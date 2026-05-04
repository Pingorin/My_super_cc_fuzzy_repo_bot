import logging
import asyncio
import info
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import ChatAdminRequired, UserNotParticipant
from database.users_chats_db import db
from plugins.auto_poster import post_trending_poster 

logger = logging.getLogger(__name__)

def get_mu_settings(group_settings):
    default = {
        'is_active': True,
        'slots': {'1': None, '2': None, '3': None},
        'group_link': None,
        'footer': [] 
    }
    return group_settings.get('movie_update', default)

# ==============================================================================
# MAIN MENU
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^mu_main#"))
async def mu_main_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    settings = await db.get_group_settings(chat_id)
    mu = get_mu_settings(settings)
    
    active_slots = sum(1 for v in mu['slots'].values() if v is not None)
    status_txt = "✅ Activated" if mu['is_active'] else "❌ Deactivated"
    slots_txt = f"✅ {active_slots}/3 Slots Set" if active_slots > 0 else "❌ Not Set"
    grp_txt = "✅ Set" if mu['group_link'] else "❌ Not Set"
    footer_txt = f"✅ {len(mu['footer'])} Set" if mu['footer'] else "❌ Not Set"

    text = (
        "**🎬 Movie Update Settings**\n\n"
        "**✨ Benefits:**\n"
        "• Increases channel engagement\n"
        "• Posts automatically trending movies\n"
        "• Helps you to increase your daily views\n\n"
        f"**Current Status:** {status_txt}\n"
        f"**Post Channels:** {slots_txt}\n"
        f"**Group Link:** {grp_txt}\n"
        f"**Footer Button:** {footer_txt}"
    )

    btn = [
        [InlineKeyboardButton("📝 Set Post Chat", callback_data=f"mu_slots#{chat_id}")],
        [InlineKeyboardButton("🔗 Set Group Link", callback_data=f"mu_group#{chat_id}"),
         InlineKeyboardButton("🔘 Set Footer Button", callback_data=f"mu_footer#{chat_id}")],
        [InlineKeyboardButton("🔴 Deactivate" if mu['is_active'] else "🟢 Activate", callback_data=f"mu_toggle#{chat_id}"),
         InlineKeyboardButton("🧪 Test", callback_data=f"mu_test#{chat_id}")],
        [InlineKeyboardButton("📖 Tutorial", callback_data=f"mu_tutorial#{chat_id}")],
        # 🔥 FIX: "group_settings#" ko "set_main#" kar diya gaya hai
        [InlineKeyboardButton("🔙 Back to Group Settings", callback_data=f"set_main#{chat_id}")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

# ==============================================================================
# SLOTS MENU
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^mu_slots#"))
async def mu_slots_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    settings = await db.get_group_settings(chat_id)
    mu = get_mu_settings(settings)
    
    # 🔥 SMART USERNAME DETECTOR
    poster_token = getattr(info, 'POSTER_BOT_TOKEN', "")
    my_token = getattr(info, 'BOT_TOKEN', "")
    
    if poster_token and poster_token.strip() != my_token.strip():
        bot_username = getattr(info, 'FILE_STORE_BOT', "Poster_Bot").replace("@", "")
        bot_username = f"@{bot_username}"
    else:
        bot_username = f"@{client.me.username}"
        
    text = (
        "**📝 Set Post Chats (Maximum 3)**\n\n"
        f"🤖 **Posting Bot:** {bot_username}\n\n"
        "**Current Slots:**\n"
        f"**Slot 1 :** `{mu['slots']['1'] or 'Not Set'}`\n"
        f"**Slot 2 :** `{mu['slots']['2'] or 'Not Set'}`\n"
        f"**Slot 3 :** `{mu['slots']['3'] or 'Not Set'}`"
    )

    btn = []
    for i in range(1, 4):
        slot_key = str(i)
        if mu['slots'][slot_key]:
            btn.append([InlineKeyboardButton(f"✏️ Edit Slot {i}", callback_data=f"mu_setslot#{i}#{chat_id}"),
                        InlineKeyboardButton(f"🗑️ Clear {i}", callback_data=f"mu_clearslot#{i}#{chat_id}")])
        else:
            btn.append([InlineKeyboardButton(f"➕ Set Slot {i}", callback_data=f"mu_setslot#{i}#{chat_id}")])
            
    btn.append([InlineKeyboardButton("🔙 Back", callback_data=f"mu_main#{chat_id}")])
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^mu_setslot#"))
async def mu_ask_slot(client, query):
    _, slot, chat_id = query.data.split("#")
    chat_id = int(chat_id)
    
    # 🔥 SMART USERNAME DETECTOR FOR MESSAGE
    poster_token = getattr(info, 'POSTER_BOT_TOKEN', "")
    my_token = getattr(info, 'BOT_TOKEN', "")
    
    if poster_token and poster_token.strip() != my_token.strip():
        bot_username = getattr(info, 'FILE_STORE_BOT', "Poster_Bot").replace("@", "")
        bot_username = f"@{bot_username}"
    else:
        bot_username = f"@{client.me.username}"

    # ✅ DYNAMIC TEXT UPDATED HERE
    text = (
        f"**Set Post Chat Slot {slot}**\n\n"
        "Please send the Chat ID where you want to post movie updates.\n\n"
        "**⚠️ Requirements:**\n"
        f"• 🤖 **This is Posting Bot:** {bot_username}\n"
        f"• Make sure to make **{bot_username}** an Admin in that channel/group.\n"
        "• It needs **'Post Messages'** permission.\n"
        "• Send the numeric chat ID (e.g., `-1001234567890`)\n\n"
        "_Send the ID now in this chat..._"
    )
    
    btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"mu_slots#{chat_id}")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text:
            channel_id_str = msg.text.strip()
            
            try: 
                target_channel = int(channel_id_str)
            except ValueError: 
                await msg.reply("❌ Invalid ID! Numeric ID bhejein (e.g., `-100123...`).")
                query.data = f"mu_slots#{chat_id}"
                return await mu_slots_menu(client, query)
                
            wait_msg = await msg.reply("⏳ Checking Admin Permissions...")
            
            # 🔥 BYPASS CHECK IF POSTER BOT IS USED
            if not poster_token or poster_token.strip() == my_token.strip():
                try:
                    member = await client.get_chat_member(target_channel, client.me.id)
                    if not member.privileges or not member.privileges.can_post_messages:
                        await wait_msg.edit(f"❌ **{bot_username}** is admin but lacks 'Post Messages' permission.")
                        query.data = f"mu_slots#{chat_id}"
                        return await mu_slots_menu(client, query)
                except ChatAdminRequired: 
                    await wait_msg.edit(f"❌ Error: Please make **{bot_username}** admin first!")
                    query.data = f"mu_slots#{chat_id}"
                    return await mu_slots_menu(client, query)
                except Exception as e: 
                    await wait_msg.edit(f"❌ Error: Channel nahi mila.\n`{e}`")
                    query.data = f"mu_slots#{chat_id}"
                    return await mu_slots_menu(client, query)

            settings = await db.get_group_settings(chat_id)
            mu = get_mu_settings(settings)
            mu['slots'][str(slot)] = target_channel
            settings['movie_update'] = mu
            await db.update_group_settings(chat_id, settings)
            
            btn = [[InlineKeyboardButton("🔙 Back to Slots", callback_data=f"mu_slots#{chat_id}")]]
            await wait_msg.edit(f"✅ **Slot {slot} set successfully!**\nChat ID: `{target_channel}`", reply_markup=InlineKeyboardMarkup(btn))
            
    except asyncio.TimeoutError:
        pass

@Client.on_callback_query(filters.regex(r"^mu_clearslot#"))
async def mu_clear_slot(client, query):
    _, slot, chat_id = query.data.split("#")
    settings = await db.get_group_settings(int(chat_id))
    mu = get_mu_settings(settings)
    mu['slots'][str(slot)] = None
    settings['movie_update'] = mu
    await db.update_group_settings(int(chat_id), settings)
    await query.answer(f"✅ Slot {slot} Cleared!", show_alert=True)
    
    # 🔥 UI REFRESH BUG FIXED HERE 🔥
    query.data = f"mu_slots#{chat_id}"
    await mu_slots_menu(client, query)

# ==============================================================================
# GROUP LINK MENU
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^mu_group#"))
async def mu_group_ask(client, query):
    chat_id = int(query.data.split("#")[1])
    text = (
        "**🔗 Set Group Link**\n\n"
        "Please send your Group Link.\n"
        "_(It must start with http:// or https://)_\n\n"
        "To remove the link, send `clear` or `0`."
    )
    btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"mu_main#{chat_id}")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text:
            link = msg.text.strip()
            settings = await db.get_group_settings(chat_id)
            mu = get_mu_settings(settings)
            
            if link.lower() in ['0', 'clear', 'none']:
                mu['group_link'] = None
                msg_txt = "✅ Group Link removed successfully!"
            else:
                if not link.startswith("http"):
                    await msg.reply("❌ Invalid Link! Link must start with http:// or https://")
                    query.data = f"mu_main#{chat_id}"
                    return await mu_main_menu(client, query)
                mu['group_link'] = link
                msg_txt = f"✅ Group Link saved!\nLink: {link}"
                
            settings['movie_update'] = mu
            await db.update_group_settings(chat_id, settings)
            btn = [[InlineKeyboardButton("🔙 Back to Menu", callback_data=f"mu_main#{chat_id}")]]
            await msg.reply(msg_txt, reply_markup=InlineKeyboardMarkup(btn))
    except asyncio.TimeoutError:
        pass

