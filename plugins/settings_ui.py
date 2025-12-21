import asyncio
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.users_chats_db import db
from utils import temp
import info

# --- HELPER: Time Convertor ---
def seconds_to_str(seconds):
    if seconds == 0: return "0s"
    if seconds < 60: return f"{seconds}s"
    if seconds < 3600: return f"{int(seconds/60)}min"
    if seconds < 86400: return f"{int(seconds/3600)}hr"
    return f"{int(seconds/86400)}days"

# --- HELPER: Check Shortener Connection ---
async def check_shortener_link(domain, api):
    test_url = "https://google.com"
    # Standard AdLinkFly API format
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

# --- /settings COMMAND (PM ONLY) ---
@Client.on_message(filters.command("settings") & filters.private)
async def settings_command(client, message):
    user_id = message.from_user.id
    msg = await message.reply_text("🔄 **Loading your groups...**")
    
    user_groups = []
    async for group in db.groups.find({}):
        try:
            chat_id = group['id']
            try:
                member = await client.get_chat_member(chat_id, user_id)
            except: continue 
            if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
                chat_info = await client.get_chat(chat_id)
                user_groups.append((chat_info.title, chat_id))
        except: continue 

    await msg.delete()
    if not user_groups:
        return await message.reply_text("❌ **No Groups Found!**\nMake sure I am added to your group and you are an Admin there.")

    buttons = []
    for title, chat_id in user_groups:
        buttons.append([InlineKeyboardButton(f"📂 {title}", callback_data=f"set_main#{chat_id}")])
    
    await message.reply_text("⚙️ **Select a Group:**", reply_markup=InlineKeyboardMarkup(buttons))

