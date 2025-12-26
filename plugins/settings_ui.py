import asyncio
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
import info

# --- HELPER: Time Convertor ---
def seconds_to_str(seconds):
    if seconds == 0: return "0s"
    if seconds < 60: return f"{seconds}s"
    if seconds < 3600: return f"{int(seconds/60)}min"
    if seconds < 86400: return f"{int(seconds/3600)}hr"
    return f"{int(seconds/86400)}days"

# --- HELPER: CHECK SHORTENER ---
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

# --- /settings COMMAND ---
@Client.on_message(filters.command("settings") & filters.private)
async def settings_command(client, message):
    user_id = message.from_user.id
    msg = await message.reply_text("🔄 **Loading your groups...**")
    
    user_groups = []
    async for group in db.groups.find({}):
        chat_id = group['id']
        saved_title = group.get('title', f"Group {chat_id}") 
        try:
            member = await client.get_chat_member(chat_id, user_id)
            if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
                user_groups.append((saved_title, chat_id))
        except:
            user_groups.append((f"{saved_title} (Cached)", chat_id))

    await msg.delete()
    if not user_groups:
        return await message.reply_text("❌ **No Connected Groups Found!**")

    buttons = []
    for title, chat_id in user_groups:
        buttons.append([InlineKeyboardButton(f"📂 {title}", callback_data=f"set_main#{chat_id}")])
    
    await message.reply_text("⚙️ **Select a Group:**", reply_markup=InlineKeyboardMarkup(buttons))

# --- MAIN MENU ---
@Client.on_callback_query(filters.regex(r"^set_main#"))
async def main_settings_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    try: 
        chat = await client.get_chat(chat_id)
        title = chat.title
    except: 
        group_data = await db.get_group_settings(chat_id)
        title = group_data.get('title', "Unknown Group")

    buttons = [
        [InlineKeyboardButton("💰 Earning Method", callback_data=f"set_earn#{chat_id}"),
         InlineKeyboardButton("🔒 Force Subscribe", callback_data=f"fsub_menu#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Groups", callback_data="set_back_home")]
    ]
    await query.message.edit_text(f"⚙️ **Settings for:** {title}", reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🔥 ADVANCED FSUB MENU (Repo 2 Style Layout)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^fsub_menu#"))
async def fsub_configure_menu(client, query):
    try:
        chat_id = int(query.data.split("#")[1])
        group_data = await db.get_group_settings(chat_id)
        
        if not group_data:
            await db.add_group(chat_id, "Unknown")
            group_data = await db.get_group_settings(chat_id)
            
        raw_fsub = group_data.get('fsub_channels')
        if isinstance(raw_fsub, list): fsub_channels = {} 
        elif isinstance(raw_fsub, dict): fsub_channels = raw_fsub
        else: fsub_channels = {}

        # Slots Read
        s1 = fsub_channels.get('1')
        s2 = fsub_channels.get('2')
        s3 = fsub_channels.get('3')
        s4 = fsub_channels.get('4')

        # Status Text (Sajawat Repo 2 Jaisi)
        txt = f"⚙️ **Advanced Force Subscribe**\n\n"
        txt += f"1️⃣ **Slot 1 (Request):** `{s1 if s1 else '❌ Not Set'}`\n"
        txt += f"2️⃣ **Slot 2 (Request):** `{s2 if s2 else '❌ Not Set'}`\n"
        txt += f"3️⃣ **Slot 3 (Normal):** `{s3 if s3 else '❌ Not Set'}`\n"
        txt += f"➖➖➖➖➖➖➖➖➖➖\n"
        txt += f"4️⃣ **Slot 4 (Post-Verify):** `{s4 if s4 else '❌ Not Set'}`\n\n"
        txt += "👇 **Click below to change:**"

        buttons = []
        
        # Row 1: Slot 1 & 2 (Ek Saath)
        btn1 = []
        btn1.append(InlineKeyboardButton(f"{'✏️' if s1 else '➕'} Set 1", callback_data=f"set_fsub#{chat_id}#1"))
        btn1.append(InlineKeyboardButton(f"{'✏️' if s2 else '➕'} Set 2", callback_data=f"set_fsub#{chat_id}#2"))
        buttons.append(btn1)

        # Row 2: Slot 3 (Normal) - Iske saath hi
        buttons.append([InlineKeyboardButton(f"{'✏️' if s3 else '➕'} Set Slot 3 (Normal)", callback_data=f"set_fsub#{chat_id}#3")])

        # Row 3: Slot 4 (Post Verification - Alag se highlighted)
        buttons.append([InlineKeyboardButton(f"{'✏️' if s4 else '➕'} Set Post-Verify (Slot 4)", callback_data=f"set_fsub#{chat_id}#4")])

        # Clear Buttons (Agar koi set hai to hi dikhega)
        if s1 or s2 or s3 or s4:
            buttons.append([InlineKeyboardButton("🗑️ Remove All Slots", callback_data=f"rem_fsub_all#{chat_id}")])

        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"set_main#{chat_id}")])
        
        await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)

