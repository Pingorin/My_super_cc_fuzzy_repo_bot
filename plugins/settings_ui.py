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
    # Fetch all groups from DB
    async for group in db.groups.find({}):
        try:
            chat_id = group['id']
            try:
                # Check if user is admin in that group
                member = await client.get_chat_member(chat_id, user_id)
            except: continue 
            
            if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
                try:
                    chat_info = await client.get_chat(chat_id)
                    title = chat_info.title
                except:
                    title = group.get('title', 'Unknown Group')
                    
                user_groups.append((title, chat_id))
        except: continue 

    await msg.delete()
    if not user_groups:
        return await message.reply_text("❌ **No Groups Found!**\nMake sure I am added to your group and you are an Admin there.")

    buttons = []
    for title, chat_id in user_groups:
        buttons.append([InlineKeyboardButton(f"📂 {title}", callback_data=f"set_main#{chat_id}")])
    
    await message.reply_text("⚙️ **Select a Group:**", reply_markup=InlineKeyboardMarkup(buttons))

# --- MAIN SETTINGS MENU ---
@Client.on_callback_query(filters.regex(r"^set_main#"))
async def main_settings_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    
    buttons = [
        [InlineKeyboardButton("💰 Earning Method", callback_data=f"set_earn#{chat_id}"),
         InlineKeyboardButton("📢 Force Subscribe", callback_data=f"fsub_menu#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Groups", callback_data="set_back_home")]
    ]
    try: title = (await client.get_chat(chat_id)).title
    except: title = "Unknown"
    await query.message.edit_text(f"⚙️ **Settings for:** {title}", reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🔒 FSUB SETTINGS (OLD REPO STYLE)
# ==============================================================================

# 1. FSUB MAIN MENU (Selection)
@Client.on_callback_query(filters.regex(r"^fsub_menu#"))
async def fsub_main_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    
    text = (
        f"📢 **Force Subscribe Settings**\n\n"
        f"Select which type of FSub you want to configure for `{chat_id}`:"
    )
    
    btn = [
        [InlineKeyboardButton("Request Fsub (Slots 1, 2, 4)", callback_data=f"req_fsub_menu#{chat_id}")],
        [InlineKeyboardButton("Normal Fsub (Slot 3)", callback_data=f"norm_fsub_menu#{chat_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"set_main#{chat_id}")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))

# 2. REQUEST FSUB MENU (Slots 1, 2, 4)
@Client.on_callback_query(filters.regex(r"^req_fsub_menu#"))
async def request_fsub_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    if not group_data: await db.add_group(chat_id)
    
    fsub_channels = group_data.get('fsub_channels', {})
    
    # Helper to get status text
    async def get_status(slot):
        cid = fsub_channels.get(str(slot))
        if not cid: return "Not Set ❌"
        try:
            chat = await client.get_chat(cid)
            return f"{chat.title}"
        except:
            return f"ID: {cid} (Unreachable)"

    s1_txt = await get_status(1)
    s2_txt = await get_status(2)
    s4_txt = await get_status(4)

    text = (
        f"⚙️ **Request F-Sub Channels (Auto-Approve Logic)**\n\n"
        f"1️⃣ **Slot 1:** {s1_txt}\n"
        f"2️⃣ **Slot 2:** {s2_txt}\n"
        f"4️⃣ **Slot 4:** {s4_txt} (Post-Verify)\n\n"
        f"👇 **Select an option:**"
    )
    
    buttons = []
    # Slot 1
    if fsub_channels.get('1'):
        buttons.append([InlineKeyboardButton("✏️ Edit Slot 1", callback_data=f"set_fsub#{chat_id}#1"), InlineKeyboardButton("🗑️", callback_data=f"rem_fsub#{chat_id}#1#req")])
    else:
        buttons.append([InlineKeyboardButton("➕ Set Slot 1", callback_data=f"set_fsub#{chat_id}#1")])
        
    # Slot 2
    if fsub_channels.get('2'):
        buttons.append([InlineKeyboardButton("✏️ Edit Slot 2", callback_data=f"set_fsub#{chat_id}#2"), InlineKeyboardButton("🗑️", callback_data=f"rem_fsub#{chat_id}#2#req")])
    else:
        buttons.append([InlineKeyboardButton("➕ Set Slot 2", callback_data=f"set_fsub#{chat_id}#2")])

    # Slot 4
    if fsub_channels.get('4'):
        buttons.append([InlineKeyboardButton("✏️ Edit Slot 4", callback_data=f"set_fsub#{chat_id}#4"), InlineKeyboardButton("🗑️", callback_data=f"rem_fsub#{chat_id}#4#req")])
    else:
        buttons.append([InlineKeyboardButton("➕ Set Slot 4", callback_data=f"set_fsub#{chat_id}#4")])

    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"fsub_menu#{chat_id}")])
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 3. NORMAL FSUB MENU (Slot 3)
@Client.on_callback_query(filters.regex(r"^norm_fsub_menu#"))
async def normal_fsub_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    if not group_data: await db.add_group(chat_id)
    
    fsub_channels = group_data.get('fsub_channels', {})
    cid = fsub_channels.get('3')
    
    status = "Not Set ❌"
    if cid:
        try:
            chat = await client.get_chat(cid)
            status = f"{chat.title}"
        except:
            status = f"ID: {cid} (Unreachable)"

    text = (
        f"⚙️ **Normal F-Sub Channel (Join & Back)**\n\n"
        f"3️⃣ **Slot 3:** {status}\n\n"
        f"👇 **Select an option:**"
    )
    
    buttons = []
    if cid:
        buttons.append([
            InlineKeyboardButton("✏️ Edit Slot 3", callback_data=f"set_fsub#{chat_id}#3"),
            InlineKeyboardButton("🗑️ Clear Slot 3", callback_data=f"rem_fsub#{chat_id}#3#norm")
        ])
    else:
        buttons.append([InlineKeyboardButton("➕ Set Slot 3", callback_data=f"set_fsub#{chat_id}#3")])

    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"fsub_menu#{chat_id}")])
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# 4. SET FSUB ID HANDLER
@Client.on_callback_query(filters.regex(r"^set_fsub#"))
async def set_fsub_input(client, query):
    _, chat_id, slot = query.data.split("#")
    chat_id = int(chat_id)
    
    # Determine Back Button destination
    back_data = f"req_fsub_menu#{chat_id}" if slot in ['1', '2', '4'] else f"norm_fsub_menu#{chat_id}"
    cancel_btn = [[InlineKeyboardButton("❌ Cancel", callback_data=back_data)]]
    
    await query.message.edit_text(
        f"👇 **Send Channel ID for Slot {slot}**\n\n"
        f"1. Make me **Admin** in that channel.\n"
        f"2. Forward a message from channel OR send ID (e.g. -100xxxx).\n",
        reply_markup=InlineKeyboardMarkup(cancel_btn)
    )
    
    try:
        input_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        
        if not input_msg.text and not input_msg.forward_from_chat:
            return await query.message.edit_text("❌ Input must be Text or Forward.", reply_markup=InlineKeyboardMarkup(cancel_btn))
        
        # Extract ID
        channel_id = None
        if input_msg.forward_from_chat:
            channel_id = input_msg.forward_from_chat.id
        else:
            try: channel_id = int(input_msg.text.strip())
            except: return await query.message.edit_text("❌ Invalid ID Format!", reply_markup=InlineKeyboardMarkup(cancel_btn))
        
        # Validate Bot Admin
        status_msg = await query.message.reply_text("🔎 Verifying Admin Status...")
        try:
            member = await client.get_chat_member(channel_id, (await client.get_me()).id)
            if member.status != enums.ChatMemberStatus.ADMINISTRATOR:
                await status_msg.delete()
                return await query.message.edit_text("❌ I am not Admin in that channel!", reply_markup=InlineKeyboardMarkup(cancel_btn))
        except Exception as e:
            await status_msg.delete()
            return await query.message.edit_text(f"❌ Error accessing channel: {e}", reply_markup=InlineKeyboardMarkup(cancel_btn))

        # Save to DB
        await db.update_fsub_channel(chat_id, slot, channel_id)
        await status_msg.delete()
        await query.message.edit_text(f"✅ **Slot {slot} Set Successfully!**")
        await asyncio.sleep(2)
        
        # Return to Menu
        if slot in ['1', '2', '4']:
            query.data = f"req_fsub_menu#{chat_id}"
            await request_fsub_menu(client, query)
        else:
            query.data = f"norm_fsub_menu#{chat_id}"
            await normal_fsub_menu(client, query)

    except asyncio.TimeoutError:
        await query.message.edit_text("❌ Timeout!", reply_markup=InlineKeyboardMarkup(cancel_btn))
    except Exception as e:
        print(f"Set Fsub Error: {e}")

