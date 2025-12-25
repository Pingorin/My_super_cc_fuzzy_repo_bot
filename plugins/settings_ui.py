import asyncio
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.errors import PeerIdInvalid, ChannelInvalid, FloodWait, UserNotParticipant
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

# --- /settings COMMAND (SMART & CRASH PROOF) ---
@Client.on_message(filters.command("settings") & filters.private)
async def settings_command(client, message):
    user_id = message.from_user.id
    msg = await message.reply_text("🔄 **Loading your groups...**")
    
    user_groups = []
    
    # 1. Fetch all groups from Database
    # We iterate over the database cursor directly
    async for group in db.groups.find({}):
        chat_id = group['id']
        title = group.get('title', f"Group {chat_id}") 
        
        try:
            # 2. Smart Verification Logic
            # Try to fetch member status to verify Admin/Owner
            member = await client.get_chat_member(chat_id, user_id)
            
            # 3. Strict Admin Check
            if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
                user_groups.append((title, chat_id))
        
        except (PeerIdInvalid, ChannelInvalid):
            # 4. Crash Prevention
            # If bot restarted and doesn't recognize the peer, skip it to avoid crash
            # Instead of stopping the whole command, we just move to the next group
            continue
        except UserNotParticipant:
            # User is not in the group anymore, skip
            continue
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception as e:
            print(f"Error loading settings for {chat_id}: {e}")
            continue

    await msg.delete()
    
    if not user_groups:
        return await message.reply_text(
            "❌ **No Connected Groups Found!**\n\n"
            "**Possible Reasons:**\n"
            "1. You are not an Admin in any registered group.\n"
            "2. Bot restarted and needs a refresh (Send /connect in group).\n"
            "3. I am not added to your groups."
        )

    buttons = []
    for title, chat_id in user_groups:
        buttons.append([InlineKeyboardButton(f"📂 {title}", callback_data=f"set_main#{chat_id}")])
    
    await message.reply_text("⚙️ **Select a Group:**", reply_markup=InlineKeyboardMarkup(buttons))

# --- MAIN MENUS ---
@Client.on_callback_query(filters.regex(r"^set_main#"))
async def main_settings_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    
    # Smart Title Fetching
    title = "Unknown Group"
    try: 
        chat = await client.get_chat(chat_id)
        title = chat.title
    except: 
        # Fallback to Database Title if live check fails
        group_data = await db.get_group_settings(chat_id)
        if group_data:
            title = group_data.get('title', "Unknown Group")

    buttons = [
        [InlineKeyboardButton("💰 Earning Method", callback_data=f"set_earn#{chat_id}"),
         InlineKeyboardButton("🔒 Force Subscribe", callback_data=f"fsub_menu#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Groups", callback_data="set_back_home")]
    ]
    await query.message.edit_text(f"⚙️ **Settings for:** {title}", reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🔒 FSUB SETTINGS (2 SLOTS) 
# ==============================================================================

# 1. FSUB CONFIGURE MENU
@Client.on_callback_query(filters.regex(r"^fsub_menu#"))
async def fsub_configure_menu(client, query):
    try:
        chat_id = int(query.data.split("#")[1])
        group_data = await db.get_group_settings(chat_id)
        
        if not group_data:
            # Fallback creation if missing
            await db.add_group(chat_id, "Unknown Group")
            group_data = await db.get_group_settings(chat_id)
            
        raw_fsub = group_data.get('fsub_channels')
        if isinstance(raw_fsub, list): fsub_channels = {} 
        elif isinstance(raw_fsub, dict): fsub_channels = raw_fsub
        else: fsub_channels = {}

        # Helper to safely get Title
        async def get_safe_title(cid):
            try:
                chat = await client.get_chat(cid)
                return f"📍{chat.title}", True
            except:
                return f"`{cid}`", False

        # SLOT 1
        s1_id = fsub_channels.get('1')
        s1_txt = "❌ Slot 1: Not Set"
        if s1_id:
            title, live = await get_safe_title(s1_id)
            status = "(Saved)" if not live else ""
            s1_txt = f"✅ Slot 1: {title} {status}"

        # SLOT 2
        s2_id = fsub_channels.get('2')
        s2_txt = "❌ Slot 2: Not Set"
        if s2_id:
            title, live = await get_safe_title(s2_id)
            status = "(Saved)" if not live else ""
            s2_txt = f"✅ Slot 2: {title} {status}"

        text = (
            f"⚙️ **Configure Request F-Sub Channels for:** `{chat_id}`\n\n"
            f"{s1_txt}\n{s2_txt}\n\n"
            f"👇 **Select an option below:**"
        )
        
        buttons = []
        if s1_id:
            buttons.append([InlineKeyboardButton("✏️ Edit Slot 1", callback_data=f"set_fsub#{chat_id}#1"), InlineKeyboardButton("🗑️ Clear Slot 1", callback_data=f"rem_fsub_one#{chat_id}#1")])
        else:
            buttons.append([InlineKeyboardButton("➕ Set Slot 1", callback_data=f"set_fsub#{chat_id}#1")])

        if s2_id:
            buttons.append([InlineKeyboardButton("✏️ Edit Slot 2", callback_data=f"set_fsub#{chat_id}#2"), InlineKeyboardButton("🗑️ Clear Slot 2", callback_data=f"rem_fsub_one#{chat_id}#2")])
        else:
            buttons.append([InlineKeyboardButton("➕ Set Slot 2", callback_data=f"set_fsub#{chat_id}#2")])

        if s1_id or s2_id:
            buttons.append([InlineKeyboardButton("🗑️ Remove all", callback_data=f"rem_fsub_all#{chat_id}")])

        buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"set_main#{chat_id}")])
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        print(f"FSub Menu Error: {e}")
        await query.answer("❌ Error: DB sync issue. Try again.", show_alert=True)

