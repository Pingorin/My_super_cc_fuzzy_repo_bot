import asyncio
import datetime
import time
import aiohttp
import pytz
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from info import ADMINS

async def check_shortener_link(domain, api):
    test_url = "https://google.com"
    api_url = f"https://{domain}/api?api={api}&url={test_url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success" or data.get("shortenedUrl"):
                        return True
    except: pass
    return False

def seconds_to_str(seconds):
    if seconds == 0: return "0s"
    if seconds < 60: return f"{seconds}s"
    if seconds < 3600: return f"{int(seconds/60)}min"
    if seconds < 86400: return f"{int(seconds/3600)}hr"
    return f"{int(seconds/86400)}days"

@Client.on_message(filters.command("settings"))
async def settings_command(client, message):
    user_id = message.from_user.id
    
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        try:
            member = await client.get_chat_member(message.chat.id, user_id)
            if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR] and user_id not in ADMINS:
                return 
        except:
            return
        
        try:
            admin_ids = []
            async for admin in client.get_chat_members(message.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                admin_ids.append(admin.user.id)
            await db.groups.update_one({"id": message.chat.id}, {"$set": {"admins": admin_ids}}, upsert=True)
            await db.add_group(message.chat.id, message.chat.title)
        except Exception:
            pass

        bot_me = await client.get_me()
        btn = [[InlineKeyboardButton("⚙️ Open Settings in PM", url=f"https://t.me/{bot_me.username}?start=settings")]]
        return await message.reply_text(
            "⚙️ **Group settings sirf Bot ke PM (Private Message) me manage ki ja sakti hain.**\n\nKripya niche diye gaye button par click karke bot ke inbox me `/settings` type karein:", 
            reply_markup=InlineKeyboardMarkup(btn)
        )

    elif message.chat.type == enums.ChatType.PRIVATE:
        user_groups = []
        seen_chats = set()
        
        db_query = {"admins": user_id}
        
        async for group in db.groups.find(db_query):
            chat_id = group.get('id')
            
            if chat_id in seen_chats:
                continue
                
            title = group.get('title')
            
            if not title or str(title) == str(chat_id) or str(title).startswith("-100"):
                continue 
                
            user_groups.append((title, chat_id))
            seen_chats.add(chat_id)
        
        if not user_groups:
            return await message.reply_text("❌ **No Groups Found!**\nKripya apne group me ja kar ek baar `/connect` type karein taaki bot group ko pehchan sake.")

        buttons = []
        for title, chat_id in user_groups:
            buttons.append([InlineKeyboardButton(f"📂 {title}", callback_data=f"set_main#{chat_id}")])
        
        await message.reply_text("⚙️ **Select your Group:**", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^set_main#"))
async def main_settings_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    try: title = (await client.get_chat(chat_id)).title
    except: title = str(chat_id)

    buttons = [
        [InlineKeyboardButton("💰 Earning method", callback_data=f"set_earn#{chat_id}"),
         InlineKeyboardButton("📢 Force Subscribe", callback_data=f"fsub_menu#{chat_id}")],
        
        [InlineKeyboardButton("📜 Result mode", callback_data=f"set_res_mode#{chat_id}"),
         InlineKeyboardButton("📄 Result per page", callback_data=f"set_page_limit#{chat_id}")],
        
        [InlineKeyboardButton("🗑️ Auto-Delete", callback_data=f"autodel_menu#{chat_id}"),
         InlineKeyboardButton("👍 Auto Reaction", callback_data=f"autoreact_ui#{chat_id}")],

        [InlineKeyboardButton("👋 Welcome Settings", callback_data=f"welcome_ui#{chat_id}"),
         InlineKeyboardButton("🛡️ Anti-Spam", callback_data=f"antispam_ui#{chat_id}")],
        
        [InlineKeyboardButton("📢 Auto Post", callback_data=f"autopost_ui#{chat_id}"),
         InlineKeyboardButton("📣 Auto Mention", callback_data=f"automention_ui#{chat_id}")],
        
        [InlineKeyboardButton("👑 Admin Free Access", callback_data=f"adm_access_ui#{chat_id}"),
         InlineKeyboardButton("📊 Daily Stats", callback_data=f"daily_stats#{chat_id}#today")],
         
        [InlineKeyboardButton("🧨 Reset Settings", callback_data=f"reset_grp_ui#{chat_id}"),
         InlineKeyboardButton("🔗 Other URLs", callback_data=f"other_urls_ui#{chat_id}")],
         
        [InlineKeyboardButton("💎 Free Premium (Referral)", callback_data=f"ref_sys_menu#{chat_id}"),
         InlineKeyboardButton("💡 Request Features", callback_data=f"req_feature#{chat_id}")],

        [InlineKeyboardButton("🎬 Set Movie Update", callback_data=f"mu_main#{chat_id}")],

        [InlineKeyboardButton("🔙 Back to Groups", callback_data="set_back_home")]
    ]
    
    await query.message.edit_text(f"⚙️ **Settings for:** {title}", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^set_res_mode#"))
async def result_mode_settings(client, query):
    chat_id = int(query.data.split("#")[1])
    
    group_data = await db.get_group_settings(chat_id)
    if not group_data: 
        await db.add_group(chat_id, "Unknown Group")
        group_data = await db.get_group_settings(chat_id)

    current = group_data.get('result_mode', 'button')

    def txt(mode_key, label):
        return f"✅ {label}" if current == mode_key else label

    text = (
        f"📜 **Result Mode for Chat ID:** `{chat_id}`\n\n"
        "Choose the display mode for search results.\n\n"
        "**Button Mode Demo**\n"
        "**Text Mode Demo**\n"
        "**Detailed Text Mode Demo**\n"
        "**Site Mode Demo**\n"
        "**Card Mode Demo**"
    )

    buttons = [
        [InlineKeyboardButton(txt('button', "Button Mode"), callback_data=f"set_rmode#{chat_id}#button"),
         InlineKeyboardButton(txt('hybrid', "Hybrid Mode"), callback_data=f"set_rmode#{chat_id}#hybrid")],
        [InlineKeyboardButton(txt('text', "Text Mode"), callback_data=f"set_rmode#{chat_id}#text"),
         InlineKeyboardButton(txt('detailed', "Detailed Text Mode"), callback_data=f"set_rmode#{chat_id}#detailed")],
        [InlineKeyboardButton(txt('card', "Card Mode"), callback_data=f"set_rmode#{chat_id}#card"),
         InlineKeyboardButton(txt('site', "Site Mode"), callback_data=f"set_rmode#{chat_id}#site")],
        [InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")]
    ]

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^set_rmode#"))
async def set_result_mode_handler(client, query):
    _, chat_id, mode = query.data.split("#")
    chat_id = int(chat_id)
    await db.update_group_settings(chat_id, {'result_mode': mode})
    await query.answer(f"Updated to {mode.capitalize()} Mode!")
    await result_mode_settings(client, query)

@Client.on_callback_query(filters.regex(r"^set_page_limit#"))
async def page_limit_settings(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    current_limit = group_data.get('result_page_limit', 10)
    
    options = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15]
    btn = []
    temp_row = []
    
    for opt in options:
        text = f"✅ {opt}" if opt == current_limit else f"{opt}"
        temp_row.append(InlineKeyboardButton(text, callback_data=f"set_limit#{opt}#{chat_id}"))
        if len(temp_row) == 4:
            btn.append(temp_row)
            temp_row = []
    if temp_row:
        btn.append(temp_row)
        
    btn.append([InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")])
    
    await query.message.edit_text(
        f"📄 **Results per Page Settings for:** `{chat_id}`\n\n"
        f"Select how many files (buttons or text entries) to show on each results page.\n\n"
        f"**Current:** {current_limit} files per page.\n"
        f"Values set for Button, Text, Detailed, Hybrid Mode.",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query(filters.regex(r"^set_limit#"))
async def save_page_limit(client, query):
    _, limit, chat_id = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'result_page_limit': int(limit)})
    await query.answer(f"Updated: {limit} files per page")
    query.data = f"set_page_limit#{chat_id}"
    await page_limit_settings(client, query)

@Client.on_callback_query(filters.regex(r"^autoreact_ui#"))
async def auto_reaction_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    is_enabled = group_data.get('auto_reaction', False)
    
    status_text = "✅ Enabled" if is_enabled else "❌ Disabled"
    btn_text = "🔴 Disable" if is_enabled else "🟢 Enable"
    toggle_data = "off" if is_enabled else "on"

    text = (
        f"👍 **Auto Reaction Settings for:** `{chat_id}`\n\n"
        "When enabled, the bot will automatically react with a random positive emoji (e.g., 👍, ❤️, 🔥) to user messages that are valid search queries.\n\n"
        "This provides quick feedback to users and makes the group more interactive.\n\n"
        f"**Current Status:** {status_text}"
    )

    buttons = [
        [InlineKeyboardButton(btn_text, callback_data=f"set_react#{chat_id}#{toggle_data}")],
        [InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^set_react#"))
async def set_reaction_handler(client, query):
    _, chat_id, action = query.data.split("#")
    chat_id = int(chat_id)
    
    new_status = True if action == "on" else False
    await db.update_group_settings(chat_id, {'auto_reaction': new_status})
    
    await auto_reaction_ui(client, query)

@Client.on_callback_query(filters.regex(r"^autodel_menu#"))
async def auto_delete_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    
    text = (
        f"🗑️ **Auto-Delete Settings for:** `{chat_id}`\n\n"
        "Choose which type of messages you want to auto-delete."
    )
    
    buttons = [
        [InlineKeyboardButton("🤖 Bot's Result Message", callback_data=f"bot_del_ui#{chat_id}")],
        [InlineKeyboardButton("👤 User's Result Message", callback_data=f"usr_del_ui#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^bot_del_ui#"))
async def bot_auto_delete_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    del_time = group_data.get('auto_delete_time', 300) 
    thanks_msg = group_data.get('delete_thanks_msg', True)
    
    def t_btn(label, seconds):
        return f"{label} ✅" if del_time == seconds else label

    if del_time == 0: time_display = "❌ Disabled"
    elif del_time < 60: time_display = f"{del_time} seconds"
    else: time_display = f"{int(del_time/60)} minute(s)"
    
    thanks_btn_text = "Thanks Msg on Delete: ✅ON" if thanks_msg else "Thanks Msg on Delete: ❌OFF"
    
    text = (
        f"🤖 **Auto-Delete Bot Messages for:** `{chat_id}`\n\n"
        "Automatically delete the bot's search result messages after a set time.\n\n"
        f"**Current Delay:** {time_display}"
    )
    
    buttons = [
        [InlineKeyboardButton(t_btn("1 min", 60), callback_data=f"set_bdel_time#{chat_id}#60"),
         InlineKeyboardButton(t_btn("2 min", 120), callback_data=f"set_bdel_time#{chat_id}#120"),
         InlineKeyboardButton(t_btn("5 min", 300), callback_data=f"set_bdel_time#{chat_id}#300"),
         InlineKeyboardButton(t_btn("10 min", 600), callback_data=f"set_bdel_time#{chat_id}#600")],
        
        [InlineKeyboardButton(t_btn("Disable Auto-Delete", 0), callback_data=f"set_bdel_time#{chat_id}#0")],
        
        [InlineKeyboardButton(thanks_btn_text, callback_data=f"toggle_thanks#{chat_id}")],
        
        [InlineKeyboardButton("🔙 Back to Auto-Delete Menu", callback_data=f"autodel_menu#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^set_bdel_time#"))
async def set_bot_delete_time(client, query):
    _, chat_id, seconds = query.data.split("#")
    chat_id = int(chat_id)
    await db.update_group_settings(chat_id, {'auto_delete_time': int(seconds)})
    await query.answer("⏱ Time Updated!")
    await bot_auto_delete_ui(client, query)

@Client.on_callback_query(filters.regex(r"^toggle_thanks#"))
async def toggle_thanks_msg(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    curr = group_data.get('delete_thanks_msg', True)
    
    await db.update_group_settings(chat_id, {'delete_thanks_msg': not curr})
    await bot_auto_delete_ui(client, query)

@Client.on_callback_query(filters.regex(r"^usr_del_ui#"))
async def user_auto_delete_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    is_enabled = group_data.get('auto_delete_user_msg', False)
    
    status_text = "✅ Enabled" if is_enabled else "❌ Disabled"
    btn_text = "🔴 Disable" if is_enabled else "🟢 Enable"
    toggle_data = "off" if is_enabled else "on"
    
    text = (
        f"👤 **Auto-Delete User Messages for:** `{chat_id}`\n\n"
        "When enabled, the bot will instantly delete a user's message after it has replied with the search results.\n\n"
        "This helps keep the group chat clean from search queries.\n\n"
        f"**Current Status:** {status_text}"
    )
    
    buttons = [
        [InlineKeyboardButton(btn_text, callback_data=f"set_udel#{chat_id}#{toggle_data}")],
        [InlineKeyboardButton("🔙 Back to Auto-Delete Menu", callback_data=f"autodel_menu#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^set_udel#"))
async def set_user_delete_handler(client, query):
    _, chat_id, action = query.data.split("#")
    chat_id = int(chat_id)
    
    new_status = True if action == "on" else False
    await db.update_group_settings(chat_id, {'auto_delete_user_msg': new_status})
    
    await user_auto_delete_ui(client, query)

@Client.on_callback_query(filters.regex(r"^welcome_ui#"))
async def welcome_settings_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    is_enabled = group_data.get('welcome_enabled', True)
    mode = group_data.get('welcome_mode', 'default') 
    
    status_icon = "✅ON" if is_enabled else "❌OFF"
    
    def chk(val): return "✅" if mode == val else ""
    
    text = (
        f"👋 **Welcome Message Settings for:** `{chat_id}`\n\n"
        "Configure the message sent to new users when they join.\n\n"
        f"[Default Welcome Demo](https://graph.org/file/4d61886e61dfa37a25945.jpg)" 
    )
    
    buttons = [
        [InlineKeyboardButton(f"Welcome Message: {status_icon}", callback_data=f"wel_toggle#{chat_id}")],
        [InlineKeyboardButton(f"Default (Image){chk('default')}", callback_data=f"wel_mode#{chat_id}#default"),
         InlineKeyboardButton(f"Custom{chk('custom')}", callback_data=f"wel_mode#{chat_id}#custom")],
    ]
    
    if mode == 'custom':
        buttons.append([InlineKeyboardButton("🎨 Configure Custom Welcome", callback_data=f"wel_cust_conf#{chat_id}")])
        
    buttons.append([InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")])
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

@Client.on_callback_query(filters.regex(r"^wel_toggle#"))
async def welcome_toggle_handler(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    curr = group_data.get('welcome_enabled', True)
    await db.update_group_settings(chat_id, {'welcome_enabled': not curr})
    await welcome_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^wel_mode#"))
async def welcome_mode_handler(client, query):
    _, chat_id, mode = query.data.split("#")
    chat_id = int(chat_id)
    await db.update_group_settings(chat_id, {'welcome_mode': mode})
    await welcome_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^wel_cust_conf#"))
async def custom_welcome_config(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    custom_text = group_data.get('custom_welcome_text')
    custom_photo = group_data.get('custom_welcome_photo')
    
    if not custom_text and not custom_photo:
        preview = "_Nothing set. Custom welcome is currently inactive._"
    else:
        txt_prev = custom_text if custom_text else "_No text set._"
        txt_prev = txt_prev.replace("{mention}", "User").replace("{username}", "@User").replace("{chat_name}", "Group")
        img_prev = "🖼️ _A custom photo is set._" if custom_photo else "🖼️ _No custom photo is set._"
        preview = f"{txt_prev}\n\n{img_prev}"
        
    text = (
        f"🎨 **Configure Custom Welcome for:** `{chat_id}`\n\n"
        f"**Current Preview:**\n"
        f"{preview}"
    )
    
    buttons = [
        [InlineKeyboardButton("✏️ Set Text", callback_data=f"wel_set_txt#{chat_id}"),
         InlineKeyboardButton("🖼️ Set Photo", callback_data=f"wel_set_img#{chat_id}")],
         
        [InlineKeyboardButton("🔄 Reset Custom Welcome", callback_data=f"wel_reset#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^wel_set_txt#"))
async def set_welcome_text(client, query):
    chat_id = int(query.data.split("#")[1])
    cancel_btn = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"wel_cust_conf#{chat_id}")]]
    
    await query.message.edit_text(
        "📝 **Set Custom Text**\n\n"
        "Please send the text you want to use.\n"
        "Variables supported:\n"
        "`{mention}` - User Mention\n"
        "`{username}` - User Username\n"
        "`{chat_name}` - Group Name",
        reply_markup=InlineKeyboardMarkup(cancel_btn)
    )
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text:
            await db.update_group_settings(chat_id, {'custom_welcome_text': msg.text})
            await msg.reply("✅ **Custom welcome text has been set.**")
            await asyncio.sleep(1)
            await custom_welcome_config(client, query) 
        else:
            await msg.reply("❌ Text only.")
            await custom_welcome_config(client, query)
    except Exception as e:
        pass 

@Client.on_callback_query(filters.regex(r"^wel_set_img#"))
async def set_welcome_photo(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    current_photo = group_data.get('custom_welcome_photo')
    
    cancel_btn = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"wel_cust_conf#{chat_id}")]]
    
    if current_photo:
        await query.message.reply_photo(
            photo=current_photo,
            caption="👆 **Current Welcome Photo**"
        )
        
    await query.message.edit_text(
        "🖼️ **Set Custom Photo**\n\n"
        "Please send the **Photo** you want to use as the thumbnail.",
        reply_markup=InlineKeyboardMarkup(cancel_btn)
    )
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.photo:
            file_id = msg.photo.file_id
            await db.update_group_settings(chat_id, {'custom_welcome_photo': file_id})
            await msg.reply("✅ **Custom welcome photo has been saved.**")
            await asyncio.sleep(1)
            await custom_welcome_config(client, query) 
        else:
            await msg.reply("❌ Photo only.")
            await custom_welcome_config(client, query)
    except Exception as e:
        pass 

@Client.on_callback_query(filters.regex(r"^wel_reset#"))
async def reset_welcome(client, query):
    chat_id = int(query.data.split("#")[1])
    
    await db.update_group_settings(chat_id, {
        'custom_welcome_text': None, 
        'custom_welcome_photo': None
    })
    
    await query.answer("🔄 Custom Welcome Reset!", show_alert=True)
    await custom_welcome_config(client, query)

@Client.on_callback_query(filters.regex(r"^antispam_ui#"))
async def antispam_settings_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    is_enabled = group_data.get('antispam_enabled', False)
    action = group_data.get('antispam_action', 'mute') 
    mute_dur = group_data.get('mute_duration', 600)
    
    status_icon = "✅ON" if is_enabled else "❌OFF"
    
    def act_chk(val): return "✅" if action == val else ""
    def time_chk(val): return "✅" if mute_dur == val and action == 'mute' else ""

    text = (
        f"🛡️ **Anti-Spam Settings for:** `{chat_id}`\n\n"
        "Automatically delete messages containing links or usernames from non-admin users."
    )
    
    if action == 'mute':
        minutes = int(mute_dur / 60)
        text += f"\n\n**Mute Duration:** {minutes} minutes"

    buttons = [
        [InlineKeyboardButton(f"Anti-Spam: {status_icon}", callback_data=f"as_toggle#{chat_id}")],
        [InlineKeyboardButton(f"Action: Warn{act_chk('mute')}", callback_data=f"as_action#{chat_id}#mute"),
         InlineKeyboardButton(f"Action: Kick{act_chk('kick')}", callback_data=f"as_action#{chat_id}#kick")]
    ]
    
    if action == 'mute':
        buttons.append([
            InlineKeyboardButton(f"10m{time_chk(600)}", callback_data=f"as_time#{chat_id}#600"),
            InlineKeyboardButton(f"20m{time_chk(1200)}", callback_data=f"as_time#{chat_id}#1200"),
            InlineKeyboardButton(f"30m{time_chk(1800)}", callback_data=f"as_time#{chat_id}#1800"),
            InlineKeyboardButton(f"60m{time_chk(3600)}", callback_data=f"as_time#{chat_id}#3600")
        ])
        
    buttons.append([InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^as_toggle#"))
async def as_toggle(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    await db.update_group_settings(chat_id, {'antispam_enabled': not group_data.get('antispam_enabled', False)})
    await antispam_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^as_action#"))
async def as_action(client, query):
    _, chat_id, val = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'antispam_action': val})
    await antispam_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^as_time#"))
async def as_time(client, query):
    _, chat_id, val = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'mute_duration': int(val)})
    await antispam_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^automention_ui#"))
async def auto_mention_settings_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    is_enabled = group_data.get('automention_enabled', True)
    interval = group_data.get('mention_interval', 300)
    
    status_icon = "✅ Enabled" if is_enabled else "❌ Disabled"
    btn_text = "Disable" if is_enabled else "Enable"
    toggle_val = "off" if is_enabled else "on"
    
    def t_chk(val): return "✅" if interval == val and is_enabled else ""

    text = (
        f"📣 **Auto Mention Settings for:** `{chat_id}`\n\n"
        "This feature will periodically mention 5 new members in the group who haven't been mentioned before, encouraging them to search for content.\n\n"
        f"**Current Status:** {status_icon}\n"
        f"**Interval:** Every {int(interval/60)} minutes.\n\n"
        f"[Auto Mention Demo](https://graph.org/file/4d61886e61dfa37a25945.jpg)"
    )
    
    buttons = [
        [InlineKeyboardButton(btn_text, callback_data=f"am_toggle#{chat_id}#{toggle_val}")],
        [InlineKeyboardButton(f"5min{t_chk(300)}", callback_data=f"am_time#{chat_id}#300"),
         InlineKeyboardButton(f"10min{t_chk(600)}", callback_data=f"am_time#{chat_id}#600"),
         InlineKeyboardButton(f"30min{t_chk(1800)}", callback_data=f"am_time#{chat_id}#1800"),
         InlineKeyboardButton(f"60min{t_chk(3600)}", callback_data=f"am_time#{chat_id}#3600")],
        [InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")])
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

@Client.on_callback_query(filters.regex(r"^am_toggle#"))
async def am_toggle_handler(client, query):
    _, chat_id, action = query.data.split("#")
    new_status = True if action == "on" else False
    await db.update_group_settings(int(chat_id), {'automention_enabled': new_status})
    await auto_mention_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^am_time#"))
async def am_time_handler(client, query):
    _, chat_id, val = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'mention_interval': int(val)})
    await auto_mention_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^autopost_ui#"))
async def auto_post_settings_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    is_enabled = group_data.get('autopost_enabled', False)
    interval = group_data.get('autopost_interval', 1800)
    del_time = group_data.get('autopost_del_time', 60)
    ad_text = group_data.get('autopost_text')
    
    ad_media = group_data.get('autopost_media_id') or group_data.get('autopost_image')
    media_type = group_data.get('autopost_media_type', 'photo' if group_data.get('autopost_image') else 'none')
    
    buttons_data = group_data.get('autopost_buttons', {})
    
    status_icon = "✅ Enabled" if is_enabled else "❌ Disabled"
    btn_text = "Disable" if is_enabled else "Enable"
    toggle_val = "off" if is_enabled else "on"
    
    txt_status = "Set" if ad_text else "Not Set"
    img_status = f"Set ({media_type.capitalize()})" if ad_media else "Not Set"
    btn_count = len(buttons_data)
    
    def t_chk(val): return "✅" if interval == val else ""
    if del_time == 0: del_str = "Never Delete"
    else: del_str = f"{int(del_time/60)} min"

    text = (
        f"📰 **Auto Post Settings for:** `{chat_id}`\n\n"
        "This feature will periodically post a custom advertisement in your group.\n\n"
        f"**Current Status:** {status_icon}\n"
        f"**Interval:** Every {int(interval/60)} min\n"
        f"**Ad Auto-Delete:** {del_str}\n"
        f"**Ad Text:** {txt_status}\n"
        f"**Ad Media:** {img_status}\n"
        f"**Buttons Configured:** {btn_count}/3\n\n"
        f"_(You can now set Photo, Video, GIF, Audio, or Sticker as Ad Media!)_"
    )
    
    buttons = [
        [InlineKeyboardButton(btn_text, callback_data=f"ap_toggle#{chat_id}#{toggle_val}")],
        [InlineKeyboardButton("Set Text", callback_data=f"ap_set_txt#{chat_id}"),
         InlineKeyboardButton("Set Media", callback_data=f"ap_set_media#{chat_id}")],
        [InlineKeyboardButton(f"⏱ Set Ad Delete Time: {del_str}", callback_data=f"ap_del_menu#{chat_id}")],
        [InlineKeyboardButton("Manage Buttons", callback_data=f"ap_btn_menu#{chat_id}"),
         InlineKeyboardButton("Reset Ad Content", callback_data=f"ap_reset#{chat_id}")],
        [InlineKeyboardButton(f"5min{t_chk(300)}", callback_data=f"ap_time#{chat_id}#300"),
         InlineKeyboardButton(f"10min{t_chk(600)}", callback_data=f"ap_time#{chat_id}#600"),
         InlineKeyboardButton(f"30min{t_chk(1800)}", callback_data=f"ap_time#{chat_id}#1800"),
         InlineKeyboardButton(f"60min{t_chk(3600)}", callback_data=f"ap_time#{chat_id}#3600")],
        [InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

@Client.on_callback_query(filters.regex(r"^ap_del_menu#"))
async def ap_delete_time_picker(client, query):
    chat_id = int(query.data.split("#")[1])
    
    text = "⏱ **Select Ad Auto-Delete Duration:**\n\nBheja gaya ad kitni der baad delete hona chahiye?"
    
    buttons = [
        [InlineKeyboardButton("1 Min", callback_data=f"set_apdel#{chat_id}#60"),
         InlineKeyboardButton("2 Min", callback_data=f"set_apdel#{chat_id}#120"),
         InlineKeyboardButton("3 Min", callback_data=f"set_apdel#{chat_id}#180")],
        [InlineKeyboardButton("5 Min", callback_data=f"set_apdel#{chat_id}#300"),
         InlineKeyboardButton("10 Min", callback_data=f"set_apdel#{chat_id}#600")],
        [InlineKeyboardButton("15 Min", callback_data=f"set_apdel#{chat_id}#900"),
         InlineKeyboardButton("30 Min", callback_data=f"set_apdel#{chat_id}#1800")],
        [InlineKeyboardButton("❌ Never Delete", callback_data=f"set_apdel#{chat_id}#0")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"autopost_ui#{chat_id}")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^set_apdel#"))
async def save_ap_delete_time(client, query):
    _, chat_id, seconds = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'autopost_del_time': int(seconds)})
    await query.answer("✅ Ad Delete Time Updated!")
    await auto_post_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^ap_toggle#"))
async def ap_toggle_handler(client, query):
    _, chat_id, action = query.data.split("#")
    chat_id = int(chat_id)
    if action == "on":
        g_data = await db.get_group_settings(chat_id)
        if not g_data.get('autopost_text') and not g_data.get('autopost_media_id') and not g_data.get('autopost_image'):
            return await query.answer("❌ Set Text or Media first!", show_alert=True)
            
    await db.update_group_settings(chat_id, {'autopost_enabled': (action == "on")})
    await auto_post_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^ap_time#"))
async def ap_time_handler(client, query):
    _, chat_id, val = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'autopost_interval': int(val)})
    await auto_post_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^ap_reset#"))
async def ap_reset_handler(client, query):
    chat_id = int(query.data.split("#")[1])
    
    await db.groups.update_one(
        {'id': chat_id},
        {'$set': {
            'autopost_text': None, 
            'autopost_image': None, 
            'autopost_media_id': None,
            'autopost_media_type': None,
            'autopost_buttons': {},
            'autopost_enabled': False
        }}
    )
    
    await query.answer("🔄 Ad Content Reset!", show_alert=True)
    await auto_post_settings_ui(client, query)

@Client.on_callback_query(filters.regex(r"^ap_set_txt#"))
async def ap_set_text(client, query):
    chat_id = int(query.data.split("#")[1])
    cancel_btn = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"autopost_ui#{chat_id}")]]
    
    await query.message.edit_text("📝 **Please send the ad text.**", reply_markup=InlineKeyboardMarkup(cancel_btn))
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text:
            await db.groups.update_one({'id': chat_id}, {'$set': {'autopost_text': msg.text}})
            await msg.reply("✅ **Ad text has been saved.**")
            await asyncio.sleep(1)
            await auto_post_settings_ui(client, query)
        else:
            await msg.reply("❌ Text only.")
            await auto_post_settings_ui(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^ap_set_img#") | filters.regex(r"^ap_set_media#"))
async def ap_set_media(client, query):
    chat_id = int(query.data.split("#")[1])
    cancel_btn = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"autopost_ui#{chat_id}")]]
    
    await query.message.edit_text(
        "🖼️ **Please send the Ad Media.**\n\n"
        "You can now send a **Photo, Video, GIF (Animation), Audio, or Sticker**.", 
        reply_markup=InlineKeyboardMarkup(cancel_btn)
    )
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        
        media_id = None
        media_type = None
        
        if msg.photo:
            media_id = msg.photo.file_id
            media_type = 'photo'
        elif msg.video:
            media_id = msg.video.file_id
            media_type = 'video'
        elif msg.animation:
            media_id = msg.animation.file_id
            media_type = 'animation'
        elif msg.audio:
            media_id = msg.audio.file_id
            media_type = 'audio'
        elif msg.sticker:
            media_id = msg.sticker.file_id
            media_type = 'sticker'
            
        if media_id:
            await db.groups.update_one(
                {'id': chat_id}, 
                {'$set': {
                    'autopost_media_id': media_id, 
                    'autopost_media_type': media_type,
                    'autopost_image': media_id if media_type == 'photo' else None 
                }}
            )
            await msg.reply(f"✅ **Ad {media_type.capitalize()} has been saved.**")
            await asyncio.sleep(1)
            await auto_post_settings_ui(client, query)
        else:
            await msg.reply("❌ Invalid format. Please send a valid Photo, Video, GIF, Audio, or Sticker.")
            await auto_post_settings_ui(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^ap_btn_menu#"))
async def ap_buttons_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    buttons_data = group_data.get('autopost_buttons', {})
    
    text = (
        f"🎛️ **Manage Ad Buttons for:** `{chat_id}`\n\n"
        "Configure up to 3 URL buttons for your ad."
    )
    
    kb = []
    
    for i in range(1, 4):
        slot = str(i)
        if slot in buttons_data:
            btn_name = buttons_data[slot]['text']
            kb.append([
                InlineKeyboardButton(f"Btn {slot}: {btn_name}", callback_data="ignore"),
                InlineKeyboardButton("🗑️ Delete", callback_data=f"ap_del_btn#{chat_id}#{slot}")
            ])
        else:
            kb.append([InlineKeyboardButton(f"➕ Set Button {slot}", callback_data=f"ap_set_btn#{chat_id}#{slot}")])
            
    kb.append([InlineKeyboardButton("🔙 Back to Ad Settings", callback_data=f"autopost_ui#{chat_id}")])
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

@Client.on_callback_query(filters.regex(r"^ap_set_btn#"))
async def ap_set_button_step1(client, query):
    _, chat_id, slot = query.data.split("#")
    chat_id = int(chat_id)
    cancel_btn = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"ap_btn_menu#{chat_id}")]]
    
    await query.message.edit_text(f"📝 **Send button name for Slot {slot}**", reply_markup=InlineKeyboardMarkup(cancel_btn))
    
    try:
        name_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if not name_msg.text: return await query.message.edit_text("❌ Text only.", reply_markup=InlineKeyboardMarkup(cancel_btn))
        btn_name = name_msg.text
        
        await query.message.edit_text(
            f"✅ Button text set to **{btn_name}**.\n\nNow, please send the **Full URL** for this button.",
            reply_markup=InlineKeyboardMarkup(cancel_btn)
        )
        
        url_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if not url_msg.text: return await query.message.edit_text("❌ Text only.", reply_markup=InlineKeyboardMarkup(cancel_btn))
        btn_url = url_msg.text
        
        await db.set_autopost_button(chat_id, slot, btn_name, btn_url)
        await query.message.edit_text(f"✅ **Button for Slot {slot} has been saved.**")
        await asyncio.sleep(1)
        await ap_buttons_menu(client, query)
        
    except Exception as e:
        print(e)

@Client.on_callback_query(filters.regex(r"^ap_del_btn#"))
async def ap_delete_button(client, query):
    _, chat_id, slot = query.data.split("#")
    await db.remove_autopost_button(int(chat_id), slot)
    await ap_buttons_menu(client, query)

@Client.on_callback_query(filters.regex(r"^adm_access_ui#"))
async def admin_access_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    is_enabled = group_data.get('admin_free_access', False)
    
    try:
        count = await client.get_chat_members_count(chat_id)
    except Exception as e:
        count = 0 
        
    REQ_COUNT = 100
    
    status_icon = "✅ Enable" if is_enabled else "❌ Disabled"
    
    if count >= REQ_COUNT:
        req_text = f"✅ Group must have over {REQ_COUNT} members (Currently: {count})."
        can_enable = True
    else:
        req_text = f"❌ Group must have over {REQ_COUNT} members (Currently: {count})."
        can_enable = False

    text = (
        f"👑 **Admin Free Access Settings for:** `{chat_id}`\n\n"
        "When enabled, all administrators in this group will be treated as premium users. "
        "They will bypass all shorteners and payment steps to get direct file access.\n\n"
        f"**Current Status:** {status_icon}\n\n"
        f"**Requirement to Enable:**\n"
        f"{req_text}"
    )
    
    buttons = []
    
    if can_enable:
        if is_enabled:
            buttons.append([InlineKeyboardButton("Disable Admin Access", callback_data=f"adm_acc_toggle#{chat_id}#off")])
        else:
            buttons.append([InlineKeyboardButton("Enable Admin Access", callback_data=f"adm_acc_toggle#{chat_id}#on")])
    else:
        buttons.append([InlineKeyboardButton("🔄 Re-check Requirements", callback_data=f"adm_access_ui#{chat_id}")])

    buttons.append([InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")])
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^adm_acc_toggle#"))
async def admin_access_toggle(client, query):
    _, chat_id, action = query.data.split("#")
    chat_id = int(chat_id)
    
    try: count = await client.get_chat_members_count(chat_id)
    except: count = 0
    
    if action == "on" and count < 100:
        return await query.answer("❌ Requirements not met!", show_alert=True)
        
    new_status = True if action == "on" else False
    await db.update_group_settings(chat_id, {'admin_free_access': new_status})
    
    await admin_access_ui(client, query)

@Client.on_callback_query(filters.regex(r"^daily_stats#"))
async def daily_stats_ui(client, query):
    _, chat_id, date_param = query.data.split("#")
    chat_id = int(chat_id)
    
    tz = pytz.timezone('Asia/Kolkata')
    today = datetime.datetime.now(tz)
    
    if date_param == "today":
        target_date = today
    else:
        target_date = datetime.datetime.strptime(date_param, "%Y-%m-%d").replace(tzinfo=tz)
    
    date_str = target_date.strftime("%Y-%m-%d")
    display_date = target_date.strftime("%B %d, %Y")
    
    if date_str == today.strftime("%Y-%m-%d"): 
        display_date = "Today (Live 🟢)"

    try:
        stats = await db.get_group_stats_by_date(chat_id, date_str)
    except:
        stats = None
        
    if not stats: 
        stats = {} 

    group_settings = await db.get_group_settings(chat_id)
    notify_status = "✅ ON" if group_settings.get('daily_stats_notify', True) else "❌ OFF"
    
    req = stats.get('req', 0)
    suc = stats.get('suc', 0)
    failed = req - suc if req > suc else 0
    spam_w = stats.get('spam_w', 0)
    spam_k = stats.get('spam_k', 0)
    refs = stats.get('referrals', 0)
    
    search_ratio = round((suc / req * 100), 2) if req > 0 else 0.0

    shortener_data = stats.get('shorteners', {})
    shortener_text = ""
    
    if not shortener_data:
        shortener_text = "  └ _No shortener data available for this date._"
    else:
        for safe_domain, data in shortener_data.items():
            real_domain = safe_domain.replace('_', '.').capitalize()
            gen = data.get('gen', 0)
            ver = data.get('ver', 0)
            failed_link = gen - ver if gen > ver else 0
            v_ratio = round((ver / gen * 100), 2) if gen > 0 else 0.0
            f_ratio = round((failed_link / gen * 100), 2) if gen > 0 else 0.0
            
            shortener_text += (
                f"  🌐 **{real_domain}**\n"
                f"    ├ Generated: `{gen}`\n"
                f"    ├ Verified: `{ver}` ({v_ratio}%)\n"
                f"    └ Failed: `{failed_link}` ({f_ratio}%)\n\n"
            )

    text = (
        f"📊 **Analytics Dashboard**\n\n"
        f"📅 **Date:** {display_date}\n\n"
        f"🔍 **Search Statistics:**\n"
        f"  ├ Total Searches: `{req}`\n"
        f"  ├ Successful: `{suc}` ({search_ratio}%)\n"
        f"  └ Failed/Missed: `{failed}`\n\n"
        f"🛡️ **Anti-Spam Blocks:**\n"
        f"  ├ Warned: `{spam_w}`\n"
        f"  └ Kicked: `{spam_k}`\n\n"
        f"🤝 **Referrals Joined:** `{refs}`\n\n"
        f"🔗 **Shortener Statistics:**\n"
        f"{shortener_text}"
    )

    buttons = []
    nav_row = []
    
    prev_date = target_date - datetime.timedelta(days=1)
    limit_date = today - datetime.timedelta(days=10)
    
    if prev_date >= limit_date:
        nav_row.append(InlineKeyboardButton("⬅️ Prev Day", callback_data=f"daily_stats#{chat_id}#{prev_date.strftime('%Y-%m-%d')}"))
    
    nav_row.append(InlineKeyboardButton("🔄 Refresh", callback_data=f"daily_stats#{chat_id}#{date_str}"))

    next_date = target_date + datetime.timedelta(days=1)
    if next_date <= today:
        nav_row.append(InlineKeyboardButton("Next Day ➡️", callback_data=f"daily_stats#{chat_id}#{next_date.strftime('%Y-%m-%d')}"))

    buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton(f"Daily Auto-Report: {notify_status}", callback_data=f"ds_notify#{chat_id}#{date_str}")])
    buttons.append([InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^ds_notify#"))
async def daily_stats_notify_toggle(client, query):
    _, chat_id, current_view_date = query.data.split("#")
    chat_id = int(chat_id)
    group_settings = await db.get_group_settings(chat_id)
    curr = group_settings.get('daily_stats_notify', True)
    
    await db.update_group_settings(chat_id, {'daily_stats_notify': not curr})
    query.data = f"daily_stats#{chat_id}#{current_view_date}"
    await daily_stats_ui(client, query)

@Client.on_callback_query(filters.regex(r"^admin_report#"))
async def admin_full_report_nav(client, query):
    parts = query.data.split("#")
    date_str = parts[1]
    page = int(parts[2])
    
    all_groups = await db.get_all_groups_stats(date_str)
    total_groups = len(all_groups)
    
    if total_groups == 0:
        return await query.answer("No data found for this date.", show_alert=True)
    
    if page >= total_groups: page = 0
    if page < 0: page = total_groups - 1
    
    data = all_groups[page]
    
    req = data.get('req', 0)
    suc = data.get('suc', 0)
    failed = req - suc
    ratio = round((suc / req * 100), 2) if req > 0 else 0.0
    
    link_gen = data.get('link_gen', 0)
    link_ver = data.get('link_ver', 0)
    l_ratio = round((link_ver / link_gen * 100), 2) if link_gen > 0 else 0.0

    shortener_data = data.get('shorteners', {})
    shortener_text = ""
    
    if not shortener_data:
        shortener_text = "  - No data available."
    else:
        for safe_domain, s_data in shortener_data.items():
            real_domain = safe_domain.replace('_', '.').capitalize()
            gen = s_data.get('gen', 0)
            ver = s_data.get('ver', 0)
            s_ratio = round((ver / gen * 100), 2) if gen > 0 else 0.0
            
            shortener_text += (
                f"  - **{real_domain}**\n"
                f"    - Generated: {gen} | Verified: {ver} | Ratio: {s_ratio}%\n"
            )
    
    text = (
        f"📊 **Full Daily Report for {date_str}**\n\n"
        f"» **Group ({page + 1}/{total_groups}):** {data['title']}\n"
        f"Mode: NONE\n\n"
        f"🔍 **Search Statistics:**\n"
        f"  - Total Requests: {req}\n"
        f"  - Successful: {suc}\n"
        f"  - Failed: {failed}\n"
        f"  - Success Ratio: {ratio}%\n\n"
        f"🔗 **Shortener Statistics:**\n"
        f"{shortener_text}"
    )
    
    buttons = []
    nav = []
    nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_report#{date_str}#{page-1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_groups}", callback_data="ignore"))
    nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_report#{date_str}#{page+1}"))
    buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^fsub_menu#"))
async def fsub_configure_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    
    text = (
        "📢 **Force Subscribe Settings**\n\n"
        "Select which type of FSub you want to configure:"
    )
    
    buttons = [
        [InlineKeyboardButton("Request Fsub (Auth 1,2,4)", callback_data=f"fsub_req_menu#{chat_id}")],
        [InlineKeyboardButton("Normal Fsub (Auth 3, 5)", callback_data=f"fsub_norm_menu#{chat_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"set_main#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^fsub_req_menu#"))
async def request_fsub_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    fsub = group_data.get('fsub_channels', {}) if group_data else {}
    if not isinstance(fsub, dict): fsub = {}

    async def get_name(id_val):
        if not id_val: return "Not Set ❌"
        try:
            chat = await client.get_chat(id_val)
            return f"{chat.title} ({id_val})"
        except: return f"Unknown ({id_val})"

    s1 = fsub.get('1')
    s2 = fsub.get('2')
    s4 = fsub.get('4')

    name1 = await get_name(s1)
    name2 = await get_name(s2)
    name4 = await get_name(s4)

    text = (
        f"⚙️ **Configure Request F-Sub Channels for:** `{chat_id}`\n\n"
        f"1️⃣ **Slot 1:** `{name1}`\n"
        f"2️⃣ **Slot 2:** `{name2}`\n"
        f"4️⃣ **Slot 4:** `{name4}` (Post-Verify)"
    )

    buttons = []
    if s1: buttons.append([InlineKeyboardButton("✏️ Edit Slot 1", callback_data=f"set_fsub#{chat_id}#1"), InlineKeyboardButton("🗑️ Clear Slot 1", callback_data=f"clr_fsub#{chat_id}#1")])
    else: buttons.append([InlineKeyboardButton("➕ Set Slot 1", callback_data=f"set_fsub#{chat_id}#1")])

    if s2: buttons.append([InlineKeyboardButton("✏️ Edit Slot 2", callback_data=f"set_fsub#{chat_id}#2"), InlineKeyboardButton("🗑️ Clear Slot 2", callback_data=f"clr_fsub#{chat_id}#2")])
    else: buttons.append([InlineKeyboardButton("➕ Set Slot 2", callback_data=f"set_fsub#{chat_id}#2")])

    if s4: buttons.append([InlineKeyboardButton("✏️ Edit Slot 4", callback_data=f"set_fsub#{chat_id}#4"), InlineKeyboardButton("🗑️ Clear Slot 4", callback_data=f"clr_fsub#{chat_id}#4")])
    else: buttons.append([InlineKeyboardButton("➕ Set Slot 4", callback_data=f"set_fsub#{chat_id}#4")])

    if s1 or s2 or s4: buttons.append([InlineKeyboardButton("⛔ Remove All Request Fsub", callback_data=f"rem_req_all#{chat_id}")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"fsub_menu#{chat_id}")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^fsub_norm_menu#"))
async def normal_fsub_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    fsub = group_data.get('fsub_channels', {}) if group_data else {}
    if not isinstance(fsub, dict): fsub = {}

    async def get_name(id_val):
        if not id_val: return "Not Set ❌"
        if isinstance(id_val, str) and ("t.me" in id_val or "http" in id_val):
            return f"Link Set ({id_val})"
        try:
            chat = await client.get_chat(id_val)
            return f"{chat.title} ({id_val})"
        except: return f"Unknown ({id_val})"

    s3 = fsub.get('3')
    s5 = fsub.get('5') 
    
    name3 = await get_name(s3)
    name5 = await get_name(s5)

    text = (
        f"⚙️ **Configure Normal F-Sub (Auth 3, 5) for:** `{chat_id}`\n\n"
        f"3️⃣ **Slot 3:** `{name3}`\n"
        f"5️⃣ **Slot 5:** `{name5}`"
    )

    buttons = []
    if s3: buttons.append([InlineKeyboardButton("✏️ Edit Slot 3", callback_data=f"set_fsub#{chat_id}#3"), InlineKeyboardButton("🗑️ Clear Slot 3", callback_data=f"clr_fsub#{chat_id}#3")])
    else: buttons.append([InlineKeyboardButton("➕ Set Slot 3", callback_data=f"set_fsub#{chat_id}#3")])

    if s5: buttons.append([InlineKeyboardButton("✏️ Edit Slot 5", callback_data=f"set_fsub#{chat_id}#5"), InlineKeyboardButton("🗑️ Clear Slot 5", callback_data=f"clr_fsub#{chat_id}#5")])
    else: buttons.append([InlineKeyboardButton("➕ Set Slot 5", callback_data=f"set_fsub#{chat_id}#5")])

    if s3 or s5: buttons.append([InlineKeyboardButton("⛔ Remove All Normal Fsub", callback_data=f"rem_norm_all#{chat_id}")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"fsub_menu#{chat_id}")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^set_fsub#"))
async def set_fsub_input(client, query):
    _, chat_id, slot = query.data.split("#")
    chat_id = int(chat_id)
    user_id = query.from_user.id
    
    back_cb = f"fsub_req_menu#{chat_id}" if slot in ['1', '2', '4'] else f"fsub_norm_menu#{chat_id}"
    
    txt = f"🆔 **Set Slot {slot}**\n\n"
    txt += "1. **Option A (Recommended):** Add bot as Admin in Channel & Forward Message.\n"
    if slot == '5':
        txt += "2. **Option B (Link Only):** Send Group Link (Button Only, No Verify).\n"
    else:
        txt += "2. **Option B:** Send Channel ID.\n"
    txt += "\n⚠️ **Note:** Bot MUST be Admin in target channel!"

    await query.message.edit_text(
        txt,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=back_cb)]])
    )
    
    try:
        msg = await client.listen(user_id, timeout=60)
    except asyncio.TimeoutError:
        return await query.message.edit_text("❌ Timeout.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=back_cb)]]))

    if msg.text or msg.forward_from_chat:
        try:
            input_identifier = None
            is_link_mode = False

            if msg.forward_from_chat:
                input_identifier = msg.forward_from_chat.id
            elif msg.text:
                text = msg.text.strip()
                if slot == '5' and ("t.me/" in text or "http" in text):
                    is_link_mode = True
                    input_identifier = text
                else:
                    input_identifier = text

            if is_link_mode:
                await db.update_fsub_channel(chat_id, slot, input_identifier)
                await msg.reply(f"✅ **Saved Link!**\nSlot {slot}: `{input_identifier}`\n(Verification: OFF - Button Only)")
            
            else:
                real_chat = await client.get_chat(input_identifier)
                try:
                    me = await client.get_chat_member(real_chat.id, "me")
                    if me.status != enums.ChatMemberStatus.ADMINISTRATOR:
                        await msg.reply(f"❌ **Error:** I am not an Admin in **{real_chat.title}**!\nPlease promote me and try again.")
                        if slot in ['1', '2', '4']: return await request_fsub_menu(client, query)
                        else: return await normal_fsub_menu(client, query)
                except Exception as e:
                    await msg.reply(f"❌ **Error:** Could not check Admin status.\nMake sure I am added to the channel.\n`{e}`")
                    if slot in ['1', '2', '4']: return await request_fsub_menu(client, query)
                    else: return await normal_fsub_menu(client, query)

                await db.update_fsub_channel(chat_id, slot, real_chat.id)
                await msg.reply(f"✅ **Saved!**\nSlot {slot}: {real_chat.title}\nID: `{real_chat.id}`")

            if slot in ['1', '2', '4']: await request_fsub_menu(client, query)
            else: await normal_fsub_menu(client, query)

        except Exception as e:
            await msg.reply(f"❌ **Error:** Invalid ID or Channel not found.\n`{e}`")
            if slot in ['1', '2', '4']: await request_fsub_menu(client, query)
            else: await normal_fsub_menu(client, query)
    else:
        await msg.reply("❌ Invalid input (Text or Forward only).")
        if slot in ['1', '2', '4']: await request_fsub_menu(client, query)
        else: await normal_fsub_menu(client, query)

@Client.on_callback_query(filters.regex(r"^clr_fsub#"))
async def clear_single_fsub(client, query):
    _, chat_id, slot = query.data.split("#")
    chat_id = int(chat_id)
    await db.remove_fsub_channel(chat_id, slot)
    
    if slot in ['1', '2', '4']: await request_fsub_menu(client, query)
    else: await normal_fsub_menu(client, query)

@Client.on_callback_query(filters.regex(r"^rem_req_all#"))
async def remove_req_all(client, query):
    chat_id = int(query.data.split("#")[1])
    await db.remove_fsub_channel(chat_id, '1')
    await db.remove_fsub_channel(chat_id, '2')
    await db.remove_fsub_channel(chat_id, '4')
    await query.answer("All Request Fsub Channels Removed!", show_alert=True)
    await request_fsub_menu(client, query)

@Client.on_callback_query(filters.regex(r"^rem_norm_all#"))
async def remove_norm_all(client, query):
    chat_id = int(query.data.split("#")[1])
    await db.remove_fsub_channel(chat_id, '3')
    await db.remove_fsub_channel(chat_id, '5')
    await query.answer("All Normal Fsub Channels Removed!", show_alert=True)
    await normal_fsub_menu(client, query)

@Client.on_callback_query(filters.regex(r"^set_earn#"))
async def earning_settings(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    if not group_data: 
        await db.add_group(chat_id, "Unknown Group")
        group_data = await db.get_group_settings(chat_id)
    
    active_mode = "SHORTLINK" if group_data.get('is_shortlink_active', True) else "FSUB (Disable Shortlink)"
    buttons = [
        [InlineKeyboardButton("🔗 Configure Mode", callback_data=f"set_smode#{chat_id}")],
        [InlineKeyboardButton("⚙️ Set URLs/APIs", callback_data=f"set_slots#{chat_id}")],
        [InlineKeyboardButton("🚫 Disable Shortlink", callback_data=f"set_disable#{chat_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"set_main#{chat_id}")]
    ]
    await query.message.edit_text(f"💰 **Earning Settings**\nActive Mode: `{active_mode}`", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^set_smode#"))
async def shortlink_config(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    if not group_data: group_data = {}

    mode = group_data.get('shortener_mode', 'dynamic').lower()
    t_dynamic = group_data.get('time_dynamic', 86400)
    t_together = group_data.get('time_together', 604800)
    t_together_3 = group_data.get('time_together_3', 86400)
    
    d_tick = "✅ " if mode == 'dynamic' else ""
    t_tick = "✅ " if mode == 'together' else ""
    s_tick = "✅ " if mode == 'smart' else ""
    
    mode_btns = [
        InlineKeyboardButton(f"{d_tick}Dynamic", callback_data=f"set_type#{chat_id}#dynamic"),
        InlineKeyboardButton(f"{t_tick}Together", callback_data=f"set_type#{chat_id}#together"),
        InlineKeyboardButton(f"{s_tick}Smart", callback_data=f"set_type#{chat_id}#smart")
    ]
    custom_btns = []
    desc = ""
    
    if mode == 'dynamic':
        desc = f"**Dynamic Mode:** 1->2->3.\n⏱ Access: `{seconds_to_str(t_dynamic)}`"
        custom_btns.append([InlineKeyboardButton("⏰ Set Access Time", callback_data=f"time_ui#{chat_id}#time_dynamic")])
    elif mode == 'together':
        desc = f"**Together Mode:** All links at once.\n1-2 Link Time: `{seconds_to_str(t_together)}`\n3 Link Time: `{seconds_to_str(t_together_3)}`"
        custom_btns.append([InlineKeyboardButton("⏰ Time (1-2 Links)", callback_data=f"time_ui#{chat_id}#time_together")])
        custom_btns.append([InlineKeyboardButton("⏰ Time (3 Links)", callback_data=f"time_ui#{chat_id}#time_together_3")])
    elif mode == 'smart':
        t_smart_full = group_data.get('time_smart', 86400)
        t_smart_gap1 = group_data.get('time_gap1', 300)
        t_smart_gap2 = group_data.get('time_gap2', 300)
        desc = f"**Smart Mode:** Waterfall Logic.\nGap 1: {seconds_to_str(t_smart_gap1)} | Gap 2: {seconds_to_str(t_smart_gap2)}\nFull Access: {seconds_to_str(t_smart_full)}"
        
        custom_btns.append([InlineKeyboardButton("⏳ Gap 1", callback_data=f"time_ui#{chat_id}#time_gap1"),
                            InlineKeyboardButton("⏳ Gap 2", callback_data=f"time_ui#{chat_id}#time_gap2")])
        custom_btns.append([InlineKeyboardButton("⏰ Set Full Access", callback_data=f"time_ui#{chat_id}#time_smart")])

    footer_btns = [[InlineKeyboardButton("⚙️ Configure Shorteners", callback_data=f"set_slots#{chat_id}")],
                   [InlineKeyboardButton("🔙 Back", callback_data=f"set_earn#{chat_id}")]]
    await query.message.edit_text(f"🔗 **Shortener Mode Config**\n\n{desc}", reply_markup=InlineKeyboardMarkup([mode_btns] + custom_btns + footer_btns))

@Client.on_callback_query(filters.regex(r"^set_type#"))
async def set_mode_handler(client, query):
    _, chat_id, mode = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'shortener_mode': mode})
    await shortlink_config(client, query)

@Client.on_callback_query(filters.regex(r"^time_ui#"))
async def time_picker_ui(client, query):
    _, chat_id, key = query.data.split("#")
    
    names = {
        'time_dynamic': "Dynamic Full Access",
        'time_gap1': "Smart Gap 1",
        'time_gap2': "Smart Gap 2",
        'time_smart': "Smart Full Access",
        'time_together': "Together Base Access (1/2 Links)",
        'time_together_3': "Together 3-Link Final Access"
    }
    name = names.get(key, "Time")

    text = f"⏱ **Set Time for {name}**\n\nChoose a duration:"
    
    if "gap" in key:
        buttons = [
            [InlineKeyboardButton("5 Mins", callback_data=f"save_time#{chat_id}#{key}#{5*60}"),
             InlineKeyboardButton("15 Mins", callback_data=f"save_time#{chat_id}#{key}#{15*60}")],
            [InlineKeyboardButton("1 Hour", callback_data=f"save_time#{chat_id}#{key}#{3600}"),
             InlineKeyboardButton("3 Hours", callback_data=f"save_time#{chat_id}#{key}#{3*3600}")]
        ]
    else:
        buttons = [
            [InlineKeyboardButton("12 Hours", callback_data=f"save_time#{chat_id}#{key}#{12*3600}"),
             InlineKeyboardButton("24 Hours", callback_data=f"save_time#{chat_id}#{key}#{86400}")],
            [InlineKeyboardButton("3 Days", callback_data=f"save_time#{chat_id}#{key}#{3*86400}"),
             InlineKeyboardButton("7 Days", callback_data=f"save_time#{chat_id}#{key}#{7*86400}")],
            [InlineKeyboardButton("1 Month", callback_data=f"save_time#{chat_id}#{key}#{30*86400}")]
        ]
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"set_smode#{chat_id}")])
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^save_time#"))
async def save_time_handler(client, query):
    _, chat_id, key, seconds = query.data.split("#")
    await db.update_group_settings(int(chat_id), {key: int(seconds)})
    await query.answer("✅ Time Updated!", show_alert=True)
    await shortlink_config(client, query)

@Client.on_callback_query(filters.regex(r"^set_slots#"))
async def configure_slots(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    if not group_data: group_data = {}
    shorteners = group_data.get('shorteners', {})
    
    current_mode = group_data.get('shortener_mode', 'dynamic').capitalize()
    interval = group_data.get('time_dynamic', 86400) if current_mode == 'Dynamic' else group_data.get('time_smart', 86400)
    interval_hours = int(interval / 3600)

    status_text = ""
    for i in range(1, 4):
        s_data = shorteners.get(str(i))
        if s_data: status_text += f"✅ Shortener {i}: {s_data['site']}\n"
        else: status_text += f"❌ Shortener {i}: Not Set\n"

    text = (
        f"🛠️ **Configuring {current_mode} Type for:** `{chat_id}`\n\n"
        f"**Verification Interval:** {interval_hours} hours\n\n"
        f"**Your Setup:**\n{status_text}"
    )

    buttons = []
    for i in range(1, 4):
        s_data = shorteners.get(str(i))
        if s_data: buttons.append([InlineKeyboardButton(f"✏️ Edit Slot {i}", callback_data=f"edit_slot#{chat_id}#{i}"), InlineKeyboardButton(f"🗑️ Reset {i}", callback_data=f"del_slot#{chat_id}#{i}")])
        else: buttons.append([InlineKeyboardButton(f"➕ Set Shortener {i}", callback_data=f"add_slot#{chat_id}#{i}")])

    help_text_btn = f"How {current_mode} mode works"
    footer_btns = [
        [InlineKeyboardButton("🧪 Test Connections", callback_data=f"test_sl#{chat_id}")],
        [InlineKeyboardButton(f"ℹ️ {help_text_btn}", url="https://t.me/YourChannel")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"set_smode#{chat_id}")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons + footer_btns))

@Client.on_callback_query(filters.regex(r"^add_slot#") | filters.regex(r"^edit_slot#"))
async def input_slot_req(client, query):
    _, chat_id, slot = query.data.split("#")
    chat_id = int(chat_id)
    cancel_btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"set_slots#{chat_id}")]]
    
    await query.message.edit_text(f"Please send **Domain** for Slot {slot}.\n(e.g. shareus.in)", reply_markup=InlineKeyboardMarkup(cancel_btn))
    try:
        domain_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if not domain_msg.text: return await query.message.edit_text("❌ Input must be text.", reply_markup=InlineKeyboardMarkup(cancel_btn))
        domain = domain_msg.text.strip()
        await domain_msg.delete()
        
        await query.message.edit_text(f"✅ Domain set.\nNow send **API Key** for Slot {slot}.", reply_markup=InlineKeyboardMarkup(cancel_btn))
        api_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if not api_msg.text: return await query.message.edit_text("❌ Text only!", reply_markup=InlineKeyboardMarkup(cancel_btn))
        api = api_msg.text.strip()
        await api_msg.delete()
        
        await db.add_shortener(chat_id, slot, domain, api)
        await query.message.edit_text("✅ Saved!")
        await asyncio.sleep(1)
        query.data = f"set_slots#{chat_id}"
        await configure_slots(client, query)
    except: return

@Client.on_callback_query(filters.regex(r"^del_slot#"))
async def delete_slot(client, query):
    _, chat_id, slot = query.data.split("#")
    await db.remove_shortener(int(chat_id), slot)
    await query.answer("🗑️ Cleared!", show_alert=True)
    await configure_slots(client, query)

@Client.on_callback_query(filters.regex(r"^test_sl#"))
async def test_shorteners(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    shorteners = group_data.get('shorteners', {})
    if not shorteners: return await query.answer("⚠️ No shorteners set!", show_alert=True)
    
    await query.message.edit_text("🧪 **Testing connections...**")
    results = []
    all_success = True
    
    for i in range(1, 4):
        s_data = shorteners.get(str(i))
        if s_data:
            is_working = await check_shortener_link(s_data['site'], s_data['api'])
            if is_working: results.append(f" - {s_data['site']}: ✅ Success")
            else: 
                results.append(f" - {s_data['site']}: ❌ Failed")
                all_success = False

    back_btn = [[InlineKeyboardButton("🔙 Back", callback_data=f"set_slots#{chat_id}")]]
    text = "🎉 **All Working!**" if all_success else "📊 **Results:**\n" + "\n".join(results)
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(back_btn))

@Client.on_callback_query(filters.regex(r"^set_disable#"))
async def disable_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    is_active = group_data.get('is_shortlink_active', True)
    
    cb_data = f"act_toggle#{chat_id}#off" if is_active else f"act_toggle#{chat_id}#on"
    buttons = [[InlineKeyboardButton("🔴 Disable" if is_active else "🟢 Enable", callback_data=cb_data)], [InlineKeyboardButton("🔙 Back", callback_data=f"set_earn#{chat_id}")]]
    await query.message.edit_text(f"🚫 **Shortlink Mode Status:** {'✅ ON' if is_active else '❌ OFF'}", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^act_toggle#"))
async def toggle_act(client, query):
    _, chat_id, action = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'is_shortlink_active': (action == "on")})
    await disable_menu(client, query)

@Client.on_callback_query(filters.regex(r"^reset_grp_ui#"))
async def reset_confirm_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    
    text = (
        f"⚠️ **Are you sure?**\n\n"
        "This will **PERMANENTLY DELETE** all settings for this group, including:\n"
        "• Fsub Channels\n"
        "• All Shortener & Earning Configurations\n"
        "• Welcome Messages, Anti-Spam, etc.\n\n"
        "**This action is IRREVERSIBLE.**\n"
        "_(This will NOT affect user verification data)_"
    )
    
    buttons = [
        [InlineKeyboardButton("✅ Yes, Reset All Settings", callback_data=f"reset_grp_now#{chat_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"set_main#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^reset_grp_now#"))
async def reset_group_now(client, query):
    chat_id = int(query.data.split("#")[1])
    
    await db.reset_group_settings(chat_id)
    
    text = (
        "✅ **Settings Reset Complete!**\n\n"
        "All settings (Shorteners, Fsub, Welcome, etc.) have been restored to **Default**.\n"
        "The bot is still connected to the group."
    )
    
    btn = [[InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")]]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^other_urls_ui#"))
async def other_urls_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    cap_url = "Set" if group_data.get('caption_url') else "Not Set"
    cap_btn = "Set" if (group_data.get('caption_btn_text') and group_data.get('caption_btn_url')) else "Not Set"
    howto = "Set" if group_data.get('howto_url') else "Not Set"
    grp_link = "Set" if group_data.get('group_link') else "Not Set"

    text = (
        f"🔗 **Other URL & Button Settings for:** `{chat_id}`\n\n"
        "Configure miscellaneous links and buttons used by the bot.\n\n"
        "[Caption URL Demo](https://graph.org/file/4d61886e61dfa37a25945.jpg) | "
        "[Caption Button Demo](https://graph.org/file/4d61886e61dfa37a25945.jpg) | "
        "[How-To URL Demo](https://graph.org/file/4d61886e61dfa37a25945.jpg) | "
        "[Group Link Demo](https://graph.org/file/4d61886e61dfa37a25945.jpg)"
    )
    
    buttons = [
        [InlineKeyboardButton(f"Caption URL ({cap_url})", callback_data=f"set_cap_url#{chat_id}")],
        [InlineKeyboardButton(f"Caption Button ({cap_btn})", callback_data=f"cap_btn_ui#{chat_id}")],
        [InlineKeyboardButton(f"How To Download Button ({howto})", callback_data=f"set_howto#{chat_id}")],
        [InlineKeyboardButton(f"Group Link ({grp_link})", callback_data=f"set_grp_link#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

@Client.on_callback_query(filters.regex(r"^set_cap_url#"))
async def set_caption_url_handler(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    current = group_data.get('caption_url')
    
    status_text = f"\n\n**Current URL:**\n`{current}`" if current else ""
    
    text = (
        "Please send the URL to be used for the file name hyperlink.\n"
        f"{status_text}\n\n"
        "Send `remove` to delete the current URL."
    )
    
    cancel_btn = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"other_urls_ui#{chat_id}")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(cancel_btn))
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text:
            if msg.text.lower() == "remove":
                await db.update_group_settings(chat_id, {'caption_url': None})
                await msg.reply("🗑️ **Caption URL has been removed.**")
            elif "http" in msg.text:
                await db.update_group_settings(chat_id, {'caption_url': msg.text.strip()})
                await msg.reply("✅ **Caption URL has been set.**")
            else:
                await msg.reply("❌ Invalid URL. Must start with http/https.")
            
            await asyncio.sleep(1)
            await other_urls_ui(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^cap_btn_ui#"))
async def caption_btn_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    curr_text = group_data.get('caption_btn_text')
    curr_url = group_data.get('caption_btn_url')
    
    if curr_text and curr_url:
        status_info = (
            f"**Current Text:**\n{curr_text}\n\n"
            f"**Current URL:**\n{curr_url}"
        )
    else:
        status_info = "**Status:** Not configured."

    text = (
        f"✨ **Caption Button Settings for:** `{chat_id}`\n\n"
        "This button will appear below all files sent to users.\n\n"
        f"{status_info}"
    )
    
    buttons = [
        [InlineKeyboardButton("Set Text", callback_data=f"set_cb_txt#{chat_id}"),
         InlineKeyboardButton("Set URL", callback_data=f"set_cb_url#{chat_id}")],
         
        [InlineKeyboardButton("Reset Button", callback_data=f"reset_cb#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Other URLs", callback_data=f"other_urls_ui#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

@Client.on_callback_query(filters.regex(r"^set_cb_txt#"))
async def set_cap_btn_text(client, query):
    chat_id = int(query.data.split("#")[1])
    cancel_btn = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"cap_btn_ui#{chat_id}")]]
    
    await query.message.edit_text("Please send the **text** for your custom button.", reply_markup=InlineKeyboardMarkup(cancel_btn))
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text:
            await db.update_group_settings(chat_id, {'caption_btn_text': msg.text})
            await msg.reply("✅ **Custom button text has been updated.**")
            await asyncio.sleep(1)
            await caption_btn_ui(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^set_cb_url#"))
async def set_cap_btn_url(client, query):
    chat_id = int(query.data.split("#")[1])
    cancel_btn = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"cap_btn_ui#{chat_id}")]]
    
    await query.message.edit_text("Please send the **full URL** (starting with http:// or https://) for your custom button.", reply_markup=InlineKeyboardMarkup(cancel_btn))
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text and "http" in msg.text:
            await db.update_group_settings(chat_id, {'caption_btn_url': msg.text.strip()})
            await msg.reply("✅ **Custom button URL has been updated.**")
            await asyncio.sleep(1)
            await caption_btn_ui(client, query)
        else:
            await msg.reply("❌ Invalid URL.")
            await caption_btn_ui(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^reset_cb#"))
async def reset_caption_btn(client, query):
    chat_id = int(query.data.split("#")[1])
    await db.update_group_settings(chat_id, {'caption_btn_text': None, 'caption_btn_url': None})
    await query.answer("Button Reset!", show_alert=True)
    await caption_btn_ui(client, query)

@Client.on_callback_query(filters.regex(r"^set_howto#"))
async def set_howto_url_handler(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    current = group_data.get('howto_url')
    
    status_text = f"\n\n**Current URL:**\n{current}" if current else ""
    
    text = (
        "Please send the new URL for the 'How to Download' button.\n"
        f"{status_text}\n\n"
        "Send `remove` to delete the current URL."
    )
    
    cancel_btn = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"other_urls_ui#{chat_id}")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(cancel_btn), disable_web_page_preview=True)
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text:
            if msg.text.lower() == "remove":
                await db.update_group_settings(chat_id, {'howto_url': None})
                await msg.reply("🗑️ **How-To URL has been removed.**")
            elif "http" in msg.text:
                await db.update_group_settings(chat_id, {'howto_url': msg.text.strip()})
                await msg.reply("✅ **How-To URL has been set.**")
            else:
                await msg.reply("❌ Invalid URL.")
            
            await asyncio.sleep(1)
            await other_urls_ui(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^set_grp_link#"))
async def set_group_link_handler(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    current = group_data.get('group_link')
    
    status_text = f"\n\n**Current Link:**\n{current}" if current else ""
    
    text = (
        "Please send the invite link for your group.\n"
        "This will be used for the 'Go Back' button on sent files.\n"
        f"{status_text}\n\n"
        "Send `remove` to delete the current link."
    )
    
    cancel_btn = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"other_urls_ui#{chat_id}")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(cancel_btn), disable_web_page_preview=True)
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if msg.text:
            if msg.text.lower() == "remove":
                await db.update_group_settings(chat_id, {'group_link': None})
                await msg.reply("🗑️ **Group link has been removed.**")
            elif "t.me" in msg.text or "http" in msg.text:
                await db.update_group_settings(chat_id, {'group_link': msg.text.strip()})
                await msg.reply("✅ **Group link has been set.**")
            else:
                await msg.reply("❌ Invalid Link.")
            
            await asyncio.sleep(1)
            await other_urls_ui(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^ref_sys_menu#"))
async def referral_settings_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    is_enabled = group_data.get('referral_enabled', True)
    target = group_data.get('referral_target', 5)
    reward_sec = group_data.get('referral_reward_time', 2592000)
    
    reward_days = int(reward_sec / 86400)
    
    status_icon = "✅ Enabled" if is_enabled else "❌ Disabled"
    btn_text = "🔴 Disable" if is_enabled else "🟢 Enable"
    toggle_val = "off" if is_enabled else "on"
    
    text = (
        f"🤝 **Referral System Settings for:** `{chat_id}`\n\n"
        "This system helps grow your group. When a user refers new members via their unique link, "
        "they will receive a premium subscription (no shorteners).\n\n"
        f"**Status:** {status_icon}\n"
        f"**Reward:** {reward_days} days of premium access for {target} referrals."
    )
    
    buttons = [
        [InlineKeyboardButton(btn_text, callback_data=f"ref_toggle#{chat_id}#{toggle_val}")],
        [InlineKeyboardButton("Set Claim Points", callback_data=f"ref_set_points#{chat_id}"),
         InlineKeyboardButton("Set Access Time", callback_data=f"ref_set_time#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Main Settings", callback_data=f"set_main#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^ref_toggle#"))
async def referral_toggle(client, query):
    _, chat_id, action = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'referral_enabled': (action == "on")})
    await referral_settings_menu(client, query)

@Client.on_callback_query(filters.regex(r"^ref_set_points#"))
async def referral_set_points_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    current = group_data.get('referral_target', 5)
    
    def chk(val): return " ✅" if val == current else ""
    
    text = f"🔢 **Set Referral Target**\nCurrent: {current} referrals needed to claim."
    
    buttons = [
        [InlineKeyboardButton(f"3{chk(3)}", callback_data=f"ref_save_pts#{chat_id}#3"),
         InlineKeyboardButton(f"5{chk(5)}", callback_data=f"ref_save_pts#{chat_id}#5"),
         InlineKeyboardButton(f"10{chk(10)}", callback_data=f"ref_save_pts#{chat_id}#10"),
         InlineKeyboardButton(f"20{chk(20)}", callback_data=f"ref_save_pts#{chat_id}#20")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"ref_sys_menu#{chat_id}")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^ref_save_pts#"))
async def save_ref_points(client, query):
    _, chat_id, val = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'referral_target': int(val)})
    await referral_set_points_ui(client, query)

@Client.on_callback_query(filters.regex(r"^ref_set_time#"))
async def referral_set_time_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    current_sec = group_data.get('referral_reward_time', 2592000)
    current_days = int(current_sec / 86400)
    
    def chk(val): return " ✅" if val == current_days else ""
    
    text = f"⏳ **Set Reward Duration**\nCurrent: {current_days} Days of Premium."
    
    buttons = [
        [InlineKeyboardButton(f"1 D{chk(1)}", callback_data=f"ref_save_time#{chat_id}#{1*86400}"),
         InlineKeyboardButton(f"7 D{chk(7)}", callback_data=f"ref_save_time#{chat_id}#{7*86400}"),
         InlineKeyboardButton(f"10 D{chk(10)}", callback_data=f"ref_save_time#{chat_id}#{10*86400}")],
        [InlineKeyboardButton(f"15 D{chk(15)}", callback_data=f"ref_save_time#{chat_id}#{15*86400}"),
         InlineKeyboardButton(f"20 D{chk(20)}", callback_data=f"ref_save_time#{chat_id}#{20*86400}"),
         InlineKeyboardButton(f"1 M{chk(30)}", callback_data=f"ref_save_time#{chat_id}#{30*86400}")],
        [InlineKeyboardButton(f"2 M{chk(60)}", callback_data=f"ref_save_time#{chat_id}#{60*86400}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"ref_sys_menu#{chat_id}")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^ref_save_time#"))
async def save_ref_time(client, query):
    _, chat_id, val = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'referral_reward_time': int(val)})
    await referral_set_time_ui(client, query)

@Client.on_callback_query(filters.regex(r"^req_feature#"))
async def request_feature_ui(client, query):
    chat_id = int(query.data.split("#")[1])
    
    text = (
        "💡 **Request a New Feature**\n\n"
        "Please describe the feature you'd like to see added to the bot. "
        "Your message will be sent directly to the bot owner."
    )
    
    buttons = [[InlineKeyboardButton("🔙 Cancel", callback_data=f"set_main#{chat_id}")]]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    
    try:
        msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        
        admin_text = f"💡 **New Feature Request!**\n\n👤 From: {msg.from_user.mention} (`{msg.from_user.id}`)\n📂 Group ID: `{chat_id}`\n\n**Request:**"
        
        for admin_id in ADMINS:
            try:
                await client.send_message(admin_id, admin_text)
                if msg.text:
                    await client.send_message(admin_id, msg.text)
                elif msg.photo or msg.video or msg.document:
                    await msg.copy(admin_id, caption=msg.caption or "")
            except: pass
            
        await msg.reply("✅ **Request Sent!** Thank you for your feedback.")
        await asyncio.sleep(1)
        await main_settings_menu(client, query)
        
    except Exception as e:
        pass 

@Client.on_callback_query(filters.regex(r"^set_back_home"))
async def back_to_group_list(client, query):
    user_id = query.from_user.id
    user_groups = []
    seen_chats = set()
    
    db_query = {"admins": user_id}
    
    async for group in db.groups.find(db_query):
        chat_id = group.get('id')
        
        if chat_id in seen_chats:
            continue
            
        title = group.get('title')
        
        if not title or str(title) == str(chat_id):
            continue 
            
        user_groups.append((title, chat_id))
        seen_chats.add(chat_id)

    if not user_groups:
        return await query.message.edit_text("❌ **No Groups Found!**\nKripya apne group me ja kar ek baar `/connect` type karein.")

    buttons = []
    for title, chat_id in user_groups:
        buttons.append([InlineKeyboardButton(f"📂 {title}", callback_data=f"set_main#{chat_id}")])
    
    await query.message.edit_text("⚙️ **Select your Group:**", reply_markup=InlineKeyboardMarkup(buttons))