# 5. REMOVE FSUB HANDLER
@Client.on_callback_query(filters.regex(r"^rem_fsub#"))
async def remove_fsub_handler(client, query):
    _, chat_id, slot, menu_type = query.data.split("#")
    chat_id = int(chat_id)
    
    await db.remove_fsub_channel(chat_id, slot)
    await query.answer(f"Slot {slot} Removed!", show_alert=True)
    
    if menu_type == "req":
        query.data = f"req_fsub_menu#{chat_id}"
        await request_fsub_menu(client, query)
    else:
        query.data = f"norm_fsub_menu#{chat_id}"
        await normal_fsub_menu(client, query)

# ==============================================================================
# 💰 EARNING & SHORTENER SETTINGS
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
    
    # Friendly Name Mapping
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
    
    # Requirement Check
    try: count = await client.get_chat_members_count(chat_id)
    except: count = 0
    fsub_list = group_data.get('fsub_channels', {})
    req_mem = count >= 100
    req_fsub = bool(fsub_list.get('1') or fsub_list.get('2'))

    text = (
        f"🚫 **Disable Shortlink Mode**\n\n"
        f"Status: {'✅ Active' if is_active else '❌ Inactive'}\n\n"
        f"Requirements to Disable:\n"
        f"{'✅' if req_fsub else '❌'} 1. Set Fsub Channel.\n"
        f"{'✅' if req_mem else '❌'} 2. 100+ Members (Cur: {count})."
    )
    
    cb_data = f"act_toggle#{chat_id}#off" if is_active else f"act_toggle#{chat_id}#on"
    if is_active and (not req_mem or not req_fsub): cb_data = "alert_req"

    buttons = [
        [InlineKeyboardButton("🔴 Disable" if is_active else "🟢 Enable", callback_data=cb_data)],
        [InlineKeyboardButton("🔙 Back", callback_data=f"set_earn#{chat_id}")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^act_toggle#"))
async def toggle_act(client, query):
    _, chat_id, action = query.data.split("#")
    await db.update_group_settings(int(chat_id), {'is_shortlink_active': (action == "on")})
    await disable_menu(client, query)

@Client.on_callback_query(filters.regex(r"^alert_req"))
async def alert_requirements(client, query):
    await query.answer("❌ Requirements not met!", show_alert=True)

@Client.on_callback_query(filters.regex(r"^set_back_home"))
async def back_home(client, query):
    await settings_command(client, query.message)