# --- MAIN MENUS ---
@Client.on_callback_query(filters.regex(r"^set_main#"))
async def main_settings_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    buttons = [
        [InlineKeyboardButton("💰 Earning Method", callback_data=f"set_earn#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Groups", callback_data="set_back_home")]
    ]
    try: title = (await client.get_chat(chat_id)).title
    except: title = "Unknown"
    await query.message.edit_text(f"⚙️ **Settings for:** {title}", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^set_earn#"))
async def earning_settings(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    if not group_data:
        await db.add_group(chat_id)
        group_data = await db.get_group_settings(chat_id)

    active_mode = "SHORTLINK" if group_data.get('is_shortlink_active', True) else "FSUB (Disable Shortlink)"
    
    buttons = [
        [InlineKeyboardButton("🔗 Shortlink Mode", callback_data=f"set_smode#{chat_id}")],
        [InlineKeyboardButton("🚫 Disable Shortlink", callback_data=f"set_disable#{chat_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"set_main#{chat_id}")]
    ]
    await query.message.edit_text(f"💰 **Earning Settings**\nActive Mode: `{active_mode}`", reply_markup=InlineKeyboardMarkup(buttons))

# --- 🧠 CORE: SHORTLINK CONFIGURATION UI ---
@Client.on_callback_query(filters.regex(r"^set_smode#"))
async def shortlink_config(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    mode = group_data.get('shortener_mode', 'dynamic').lower()
    
    # Fetch Times from DB (Defaults handled here)
    t_dynamic = group_data.get('time_dynamic', 86400)
    t_smart_gap1 = group_data.get('time_gap1', 300)
    t_smart_gap2 = group_data.get('time_gap2', 300)
    t_smart_full = group_data.get('time_smart', 86400)
    
    # Together Mode Times
    t_together_base = group_data.get('time_together', 604800) # Default 7 Days (for 1 or 2 links)
    t_together_3 = group_data.get('time_together_3', 86400)   # Default 24 Hours (for 3 links)
    
    # Checkmarks
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
    
    # --- DYNAMIC UI ---
    if mode == 'dynamic':
        desc = f"**Dynamic Mode:** Checks slots 1->2->3.\n⏱ Full Access: `{seconds_to_str(t_dynamic)}`"
        custom_btns.append([InlineKeyboardButton("⏰ Set Access Time", callback_data=f"time_ui#{chat_id}#time_dynamic")])

    # --- TOGETHER UI (UPDATED) ---
    elif mode == 'together':
        desc = (f"**Together Mode Logic:**\n"
                f"• 1 Link Verified: `{seconds_to_str(t_together_base)}` Access\n"
                f"• 2 Links Verified: Link 1 (1hr) -> Link 2 (`{seconds_to_str(t_together_base)}`)\n"
                f"• 3 Links Verified: Link 1 (1hr) -> Link 2 (6hr) -> Link 3 (`{seconds_to_str(t_together_3)}`)")
        
        custom_btns.append([InlineKeyboardButton("⏰ Set Base Time (1 or 2 Links)", callback_data=f"time_ui#{chat_id}#time_together")])
        custom_btns.append([InlineKeyboardButton("⏰ Set 3-Link Final Time", callback_data=f"time_ui#{chat_id}#time_together_3")])

    # --- SMART UI ---
    elif mode == 'smart':
        desc = (f"**Smart Mode:** Waterfall Logic.\n"
                f"• Gap 1: `{seconds_to_str(t_smart_gap1)}`\n"
                f"• Gap 2: `{seconds_to_str(t_smart_gap2)}`\n"
                f"• Full Access: `{seconds_to_str(t_smart_full)}`")
        custom_btns.append([InlineKeyboardButton("⏳ Set Gap 1", callback_data=f"time_ui#{chat_id}#time_gap1"),
                            InlineKeyboardButton("⏳ Set Gap 2", callback_data=f"time_ui#{chat_id}#time_gap2")])
        custom_btns.append([InlineKeyboardButton("⏰ Set Full Access", callback_data=f"time_ui#{chat_id}#time_smart")])

    footer_btns = [
        [InlineKeyboardButton("⚙️ Configure Shorteners", callback_data=f"set_slots#{chat_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"set_earn#{chat_id}")]
    ]

    await query.message.edit_text(
        f"🔗 **Shortener Mode Config**\n\n{desc}",
        reply_markup=InlineKeyboardMarkup([mode_btns] + custom_btns + footer_btns)
    )

@Client.on_callback_query(filters.regex(r"^set_type#"))
async def set_mode_handler(client, query):
    _, chat_id, mode = query.data.split("#")
    await db.update_group_settings(chat_id, {'shortener_mode': mode})
    await shortlink_config(client, query)

# --- ⏰ TIME PICKER UI ---
@Client.on_callback_query(filters.regex(r"^time_ui#"))
async def time_picker_ui(client, query):
    _, chat_id, key = query.data.split("#")
    
    names = {
        'time_dynamic': "Dynamic Full Access",
        'time_gap1': "Smart Gap 1",
        'time_gap2': "Smart Gap 2",
        'time_smart': "Smart Full Access",
        'time_together': "Together Base Access (1-2 Links)",
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
    await db.update_group_settings(chat_id, {key: int(seconds)})
    await query.answer("✅ Time Updated!", show_alert=True)
    await shortlink_config(client, query)

# --- 7. CONFIGURE SHORTENERS (STATUS DASHBOARD) ---
@Client.on_callback_query(filters.regex(r"^set_slots#"))
async def configure_slots(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    shorteners = group_data.get('shorteners', {})
    
    current_mode = group_data.get('shortener_mode', 'dynamic').capitalize()
    interval = group_data.get('time_dynamic', 86400) if current_mode == 'Dynamic' else group_data.get('time_smart', 86400)
    interval_hours = int(interval / 3600)

    status_text = ""
    for i in range(1, 4):
        s_data = shorteners.get(str(i))
        status_text += f"✅ Shortener {i}: {s_data['site']}\n" if s_data else f"❌ Shortener {i}: Not Set\n"

    text = (
        f"🛠️ **Configuring {current_mode} Type for:** `{chat_id}`\n\n"
        f"**Verification Interval:** {interval_hours} hours\n\n"
        f"**Your Setup:**\n{status_text}"
    )
    
    buttons = []
    for i in range(1, 4):
        if shorteners.get(str(i)):
            buttons.append([
                InlineKeyboardButton(f"✏️ Edit Shortener {i}", callback_data=f"edit_slot#{chat_id}#{i}"),
                InlineKeyboardButton(f"🗑️ Reset Slot {i}", callback_data=f"del_slot#{chat_id}#{i}")
            ])
        else:
            buttons.append([InlineKeyboardButton(f"➕ Set Shortener {i}", callback_data=f"add_slot#{chat_id}#{i}")])

    help_text_btn = f"How {current_mode} mode works"
    footer_btns = [
        [InlineKeyboardButton("🧪 Test connected Shorteners", callback_data=f"test_sl#{chat_id}")],
        [InlineKeyboardButton("📘 How to connect shortener", url="https://t.me/YourChannel")],
        [InlineKeyboardButton(f"ℹ️ {help_text_btn}", url="https://t.me/YourChannel")],
        [InlineKeyboardButton("🔙 Back to shortener settings", callback_data=f"set_smode#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons + footer_btns))

# --- 8. STEP-BY-STEP ADD/EDIT SLOT HANDLER ---
@Client.on_callback_query(filters.regex(r"^add_slot#") | filters.regex(r"^edit_slot#"))
async def input_slot_req(client, query):
    _, chat_id, slot = query.data.split("#")
    chat_id = int(chat_id)
    cancel_btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"set_slots#{chat_id}")]]

    # Step 1: Ask Domain
    await query.message.edit_text(
        f"Please send the **Domain** for **Shortener {slot}**.\n\n(e.g., `earn4link.in`)",
        reply_markup=InlineKeyboardMarkup(cancel_btn)
    )
    
    try:
        domain_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if not domain_msg.text: return await query.message.edit_text("❌ Input must be text.", reply_markup=InlineKeyboardMarkup(cancel_btn))
        domain = domain_msg.text.strip()
        await domain_msg.delete()
    except: return await query.message.edit_text("❌ Timeout!", reply_markup=InlineKeyboardMarkup(cancel_btn))

    # Step 2: Ask API
    await query.message.edit_text(
        f"✅ **Domain for slot {slot} has been updated.**\nNow, please send the **API Key**.",
        reply_markup=InlineKeyboardMarkup(cancel_btn)
    )

    try:
        api_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if not api_msg.text: return await query.message.edit_text("❌ Text only!", reply_markup=InlineKeyboardMarkup(cancel_btn))
        api = api_msg.text.strip()
        await api_msg.delete()
    except: return await query.message.edit_text("❌ Timeout!", reply_markup=InlineKeyboardMarkup(cancel_btn))

    # Step 3: Save & Return
    await db.add_shortener(chat_id, slot, domain, api)
    await query.message.edit_text(f"✅ **Api for slot {slot} has been updated.**")
    await asyncio.sleep(1.5)
    query.data = f"set_slots#{chat_id}"
    await configure_slots(client, query)

@Client.on_callback_query(filters.regex(r"^del_slot#"))
async def delete_slot(client, query):
    _, chat_id, slot = query.data.split("#")
    await db.remove_shortener(chat_id, slot)
    await query.answer(f"🗑️ Slot {slot} Cleared!", show_alert=True)
    await configure_slots(client, query)

# --- 9. TEST CONNECTED SHORTENERS ---
@Client.on_callback_query(filters.regex(r"^test_sl#"))
async def test_shorteners(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    shorteners = group_data.get('shorteners', {})

    if not shorteners: return await query.answer("⚠️ No shorteners connected!", show_alert=True)
    await query.message.edit_text("🧪 **Testing connections...**")

    results = []
    all_success = True
    for i in range(1, 4):
        s_data = shorteners.get(str(i))
        if s_data:
            domain, api = s_data['site'], s_data['api']
            is_working = await check_shortener_link(domain, api)
            if is_working: results.append(f" - {domain}: ✅ Success")
            else:
                results.append(f" - {domain}: ❌ Failed")
                all_success = False

    back_btn = [[InlineKeyboardButton("🔙 Back", callback_data=f"set_slots#{chat_id}")]]
    if all_success:
        await query.message.edit_text("🎉 **Congratulations!**\n\nAll shorteners are working perfectly.", reply_markup=InlineKeyboardMarkup(back_btn))
    else:
        fail_btns = [[InlineKeyboardButton("📘 How to connect", url="https://t.me/YourChannel")], back_btn[0]]
        await query.message.edit_text(f"📊 **Test Results:**\n\n" + "\n".join(results) + "\n\nOne or more failed.", reply_markup=InlineKeyboardMarkup(fail_btns))

# --- BACK HOME ---
@Client.on_callback_query(filters.regex(r"^set_back_home"))
async def back_home(client, query):
    await settings_command(client, query.message)

# --- DISABLE SHORTLINK (FSUB MENU) ---
@Client.on_callback_query(filters.regex(r"^set_disable#"))
async def disable_shortlink_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    is_active = not group_data.get('is_shortlink_active', True)
    status_icon = "✅ ACTIVE" if is_active else "❌ INACTIVE"
    
    try: count = await client.get_chat_members_count(chat_id)
    except: count = 0
    
    fsub_list = group_data.get('fsub_channels', [])
    req_mem = count >= 100
    req_fsub = len(fsub_list) > 0

    text = (
        f"🚫 **Disable Shortlink for:** `{chat_id}`\n\n**Status:** {status_icon}\n\n"
        f"**Requirements:**\n"
        f"{'✅' if req_fsub else '❌'} 1. Configure Fsub.\n"
        f"{'✅' if req_mem else '❌'} 2. 100+ Members (Cur: {count})."
    )
    
    cb_data = f"act_toggle#{chat_id}#off" if not is_active else f"act_toggle#{chat_id}#on"
    if not is_active and (not req_mem or not req_fsub): cb_data = "alert_req"

    buttons = [
        [InlineKeyboardButton("🔴 Disable" if not is_active else "🟢 Enable", callback_data=cb_data)],
        [InlineKeyboardButton("🔙 Back", callback_data=f"set_earn#{chat_id}")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^act_toggle#"))
async def toggle_activation(client, query):
    _, chat_id, action = query.data.split("#")
    chat_id = int(chat_id)
    await db.update_group_settings(chat_id, {'is_shortlink_active': (action == "on")})
    await query.answer(f"✅ Shortlink Mode {'Activated' if action == 'on' else 'Deactivated'}!", show_alert=True)
    await earning_settings(client, query)

@Client.on_callback_query(filters.regex(r"^alert_req"))
async def alert_requirements(client, query):
    await query.answer("❌ Requirements not met!", show_alert=True)
