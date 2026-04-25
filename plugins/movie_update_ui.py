import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import ChatAdminRequired, UserNotParticipant
from database.users_chats_db import db
from plugins.auto_poster import post_trending_poster 

logger = logging.getLogger(__name__)

# Temporary Memory for taking user inputs
WAITING_FOR_INPUT = {}

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
        [InlineKeyboardButton("🔙 Back to Group Settings", callback_data=f"group_settings#{chat_id}")]
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
    
    bot_username = client.me.username
    text = (
        "**📝 Set Post Chats (Maximum 3)**\n\n"
        f"**Posting Bot:** @{bot_username}\n\n"
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
    text = (
        f"**Set Post Chat Slot {slot}**\n\n"
        "Please send the Chat ID where you want to post movie updates.\n\n"
        "**⚠️ Requirements:**\n"
        f"• Bot must be **admin** in that channel.\n"
        "• It needs **'Post Messages'** permission.\n"
        "• Send the numeric chat ID (e.g., `-1001234567890`)\n\n"
        "_Send the ID now in this chat..._"
    )
    btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"mu_slots#{chat_id}")]]
    msg = await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    
    WAITING_FOR_INPUT[query.from_user.id] = {'action': 'set_slot', 'slot': slot, 'chat_id': int(chat_id), 'msg_id': msg.id}

@Client.on_callback_query(filters.regex(r"^mu_clearslot#"))
async def mu_clear_slot(client, query):
    _, slot, chat_id = query.data.split("#")
    settings = await db.get_group_settings(int(chat_id))
    mu = get_mu_settings(settings)
    mu['slots'][str(slot)] = None
    settings['movie_update'] = mu
    await db.update_group_settings(int(chat_id), settings)
    await query.answer(f"✅ Slot {slot} Cleared!", show_alert=True)
    await mu_slots_menu(client, query)

# ==============================================================================
# GROUP LINK MENU
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^mu_group#"))
async def mu_group_ask(client, query):
    chat_id = query.data.split("#")[1]
    text = (
        "**🔗 Set Group Link**\n\n"
        "Please send your Group Link.\n"
        "_(It must start with http:// or https://)_\n\n"
        "To remove the link, send `clear` or `0`."
    )
    btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"mu_main#{chat_id}")]]
    msg = await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    WAITING_FOR_INPUT[query.from_user.id] = {'action': 'set_group', 'chat_id': int(chat_id), 'msg_id': msg.id}

# ==============================================================================
# FOOTER BUTTONS MENU
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^mu_footer#"))
async def mu_footer_menu(client, query):
    chat_id = query.data.split("#")[1]
    settings = await db.get_group_settings(int(chat_id))
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
    chat_id = query.data.split("#")[1]
    text = (
        "**🔘 Add Footer Button**\n\n"
        "Please send the button details in this format:\n"
        "`Button Name | https://yourlink.com`\n\n"
        "**Example:**\n"
        "`Join Channel | https://t.me/filmy_studioo`"
    )
    btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"mu_footer#{chat_id}")]]
    msg = await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    WAITING_FOR_INPUT[query.from_user.id] = {'action': 'set_footer', 'chat_id': int(chat_id), 'msg_id': msg.id}

@Client.on_callback_query(filters.regex(r"^mu_clearfooter#"))
async def mu_clearfooter(client, query):
    chat_id = int(query.data.split("#")[1])
    settings = await db.get_group_settings(chat_id)
    mu = get_mu_settings(settings)
    mu['footer'] = []
    settings['movie_update'] = mu
    await db.update_group_settings(chat_id, settings)
    await query.answer("✅ All Footer Buttons Cleared!", show_alert=True)
    await mu_footer_menu(client, query)

