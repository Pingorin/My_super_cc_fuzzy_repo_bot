import asyncio
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

# --- HELPER: Check Shortener ---
async def check_shortener_link(domain, api):
    import aiohttp
    test_url = "https://google.com"
    api_url = f"https://{domain}/api?api={api}&url={test_url}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success" or data.get("shortenedUrl"): return True
    except: pass
    return False

# --- /settings COMMAND ---
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
    
    # ✅ Added "Force Subscribe" Button here
    buttons = [
        [InlineKeyboardButton("💰 Earning Method", callback_data=f"set_earn#{chat_id}"),
         InlineKeyboardButton("🔒 Force Subscribe", callback_data=f"fsub_menu#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Groups", callback_data="set_back_home")]
    ]
    try: title = (await client.get_chat(chat_id)).title
    except: title = "Unknown"
    await query.message.edit_text(f"⚙️ **Settings for:** {title}", reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🔒 FORCE SUBSCRIBE MENUS (NEW FEATURES)
# ==============================================================================

# --- FSUB MENU 1: LANDING PAGE ---
@Client.on_callback_query(filters.regex(r"^fsub_menu#"))
async def fsub_main_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    
    text = (
        f"🔒 **Fsub Settings for Chat ID:** `{chat_id}`\n\n"
        f"You can set specific channels that users must join before accessing files from this group.\n"
        f"This overrides the default bot settings."
    )
    
    buttons = [
        [InlineKeyboardButton("📢 Request Fsub", callback_data=f"fsub_slots#{chat_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"set_main#{chat_id}")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- FSUB MENU 2: CONFIGURE SLOTS ---
@Client.on_callback_query(filters.regex(r"^fsub_slots#"))
async def fsub_configure_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    fsub_channels = group_data.get('fsub_channels', {})
    
    # Status Logic
    s1 = f"✅ ID: `{fsub_channels.get('1')}`" if fsub_channels.get('1') else "Not Set ❌"
    s2 = f"✅ ID: `{fsub_channels.get('2')}`" if fsub_channels.get('2') else "Not Set ❌"
    s3 = f"✅ ID: `{fsub_channels.get('3')}`" if fsub_channels.get('3') else "Not Set ❌"

    text = (
        f"⚙️ **Configure Request F-Sub Channels for:** `{chat_id}`\n\n"
        f"1️⃣ **Slot 1:** {s1}\n"
        f"2️⃣ **Slot 2:** {s2}\n"
        f"3️⃣ **Slot 3:** {s3}\n\n"
        f"👇 **Select an option below:**"
    )
    
    buttons = []
    # Slot 1
    if fsub_channels.get('1'): buttons.append([InlineKeyboardButton("🗑️ Remove Slot 1", callback_data=f"rem_fsub#{chat_id}#1")])
    else: buttons.append([InlineKeyboardButton("➕ Set Slot 1", callback_data=f"set_fsub#{chat_id}#1")])
        
    # Slot 2
    if fsub_channels.get('2'): buttons.append([InlineKeyboardButton("🗑️ Remove Slot 2", callback_data=f"rem_fsub#{chat_id}#2")])
    else: buttons.append([InlineKeyboardButton("➕ Set Slot 2", callback_data=f"set_fsub#{chat_id}#2")])

    # Slot 3
    if fsub_channels.get('3'): buttons.append([InlineKeyboardButton("🗑️ Remove Slot 3", callback_data=f"rem_fsub#{chat_id}#3")])
    else: buttons.append([InlineKeyboardButton("➕ Set Slot 3", callback_data=f"set_fsub#{chat_id}#3")])

    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"fsub_menu#{chat_id}")])
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- FSUB INPUT HANDLER ---
@Client.on_callback_query(filters.regex(r"^set_fsub#"))
async def set_fsub_input(client, query):
    _, chat_id, slot = query.data.split("#")
    chat_id = int(chat_id)
    
    cancel_btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"fsub_slots#{chat_id}")]]
    
    await query.message.edit_text(
        f"👇 **Please send the Channel ID for Slot {slot}.**\n\n"
        f"ℹ️ **Instructions:**\n"
        f"1. Add this bot to that channel as **Admin**.\n"
        f"2. Forward a message from that channel here OR send the ID directly (e.g., `-100xxxxxxx`).\n"
        f"3. Supports both Private & Public channels.",
        reply_markup=InlineKeyboardMarkup(cancel_btn)
    )
    
    try:
        input_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        
        if not input_msg.text and not input_msg.forward_from_chat:
            return await query.message.edit_text("❌ Input must be a Text ID or Forwarded Message.", reply_markup=InlineKeyboardMarkup(cancel_btn))
        
        # 1. Extract Channel ID
        channel_id = None
        if input_msg.forward_from_chat:
            channel_id = input_msg.forward_from_chat.id
        else:
            try: channel_id = int(input_msg.text.strip())
            except: return await query.message.edit_text("❌ Invalid ID format! Must start with -100...", reply_markup=InlineKeyboardMarkup(cancel_btn))
        
        # 2. Check Admin Status
        status_msg = await query.message.reply_text("🔎 **Verifying Admin Status...**")
        try:
            member = await client.get_chat_member(channel_id, (await client.get_me()).id)
            if member.status != enums.ChatMemberStatus.ADMINISTRATOR:
                await status_msg.delete()
                return await query.message.edit_text(
                    f"❌ **Error:** I am not an Admin in `{channel_id}`.\n\nPlease add me as Admin and try again.",
                    reply_markup=InlineKeyboardMarkup(cancel_btn)
                )
        except Exception as e:
            await status_msg.delete()
            return await query.message.edit_text(
                f"❌ **Error:** Cannot access channel `{channel_id}`.\nMake sure I am added as Admin.\n\nError: {e}",
                reply_markup=InlineKeyboardMarkup(cancel_btn)
            )

        # 3. Save to DB
        await db.update_fsub_channel(chat_id, slot, channel_id)
        await status_msg.delete()
        await query.message.edit_text(f"✅ **Slot {slot} Set Successfully!**\nChannel ID: `{channel_id}`")
        await asyncio.sleep(2)
        
        # Return
        query.data = f"fsub_slots#{chat_id}"
        await fsub_configure_menu(client, query)

    except asyncio.TimeoutError:
        await query.message.edit_text("❌ Timeout! Please try again.", reply_markup=InlineKeyboardMarkup(cancel_btn))
    except Exception as e:
        print(f"Fsub Set Error: {e}")