# ==============================================================================
# FOOTER BUTTONS MENU
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^mu_footer#"))
async def mu_footer_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    settings = await db.get_group_settings(chat_id)
    mu = get_mu_settings(settings)
    footers = mu.get('footer', [])
    
    text = "**🔘 Set Footer Button**\n\nHer post ke saath ye buttons aayenge. Aap Max 2 buttons add kr skte hai.\n\n**Current Buttons:**\n"
    if not footers:
        text += "None\n"
    else:
        for i, f in enumerate(footers, 1):
            text += f"{i}. [{f['text']}]({f['url']})\n"
            
    btn = []
    if len(footers) < 2:
        btn.append([InlineKeyboardButton("➕ Add Button", callback_data=f"mu_addfooter#{chat_id}")])
    if footers:
        btn.append([InlineKeyboardButton("🗑️ Clear All Buttons", callback_data=f"mu_clearfooter#{chat_id}")])
    btn.append([InlineKeyboardButton("🔙 Back", callback_data=f"mu_main#{chat_id}")])
    
    await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^mu_addfooter#"))
async def mu_addfooter_ask(client, query):
    chat_id = int(query.data.split("#")[1])
    text = (
        "**🔘 Add Footer Button**\n\n"
        "Please send the button details in this format:\n"
        "`Button Name | https://yourlink.com`\n\n"
        "**Example:**\n"
        "`Join Channel | https://t.me/filmy_studioo`"
    )
    btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"mu_footer#{chat_id}")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text:
            btn_data = msg.text.strip()
            
            if "|" not in btn_data:
                await msg.reply("❌ Invalid Format!\nPlease use `Name | Link` format.")
                query.data = f"mu_footer#{chat_id}"
                return await mu_footer_menu(client, query)
                
            text_part, url_part = btn_data.split("|", 1)
            text_part = text_part.strip()
            url_part = url_part.strip()
            
            if not url_part.startswith("http"):
                await msg.reply("❌ Invalid URL! Must start with http:// or https://")
                query.data = f"mu_footer#{chat_id}"
                return await mu_footer_menu(client, query)
                
            settings = await db.get_group_settings(chat_id)
            mu = get_mu_settings(settings)
            
            mu['footer'].append({'text': text_part, 'url': url_part})
            settings['movie_update'] = mu
            await db.update_group_settings(chat_id, settings)
            
            btn = [[InlineKeyboardButton("🔙 Back to Footers", callback_data=f"mu_footer#{chat_id}")]]
            await msg.reply(f"✅ Button Added: **{text_part}**", reply_markup=InlineKeyboardMarkup(btn))
    except asyncio.TimeoutError:
        pass

