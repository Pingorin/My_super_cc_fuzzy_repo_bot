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
    
    # Get Current Mode (Default: dynamic)
    mode = group_data.get('shortener_mode', 'dynamic').lower()
    
    # Get Stored Times (Defaults)
    t_dynamic = group_data.get('time_dynamic', 86400) # 24h
    t_smart_gap1 = group_data.get('time_gap1', 300)   # 5m
    t_smart_gap2 = group_data.get('time_gap2', 300)   # 5m
    t_smart_full = group_data.get('time_smart', 86400)# 24h
    t_together_final = group_data.get('time_together', 43200) # 12h (Default)
    
    # Mode Buttons (Add ✅)
    d_tick = "✅ " if mode == 'dynamic' else ""
    t_tick = "✅ " if mode == 'together' else ""
    s_tick = "✅ " if mode == 'smart' else ""
    
    mode_btns = [
        InlineKeyboardButton(f"{d_tick}Dynamic", callback_data=f"set_type#{chat_id}#dynamic"),
        InlineKeyboardButton(f"{t_tick}Together", callback_data=f"set_type#{chat_id}#together"),
        InlineKeyboardButton(f"{s_tick}Smart", callback_data=f"set_type#{chat_id}#smart")
    ]

    # --- DYNAMIC CUSTOMIZATION ---
    custom_btns = []
    desc = ""
    
    if mode == 'dynamic':
        desc = f"**Dynamic Mode:** Checks slots 1->2->3.\n⏱ Full Access: `{seconds_to_str(t_dynamic)}`"
        custom_btns.append([InlineKeyboardButton("⏰ Set Access Time", callback_data=f"time_ui#{chat_id}#time_dynamic")])

    # --- TOGETHER CUSTOMIZATION ---
    elif mode == 'together':
        desc = (f"**Together Mode:**\n"
                f"• 1 Link: `{seconds_to_str(t_together_final)}` Access\n"
                f"• 2 Links: Link 1 (1hr) -> Link 2 ({seconds_to_str(t_together_final)})\n"
                f"• 3 Links: Link 1 (1hr) -> Link 2 (6hr) -> Link 3 (24hr)")
        custom_btns.append([InlineKeyboardButton("⚙️ Customize Base Time", callback_data=f"time_ui#{chat_id}#time_together")])

    # --- SMART CUSTOMIZATION ---
    elif mode == 'smart':
        desc = (f"**Smart Mode:** Waterfall Logic.\n"
                f"• Gap 1: `{seconds_to_str(t_smart_gap1)}`\n"
                f"• Gap 2: `{seconds_to_str(t_smart_gap2)}`\n"
                f"• Full Access: `{seconds_to_str(t_smart_full)}`")
        
        custom_btns.append([InlineKeyboardButton("⏳ Set Gap 1", callback_data=f"time_ui#{chat_id}#time_gap1"),
                            InlineKeyboardButton("⏳ Set Gap 2", callback_data=f"time_ui#{chat_id}#time_gap2")])
        custom_btns.append([InlineKeyboardButton("⏰ Set Full Access", callback_data=f"time_ui#{chat_id}#time_smart")])

    # Footer
    footer_btns = [
        [InlineKeyboardButton("⚙️ Configure Shorteners", callback_data=f"set_slots#{chat_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"set_earn#{chat_id}")]
    ]

    await query.message.edit_text(
        f"🔗 **Shortener Mode Config**\n\n{desc}",
        reply_markup=InlineKeyboardMarkup([mode_btns] + custom_btns + footer_btns)
    )

# --- MODE CHANGER HANDLER ---
@Client.on_callback_query(filters.regex(r"^set_type#"))
async def set_mode_handler(client, query):
    _, chat_id, mode = query.data.split("#")
    await db.update_group_settings(chat_id, {'shortener_mode': mode})
    await shortlink_config(client, query) # Refresh UI

# --- ⏰ TIME PICKER UI ---
@Client.on_callback_query(filters.regex(r"^time_ui#"))
async def time_picker_ui(client, query):
    _, chat_id, key = query.data.split("#")
    
    # Mapping friendly names
    names = {
        'time_dynamic': "Dynamic Full Access",
        'time_gap1': "Smart Gap 1",
        'time_gap2': "Smart Gap 2",
        'time_smart': "Smart Full Access",
        'time_together': "Together Base Access"
    }
    name = names.get(key, "Time")

    text = f"⏱ **Set Time for {name}**\n\nChoose a duration:"
    
    # Time Options (Value in Seconds)
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

# --- SAVE TIME HANDLER ---
@Client.on_callback_query(filters.regex(r"^save_time#"))
async def save_time_handler(client, query):
    _, chat_id, key, seconds = query.data.split("#")
    await db.update_group_settings(chat_id, {key: int(seconds)})
    await query.answer("✅ Time Updated!", show_alert=True)
    await shortlink_config(client, query) # Return to Main Config

# --- 7. CONFIGURE SHORTENERS (SLOT UI) ---
@Client.on_callback_query(filters.regex(r"^set_slots#"))
async def configure_slots(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    shorteners = group_data.get('shorteners', {})
    
    current_mode = group_data.get('shortener_mode', 'dynamic').capitalize()
    
    # Calculate Interval in Hours
    interval = group_data.get('time_dynamic', 86400) if current_mode == 'Dynamic' else group_data.get('time_smart', 86400)
    interval_hours = int(interval / 3600)

    # --- BUILD STATUS LIST ---
    status_text = ""
    for i in range(1, 4):
        s_data = shorteners.get(str(i))
        if s_data:
            site_name = s_data['site']
            status_text += f"✅ Shortener {i}: {site_name}\n"
        else:
            status_text += f"❌ Shortener {i}: Not Set\n"

    # --- BUILD DESCRIPTION ---
    text = (
        f"🛠️ **Configuring {current_mode} Type for:** `{chat_id}`\n\n"
        f"**Verification Interval:** {interval_hours} hours\n\n"
        f"**Your Setup:**\n"
        f"{status_text}"
    )
    
    # --- BUILD BUTTONS ---
    buttons = []
    for i in range(1, 4):
        s_data = shorteners.get(str(i))
        if s_data:
            buttons.append([
                InlineKeyboardButton(f"✏️ Edit Shortener {i}", callback_data=f"edit_slot#{chat_id}#{i}"),
                InlineKeyboardButton(f"🗑️ Reset Slot {i}", callback_data=f"del_slot#{chat_id}#{i}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(f"➕ Set Shortener {i}", callback_data=f"add_slot#{chat_id}#{i}")
            ])

    help_text_btn = f"How {current_mode} mode works"

    footer_btns = [
        [InlineKeyboardButton("🧪 Test connected Shorteners", callback_data=f"test_sl#{chat_id}")],
        [InlineKeyboardButton("📘 How to connect shortener", url="https://t.me/YourChannel")],
        [InlineKeyboardButton(f"ℹ️ {help_text_btn}", url="https://t.me/YourChannel")],
        [InlineKeyboardButton("🔙 Back to shortener settings", callback_data=f"set_smode#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons + footer_btns))

# --- 8. ADD/EDIT SLOT HANDLER ---
@Client.on_callback_query(filters.regex(r"^add_slot#") | filters.regex(r"^edit_slot#"))
async def input_slot_req(client, query):
    _, chat_id, slot = query.data.split("#")
    
    await query.message.edit_text(
        f"📝 **Configuring Slot {slot}**\n\n"
        f"Send the Website and API Key in this format:\n"
        f"`website.com your_api_key`\n\n"
        f"Example: `gplinks.com 12345abcdef`\n\n"
        f"👇 Reply to this message within 60 seconds.",
    )
    
    try:
        reply = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if reply.text:
            try:
                parts = reply.text.strip().split(" ", 1)
                site = parts[0]
                api = parts[1]
                
                await db.add_shortener(chat_id, slot, site, api)
                await reply.reply_text(f"✅ **Slot {slot} Updated!**\nSite: {site}")
                await configure_slots(client, query)
            except:
                await reply.reply_text("❌ Invalid Format! Try again.")
                await configure_slots(client, query)
    except Exception as e:
        await query.message.reply_text("❌ Timeout! Please try again.")
        await configure_slots(client, query)

@Client.on_callback_query(filters.regex(r"^del_slot#"))
async def delete_slot(client, query):
    _, chat_id, slot = query.data.split("#")
    await db.remove_shortener(chat_id, slot)
    await query.answer(f"🗑️ Slot {slot} Cleared!", show_alert=True)
    await configure_slots(client, query)

@Client.on_callback_query(filters.regex(r"^test_sl#"))
async def test_shorteners(client, query):
    await query.answer("🧪 Testing connections... (Feature in progress)", show_alert=True)

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
    req_members = count >= 100
    icon_mem = "✅" if req_members else "❌"
    
    fsub_list = group_data.get('fsub_channels', [])
    req_fsub = len(fsub_list) > 0
    icon_fsub = "✅" if req_fsub else "❌"

    text = (
        f"🚫 **Disable Shortlink for:** `{chat_id}`\n\n"
        f"**Status:** {status_icon}\n\n"
        f"This feature bypasses shorteners, requiring users to join your Fsub channel(s) instead.\n\n"
        f"**Requirements to Activate:**\n"
        f"{icon_fsub} 1. Configure at least one Fsub channel.\n"
        f"{icon_mem} 2. Group must have over 100 members (Currently: {count})."
    )
    
    btn_text = "🔴 Disable Shortlinks Now" if not is_active else "🟢 Enable Shortlinks Back"
    cb_data = f"act_toggle#{chat_id}#off" if not is_active else f"act_toggle#{chat_id}#on"
    
    if not is_active and (not req_members or not req_fsub):
        cb_data = "alert_req"

    buttons = [
        [InlineKeyboardButton(btn_text, callback_data=cb_data)],
        [InlineKeyboardButton("🔙 Back to Earning Method", callback_data=f"set_earn#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^act_toggle#"))
async def toggle_activation(client, query):
    _, chat_id, action = query.data.split("#")
    chat_id = int(chat_id)
    if action == "off":
        await db.update_group_settings(chat_id, {'is_shortlink_active': False})
        await query.answer("🚫 Shortlink Mode Deactivated!", show_alert=True)
    else:
        await db.update_group_settings(chat_id, {'is_shortlink_active': True})
        await query.answer("✅ Shortlink Mode Activated!", show_alert=True)
    await earning_settings(client, query)

@Client.on_callback_query(filters.regex(r"^alert_req"))
async def alert_requirements(client, query):
    await query.answer("❌ Requirements not met!", show_alert=True)