# 2. SET SLOT INPUT
@Client.on_callback_query(filters.regex(r"^set_fsub#"))
async def set_fsub_input(client, query):
    _, chat_id, slot = query.data.split("#")
    chat_id = int(chat_id)
    cancel_btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"fsub_menu#{chat_id}")]]
    
    await query.message.edit_text(
        f"👇 **Set F-Sub Channel for Slot {slot}**\n\nPlease send **Channel ID** (e.g. `-100xxxx`).\n⚠️ Bot must be Admin there.",
        reply_markup=InlineKeyboardMarkup(cancel_btn)
    )
    
    try:
        input_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if not input_msg.text: return await query.message.edit_text("❌ Text only.", reply_markup=InlineKeyboardMarkup(cancel_btn))
        
        try:
            channel_id = int(input_msg.text.strip())
            if not str(channel_id).startswith("-100"): channel_id = int("-100" + str(channel_id).replace("-", ""))
        except: return await query.message.edit_text("❌ Invalid ID.", reply_markup=InlineKeyboardMarkup(cancel_btn))
        
        # Save to DB
        await db.update_fsub_channel(chat_id, slot, channel_id)
        
        await query.message.edit_text(f"✅ **Saved!**\nID: `{channel_id}`", reply_markup=InlineKeyboardMarkup(cancel_btn))
        await asyncio.sleep(1)
        query.data = f"fsub_menu#{chat_id}"
        await fsub_configure_menu(client, query)

    except asyncio.TimeoutError:
        await query.message.edit_text("❌ Timeout!", reply_markup=InlineKeyboardMarkup(cancel_btn))

# 4. REMOVE SINGLE SLOT
@Client.on_callback_query(filters.regex(r"^rem_fsub_one#"))
async def remove_fsub_one(client, query):
    _, chat_id, slot = query.data.split("#")
    await db.remove_fsub_channel(int(chat_id), slot)
    await query.answer(f"Slot {slot} Cleared!", show_alert=True)
    await fsub_configure_menu(client, query)

# 5. REMOVE ALL SLOTS
@Client.on_callback_query(filters.regex(r"^rem_fsub_all#"))
async def remove_fsub_all(client, query):
    chat_id = int(query.data.split("#")[1])
    await db.remove_all_fsub_channels(chat_id)
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
    chat_id = int(chat_id)
    cancel_btn = [[InlineKeyboardButton("❌ Cancel", callback_data=f"set_slots#{chat_id}")]]
    
    await query.message.edit_text(f"Send **Domain** for Slot {slot}.\n(e.g. shareus.in)", reply_markup=InlineKeyboardMarkup(cancel_btn))
    try:
        d_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        domain = d_msg.text.strip()
        await d_msg.delete()
        
        await query.message.edit_text(f"✅ Domain set.\nNow send **API Key** for Slot {slot}.", reply_markup=InlineKeyboardMarkup(cancel_btn))
        a_msg = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        api = a_msg.text.strip()
        await a_msg.delete()
        
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