@Client.on_callback_query(filters.regex(r"^rem_fsub#"))
async def remove_fsub_handler(client, query):
    _, chat_id, slot = query.data.split("#")
    await db.remove_fsub_channel(int(chat_id), slot)
    await query.answer(f"🗑️ Slot {slot} Removed!", show_alert=True)
    await fsub_configure_menu(client, query)

# ==============================================================================
# 💰 EARNING & SHORTENER MENUS (EXISTING)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^set_earn#"))
async def earning_settings(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    if not group_data: await db.add_group(chat_id)
    
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
    
    mode = group_data.get('shortener_mode', 'dynamic').lower()
    
    # Times
    t_dynamic = group_data.get('time_dynamic', 86400)
    t_smart_gap1 = group_data.get('time_gap1', 300)
    t_smart_gap2 = group_data.get('time_gap2', 300)
    t_smart_full = group_data.get('time_smart', 86400)
    t_together_base = group_data.get('time_together', 604800)
    t_together_3 = group_data.get('time_together_3', 86400)
    
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
    
    if mode == 'dynamic':
        desc = f"**Dynamic Mode:** Checks slots 1->2->3.\n⏱ Full Access: `{seconds_to_str(t_dynamic)}`"
        custom_btns.append([InlineKeyboardButton("⏰ Set Access Time", callback_data=f"time_ui#{chat_id}#time_dynamic")])

    elif mode == 'together':
        desc = (f"**Together Mode:**\n"
                f"• 1-2 Links: `{seconds_to_str(t_together_base)}` Access\n"
                f"• 3 Links: Final Access `{seconds_to_str(t_together_3)}`")
        
        custom_btns.append([InlineKeyboardButton("⏰ Set Base Time", callback_data=f"time_ui#{chat_id}#time_together")])
        custom_btns.append([InlineKeyboardButton("⏰ Set 3-Link Time", callback_data=f"time_ui#{chat_id}#time_together_3")])

    elif mode == 'smart':
        desc = (f"**Smart Mode:** Waterfall Logic.\n"
                f"• Gap 1: `{seconds_to_str(t_smart_gap1)}`\n"
                f"• Gap 2: `{seconds_to_str(t_smart_gap2)}`\n"
                f"• Full Access: `{seconds_to_str(t_smart_full)}`")
        custom_btns.append([InlineKeyboardButton("⏳ Gap 1", callback_data=f"time_ui#{chat_id}#time_gap1"),
                            InlineKeyboardButton("⏳ Gap 2", callback_data=f"time_ui#{chat_id}#time_gap2")])
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

@Client.on_callback_query(filters.regex(r"^time_ui#"))
async def time_picker_ui(client, query):
    _, chat_id, key = query.data.split("#")
    
    names = {
        'time_dynamic': "Dynamic Full Access",
        'time_gap1': "Smart Gap 1",
        'time_gap2': "Smart Gap 2",
        'time_smart': "Smart Full Access",
        'time_together': "Together Base Access",
        'time_together_3': "Together 3-Link Time"
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

@Client.on_callback_query(filters.regex(r"^set_slots#"))
async def configure_slots(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    shorteners = group_data.get('shorteners', {})
    current_mode = group_data.get('shortener_mode', 'dynamic').capitalize()
    
    interval = group_data.get('time_dynamic', 86400)
    interval_hours = int(interval / 3600)

    status_text = ""
    for i in range(1, 4):
        s_data = shorteners.get(str(i))
        if s_data: status_text += f"✅ Shortener {i}: {s_data['site']}\n"
        else: status_text += f"❌ Shortener {i}: Not Set\n"

    text = f"🛠️ **Configuring {current_mode} Mode**\n**Interval:** {interval_hours}h\n\n**Setup:**\n{status_text}"
    
    buttons = []
    for i in range(1, 4):
        s_data = shorteners.get(str(i))
        if s_data:
            buttons.append([InlineKeyboardButton(f"✏️ Edit Slot {i}", callback_data=f"edit_slot#{chat_id}#{i}"),
                            InlineKeyboardButton(f"🗑️ Reset {i}", callback_data=f"del_slot#{chat_id}#{i}")])
        else:
            buttons.append([InlineKeyboardButton(f"➕ Set Shortener {i}", callback_data=f"add_slot#{chat_id}#{i}")])

    footer = [[InlineKeyboardButton("🧪 Test Connections", callback_data=f"test_sl#{chat_id}")],
              [InlineKeyboardButton("🔙 Back", callback_data=f"set_smode#{chat_id}")]]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons + footer))

@Client.on_callback_query(filters.regex(r"^add_slot#") | filters.regex(r"^edit_slot#"))
async def input_slot_req(client, query):
    _, chat_id, slot = query.data.split("#")
    chat_id = int(chat_id)
    cancel_btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"set_slots#{chat_id}")]]

    await query.message.edit_text(f"Send **Domain** for Slot {slot}.\n(e.g., `shareus.in`)", reply_markup=InlineKeyboardMarkup(cancel_btn))
    
    try:
        domain_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if not domain_msg.text: return await query.message.edit_text("❌ Text only!", reply_markup=InlineKeyboardMarkup(cancel_btn))
        domain = domain_msg.text.strip()
        await domain_msg.delete()
    except: return

    await query.message.edit_text(f"✅ Domain set.\nNow send **API Key**.", reply_markup=InlineKeyboardMarkup(cancel_btn))

    try:
        api_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if not api_msg.text: return await query.message.edit_text("❌ Text only!", reply_markup=InlineKeyboardMarkup(cancel_btn))
        api = api_msg.text.strip()
        await api_msg.delete()
    except: return

    await db.add_shortener(chat_id, slot, domain, api)
    await query.message.edit_text(f"✅ **Slot {slot} Updated!**")
    await asyncio.sleep(1.5)
    query.data = f"set_slots#{chat_id}"
    await configure_slots(client, query)