@Client.on_callback_query(filters.regex(r"^mu_clearfooter#"))
async def mu_clearfooter(client, query):
    chat_id = int(query.data.split("#")[1])
    settings = await db.get_group_settings(chat_id)
    mu = get_mu_settings(settings)
    mu['footer'] = []
    settings['movie_update'] = mu
    await db.update_group_settings(chat_id, settings)
    await query.answer("✅ All Footer Buttons Cleared!", show_alert=True)
    query.data = f"mu_footer#{chat_id}"
    await mu_footer_menu(client, query)

# ==============================================================================
# TEST & TOGGLES (WITH DEEP-LINK REDIRECT AND DIRECT POST LOGIC)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^mu_test#"))
async def mu_test_post(client, query):
    chat_id = int(query.data.split("#")[1])
    settings = await db.get_group_settings(chat_id)
    mu = get_mu_settings(settings)
    
    # 🔥 DEEP LINK REDIRECT LOGIC FOR MAIN BOT
    poster_token = getattr(info, 'POSTER_BOT_TOKEN', "")
    my_token = getattr(info, 'BOT_TOKEN', "")
    
    # Check if Bot B is set (Token is present and different from Main Bot)
    if poster_token and poster_token.strip() != my_token.strip():
        second_bot_username = getattr(info, 'FILE_STORE_BOT', "Poster_Bot").replace("@", "")
        url = f"https://t.me/{second_bot_username}?start=testpost_{chat_id}"
        
        text = (
            f"🤖 **Bot Redirect System**\n\n"
            f"Kyunki poster posting ka kaam **@{second_bot_username}** handle kar raha hai, isliye Test Post wahi karega.\n\n"
            f"👉 Niche diye button par click karein. Ye aapko dusre bot par le jayega aur wahan automatic test run ho jayega!"
        )
        btn = [
            [InlineKeyboardButton("🚀 Run Test on Poster Bot", url=url)],
            [InlineKeyboardButton("🔙 Back", callback_data=f"mu_main#{chat_id}")]
        ]
        return await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

    # 👇 NORMAL TEST POST (Jab Token khali ho ya Bot B me ho) 👇
    active_channels = [ch for ch in mu['slots'].values() if ch is not None]
    if not active_channels:
        return await query.answer("❌ No slots set! Pehle koi channel add karein.", show_alert=True)
        
    await query.message.edit_text("⏳ Running Test Post...", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"mu_main#{chat_id}")]]))
    
    success_count = 0
    error_logs = ""
    for channel in active_channels:
        try:
            await post_trending_poster(client, custom_channel_id=channel, group_chat_id=chat_id) 
            success_count += 1
        except Exception as e:
            logger.error(f"Test post failed for {channel}: {e}")
            error_logs += f"\n• `{channel}`: {str(e)}"
            
    bot_username = client.me.username if client.me else "Bot"
    btn = [[InlineKeyboardButton("🔙 Back", callback_data=f"mu_main#{chat_id}")]]
    
    # 🔥 NEW: Message me Bot ka username aur Admin warning
    if success_count > 0:
        success_msg = (
            f"✅ **Test successful!**\n"
            f"Posted to {success_count}/{len(active_channels)} channel(s).\n\n"
            f"🤖 **Posting Bot:** `@{bot_username}`\n"
            f"⚠️ **Note:** Make sure I am Admin in the channel to post successfully in the future!"
        )
        await query.message.edit_text(success_msg, reply_markup=InlineKeyboardMarkup(btn))
    else:
        fail_msg = (
            f"❌ **Test Failed!**\n\n"
            f"🤖 **Posting Bot:** `@{bot_username}`\n"
            f"⚠️ **Note:** Make sure I am Admin with 'Post Messages' rights in the channel!\n\n"
            f"**Error Logs:**\n{error_logs}"
        )
        await query.message.edit_text(fail_msg, reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^mu_toggle#"))
async def mu_toggle_status(client, query):
    chat_id = int(query.data.split("#")[1])
    settings = await db.get_group_settings(chat_id)
    mu = get_mu_settings(settings)
    mu['is_active'] = not mu['is_active']
    settings['movie_update'] = mu
    await db.update_group_settings(chat_id, settings)
    await mu_main_menu(client, query)