# ==============================================================================
# MESSAGE LISTENER (FIXED 🔥)
# ==============================================================================
# 🔥 FIX: Ab ye un messages ko ignore karega jo "/" (commands) se shuru hote hain.
@Client.on_message(filters.private & filters.text & ~filters.regex(r"^/"))
async def input_listener(client, message):
    user_id = message.from_user.id
    if user_id not in WAITING_FOR_INPUT: return
        
    state = WAITING_FOR_INPUT[user_id]
    group_chat_id = state['chat_id']
    
    if state['action'] == 'set_slot':
        channel_id_str = message.text.strip()
        slot = state['slot']
        
        try: target_channel = int(channel_id_str)
        except ValueError: return await message.reply("❌ Invalid ID! Numeric ID bhejein (e.g., `-100123...`).")
            
        wait_msg = await message.reply("⏳ Checking Admin Permissions...")
        
        try:
            member = await client.get_chat_member(target_channel, client.me.id)
            if not member.privileges or not member.privileges.can_post_messages:
                return await wait_msg.edit("❌ Bot is admin but lacks 'Post Messages' permission.")
        except ChatAdminRequired: return await wait_msg.edit("❌ Error: Mujhe us channel me Admin banao pehle!")
        except Exception as e: return await wait_msg.edit(f"❌ Error: Channel nahi mila.\n`{e}`")

        settings = await db.get_group_settings(group_chat_id)
        mu = get_mu_settings(settings)
        mu['slots'][str(slot)] = target_channel
        settings['movie_update'] = mu
        await db.update_group_settings(group_chat_id, settings)
        
        del WAITING_FOR_INPUT[user_id]
        btn = [[InlineKeyboardButton("🔙 Back to Slots", callback_data=f"mu_slots#{group_chat_id}")]]
        await wait_msg.edit(f"✅ **Slot {slot} set successfully!**\nChat ID: `{target_channel}`", reply_markup=InlineKeyboardMarkup(btn))

    elif state['action'] == 'set_group':
        link = message.text.strip()
        settings = await db.get_group_settings(group_chat_id)
        mu = get_mu_settings(settings)
        
        if link.lower() in ['0', 'clear', 'none']:
            mu['group_link'] = None
            msg_txt = "✅ Group Link removed successfully!"
        else:
            if not link.startswith("http"):
                return await message.reply("❌ Invalid Link! Link must start with http:// or https://")
            mu['group_link'] = link
            msg_txt = f"✅ Group Link saved!\nLink: {link}"
            
        settings['movie_update'] = mu
        await db.update_group_settings(group_chat_id, settings)
        del WAITING_FOR_INPUT[user_id]
        btn = [[InlineKeyboardButton("🔙 Back to Menu", callback_data=f"mu_main#{group_chat_id}")]]
        await message.reply(msg_txt, reply_markup=InlineKeyboardMarkup(btn))

    elif state['action'] == 'set_footer':
        btn_data = message.text.strip()
        
        if "|" not in btn_data:
            return await message.reply("❌ Invalid Format!\nPlease use `Name | Link` format.")
            
        text_part, url_part = btn_data.split("|", 1)
        text_part = text_part.strip()
        url_part = url_part.strip()
        
        if not url_part.startswith("http"):
            return await message.reply("❌ Invalid URL! Must start with http:// or https://")
            
        settings = await db.get_group_settings(group_chat_id)
        mu = get_mu_settings(settings)
        
        mu['footer'].append({'text': text_part, 'url': url_part})
        settings['movie_update'] = mu
        await db.update_group_settings(group_chat_id, settings)
        
        del WAITING_FOR_INPUT[user_id]
        btn = [[InlineKeyboardButton("🔙 Back to Footers", callback_data=f"mu_footer#{group_chat_id}")]]
        await message.reply(f"✅ Button Added: **{text_part}**", reply_markup=InlineKeyboardMarkup(btn))

# ==============================================================================
# TEST & TOGGLES
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^mu_test#"))
async def mu_test_post(client, query):
    chat_id = int(query.data.split("#")[1])
    settings = await db.get_group_settings(chat_id)
    mu = get_mu_settings(settings)
    
    active_channels = [ch for ch in mu['slots'].values() if ch is not None]
    if not active_channels:
        return await query.answer("❌ No slots set! Pehle koi channel add karein.", show_alert=True)
        
    await query.answer("⏳ Running Test Post...", show_alert=False)
    
    success_count = 0
    for channel in active_channels:
        try:
            await post_trending_poster(client, custom_channel_id=channel, group_chat_id=chat_id) 
            success_count += 1
        except Exception as e:
            logger.error(f"Test post failed for {channel}: {e}")
            
    btn = [[InlineKeyboardButton("🔙 Back", callback_data=f"mu_main#{chat_id}")]]
    if success_count > 0:
        await query.message.edit_text(f"✅ **Test successful!**\nPosted to {success_count}/{len(active_channels)} channel(s).\n\nCheck your post channel!", reply_markup=InlineKeyboardMarkup(btn))
    else:
        await query.message.edit_text("❌ **Test Failed!**\nCould not post to any channel. Check terminal logs.", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^mu_toggle#"))
async def mu_toggle_status(client, query):
    chat_id = int(query.data.split("#")[1])
    settings = await db.get_group_settings(chat_id)
    mu = get_mu_settings(settings)
    mu['is_active'] = not mu['is_active']
    settings['movie_update'] = mu
    await db.update_group_settings(chat_id, settings)
    await mu_main_menu(client, query)