@Client.on_callback_query(filters.regex(r"^del_slot#"))
async def delete_slot(client, query):
    _, chat_id, slot = query.data.split("#")
    await db.remove_shortener(chat_id, slot)
    await query.answer(f"🗑️ Slot {slot} Reset!", show_alert=True)
    await configure_slots(client, query)

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
        await query.message.edit_text("🎉 **All shorteners working!**", reply_markup=InlineKeyboardMarkup(back_btn))
    else:
        await query.message.edit_text(f"📊 **Results:**\n\n" + "\n".join(results), reply_markup=InlineKeyboardMarkup(back_btn))

@Client.on_callback_query(filters.regex(r"^set_back_home"))
async def back_home(client, query):
    await settings_command(client, query.message)

@Client.on_callback_query(filters.regex(r"^set_disable#"))
async def disable_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    is_active = group_data.get('is_shortlink_active', True)
    
    btn_text = "🔴 Disable" if is_active else "🟢 Enable"
    cb = f"act_toggle#{chat_id}#off" if is_active else f"act_toggle#{chat_id}#on"
    
    await query.message.edit_text(f"Status: {'Active' if is_active else 'Inactive'}", 
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, callback_data=cb)], [InlineKeyboardButton("🔙 Back", callback_data=f"set_earn#{chat_id}")]]))

@Client.on_callback_query(filters.regex(r"^act_toggle#"))
async def toggle_act(client, query):
    _, chat_id, action = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'is_shortlink_active': (action == "on")})
    await disable_menu(client, query)