# 2. SET SLOT INPUT (Interactive Listen Enabled)
@Client.on_callback_query(filters.regex(r"^set_fsub#"))
async def set_fsub_input(client, query):
    _, chat_id, slot = query.data.split("#")
    chat_id = int(chat_id)
    user_id = query.from_user.id
    
    slot_name = "Normal" if slot == "3" else "Post-Verify" if slot == "4" else "Request"
    
    await query.message.edit_text(
        f"🆔 **Set Slot {slot} ({slot_name})**\n\n"
        "**Target Channel se koi bhi message Forward karein**\n"
        "YA Channel ID/Username bhejein.\n\n"
        "⚠️ **Dhyan dein:** Bot wahan Admin hona chahiye!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Cancel", callback_data=f"fsub_menu#{chat_id}")]])
    )
    
    try:
        # Listening for input (Repo 2 Style)
        msg = await client.listen(user_id, timeout=60)
    except asyncio.TimeoutError:
        await query.message.edit_text("❌ **Timeout!** Too slow.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"fsub_menu#{chat_id}")]]))
        return

    if msg.text or msg.forward_from_chat:
        try:
            if msg.forward_from_chat:
                target_chat = msg.forward_from_chat
            else:
                target_chat = await client.get_chat(msg.text)
            
            # Save to Database
            group_data = await db.get_group_settings(chat_id)
            fsub_channels = group_data.get('fsub_channels', {})
            if not isinstance(fsub_channels, dict): fsub_channels = {}
            
            fsub_channels[str(slot)] = int(target_chat.id)
            await db.update_group_settings(chat_id, {'fsub_channels': fsub_channels})
            
            await msg.reply(f"✅ **Saved!**\nSlot {slot}: {target_chat.title}")
            
            # Wapas Menu par le jao
            await fsub_configure_menu(client, query) 

        except Exception as e:
            await msg.reply(f"❌ **Error:** Invalid Channel.\nMake sure bot is admin there.\n`{e}`")
            await fsub_configure_menu(client, query) 
    else:
        await msg.reply("❌ Invalid input.")
        await fsub_configure_menu(client, query) 

# 3. REMOVE ALL SLOTS
@Client.on_callback_query(filters.regex(r"^rem_fsub_all#"))
async def remove_fsub_all(client, query):
    chat_id = int(query.data.split("#")[1])
    await db.update_group_settings(chat_id, {'fsub_channels': {}})
    await query.answer("All Fsub Channels Removed!", show_alert=True)
    await fsub_configure_menu(client, query)

# ==============================================================================
# 💰 EARNING & SHORTENER SETTINGS
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^set_earn#"))
async def earning_settings(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    if not group_data: 
        await db.add_group(chat_id, "Unknown Group")
        group_data = await db.get_group_settings(chat_id)
    
    active_mode = "SHORTLINK" if group_data.get('is_shortlink_active', True) else "FSUB (Disable Shortlink)"
    buttons = [
        [InlineKeyboardButton("🔗 Shortlink Mode", callback_data=f"set_smode#{chat_id}")],
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
    names = {'time_dynamic': "Dynamic Full Access", 'time_gap1': "Smart Gap 1", 'time_gap2': "Smart Gap 2", 'time_smart': "Smart Full Access", 'time_together': "Together Base Access", 'time_together_3': "Together 3-Link"}
    name = names.get(key, "Time")
    text = f"⏱ **Set Time for {name}**\n\nChoose duration:"
    
    if "gap" in key:
        buttons = [[InlineKeyboardButton("5 Mins", callback_data=f"save_time#{chat_id}#{key}#{300}"), InlineKeyboardButton("15 Mins", callback_data=f"save_time#{chat_id}#{key}#{900}")], [InlineKeyboardButton("1 Hour", callback_data=f"save_time#{chat_id}#{key}#{3600}")]]
    else:
        buttons = [[InlineKeyboardButton("12 Hours", callback_data=f"save_time#{chat_id}#{key}#{43200}"), InlineKeyboardButton("24 Hours", callback_data=f"save_time#{chat_id}#{key}#{86400}")], [InlineKeyboardButton("3 Days", callback_data=f"save_time#{chat_id}#{key}#{259200}"), InlineKeyboardButton("7 Days", callback_data=f"save_time#{chat_id}#{key}#{604800}")]]
    
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
    shorteners = group_data.get('shorteners', {})
    
    status_text = ""
    for i in range(1, 4):
        s = shorteners.get(str(i))
        status_text += f"✅ Shortener {i}: {s['site']}\n" if s else f"❌ Shortener {i}: Not Set\n"

    text = f"🛠️ **Shortener Setup for:** `{chat_id}`\n\n{status_text}"
    buttons = []
    for i in range(1, 4):
        s = shorteners.get(str(i))
        if s: buttons.append([InlineKeyboardButton(f"✏️ Edit Slot {i}", callback_data=f"edit_slot#{chat_id}#{i}"), InlineKeyboardButton(f"🗑️ Reset", callback_data=f"del_slot#{chat_id}#{i}")])
        else: buttons.append([InlineKeyboardButton(f"➕ Set Slot {i}", callback_data=f"add_slot#{chat_id}#{i}")])

    buttons.append([InlineKeyboardButton("🧪 Test Connections", callback_data=f"test_sl#{chat_id}")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"set_smode#{chat_id}")])
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^add_slot#") | filters.regex(r"^edit_slot#"))
async def input_slot_req(client, query):
    _, chat_id, slot = query.data.split("#")
    # Redirect to interactive input
    await set_fsub_input(client, query)
    return

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
    
    await query.message.edit_text("🧪 **Testing connections...**")
    results = []
    for i in range(1, 4):
        s = shorteners.get(str(i))
        if s:
            if await check_shortener_link(s['site'], s['api']): results.append(f"Slot {i}: ✅ Success")
            else: results.append(f"Slot {i}: ❌ Failed")
    
    text = "\n".join(results) if results else "No shorteners set."
    await query.message.edit_text(f"📊 **Results:**\n{text}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=f"set_slots#{chat_id}")]]))

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

@Client.on_callback_query(filters.regex(r"^set_back_home"))
async def back_home(client, query):
    await settings_command(client, query.message)
