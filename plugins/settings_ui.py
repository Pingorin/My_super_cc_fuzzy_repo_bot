from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from database.users_chats_db import db
from utils import temp
import info

# --- /settings COMMAND (PM ONLY) ---
@Client.on_message(filters.command("settings") & filters.private)
async def settings_command(client, message):
    user_id = message.from_user.id
    msg = await message.reply_text("🔄 **Loading your groups...**")
    
    # User ke groups dhundo jahan wo Admin hai aur Bot bhi hai
    # (Note: MongoDB me iterate karke check karna padega)
    user_groups = []
    async for group in db.groups.find({}):
        try:
            chat_id = group['id']
            member = await client.get_chat_member(chat_id, user_id)
            if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
                chat_info = await client.get_chat(chat_id)
                user_groups.append((chat_info.title, chat_id))
        except Exception as e:
            continue # Bot shayad group se nikal gaya ho

    await msg.delete()
    
    if not user_groups:
        return await message.reply_text("❌ **No Groups Found!**\nMake sure I am added to your group and you are an Admin there.")

    # Groups List Buttons
    buttons = []
    for title, chat_id in user_groups:
        buttons.append([InlineKeyboardButton(f"📂 {title}", callback_data=f"set_main#{chat_id}")])
    
    await message.reply_text(
        "⚙️ **Select a Group to Configure:**\n\nChoose the group you want to manage settings for.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- 1. MAIN SETTINGS MENU ---
@Client.on_callback_query(filters.regex(r^"set_main#"))
async def main_settings_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    
    buttons = [
        [InlineKeyboardButton("💰 Earning Method", callback_data=f"set_earn#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to Groups", callback_data="set_back_home")]
    ]
    
    try:
        chat = await client.get_chat(chat_id)
        title = chat.title
    except: title = "Unknown Group"

    await query.message.edit_text(
        f"⚙️ **Settings for:** {title}\nID: `{chat_id}`\n\nSelect a category to configure:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- 2. EARNING METHOD MENU ---
@Client.on_callback_query(filters.regex(r^"set_earn#"))
async def earning_settings(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    # Data Fetch
    active_mode = "SHORTLINK" if group_data.get('is_shortlink_active', True) else "FSUB (Disable Shortlink)"
    shortener_count = len(group_data.get('shorteners', {}))
    
    text = (
        f"💰 **Earning Method Settings for:** `{chat_id}`\n\n"
        f"**Current Active Mode:** `{active_mode}`\n"
        f"🔗 **Shorteners Configured:** `{shortener_count}`\n\n"
        f"Select a mode below to configure and activate it."
    )
    
    buttons = [
        [InlineKeyboardButton("🔗 Shortlink Mode", callback_data=f"set_smode#{chat_id}")],
        [InlineKeyboardButton("🚫 Disable Shortlink", callback_data=f"set_disable#{chat_id}")],
        [InlineKeyboardButton("🔙 Back to main settings", callback_data=f"set_main#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- 3. SHORTLINK MODE CONFIGURATION ---
@Client.on_callback_query(filters.regex(r^"set_smode#"))
async def shortlink_config(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    current_type = group_data.get('shortener_mode', 'dynamic').capitalize()
    
    # Helper Texts based on selection
    desc_map = {
        'dynamic': "Bot will check Slot 1 -> Slot 2 -> Slot 3 one by one. If user verifies one, they get file.",
        'together': "User must verify ALL configured slots together to get the file.",
        'smart': "Bot automatically rotates between available shorteners for each user."
    }
    desc = desc_map.get(current_type.lower(), "Standard Mode")

    text = (
        f"🔗 **Shortener Mode Configuration for:** `{chat_id}`\n\n"
        f"**Current Shortener Type:** `{current_type}`\n\n"
        f"📝 **{current_type} Mode Demo:**\n_{desc}_"
    )
    
    # Logic for Select Buttons (Tick mark)
    modes = ['dynamic', 'together', 'smart']
    mode_btns = []
    for m in modes:
        tick = "✅ " if m == current_type.lower() else ""
        mode_btns.append(InlineKeyboardButton(f"{tick}{m.capitalize()}", callback_data=f"set_type#{chat_id}#{m}"))

    buttons = [
        mode_btns, # Row with 3 buttons
        [InlineKeyboardButton("⚙️ Configure Shorteners", callback_data=f"set_slots#{chat_id}")],
        [InlineKeyboardButton("🔴 Deactivate Shortlink Mode", callback_data=f"act_toggle#{chat_id}#off")],
        [InlineKeyboardButton("🔙 Back to Earning methods", callback_data=f"set_earn#{chat_id}")]
    ]
    
    if group_data.get('is_shortlink_active') == False:
         buttons[2] = [InlineKeyboardButton("🟢 Activate Shortlink Mode", callback_data=f"act_toggle#{chat_id}#on")]

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- 4. TOGGLE MODE (Dynamic/Together/Smart) ---
@Client.on_callback_query(filters.regex(r^"set_type#"))
async def set_shortener_mode(client, query):
    _, chat_id, mode = query.data.split("#")
    await db.update_group_settings(chat_id, {'shortener_mode': mode})
    await query.answer(f"✅ Mode Changed to {mode.capitalize()}")
    # Refresh Page
    await shortlink_config(client, query)

# --- 5. DISABLE SHORTLINK (FSUB MENU) ---
@Client.on_callback_query(filters.regex(r^"set_disable#"))
async def disable_shortlink_menu(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    
    is_active = not group_data.get('is_shortlink_active', True)
    status_icon = "✅ ACTIVE" if is_active else "❌ INACTIVE"
    
    # Check Requirements
    # 1. Member Count
    try:
        count = await client.get_chat_members_count(chat_id)
    except: count = 0
    req_members = count >= 100
    icon_mem = "✅" if req_members else "❌"
    
    # 2. FSub Configured (Dummy check - assumes saved in DB)
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
    
    # Agar requirement meet nahi hui to button disable ya alert
    if not is_active and (not req_members or not req_fsub):
        cb_data = "alert_req"

    buttons = [
        [InlineKeyboardButton(btn_text, callback_data=cb_data)],
        [InlineKeyboardButton("🔙 Back to Earning Method", callback_data=f"set_earn#{chat_id}")]
    ]
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

# --- 6. ACTIVATE/DEACTIVATE TOGGLE POPUP ---
@Client.on_callback_query(filters.regex(r^"act_toggle#"))
async def toggle_activation(client, query):
    _, chat_id, action = query.data.split("#")
    chat_id = int(chat_id)
    
    if action == "off":
        await db.update_group_settings(chat_id, {'is_shortlink_active': False})
        await query.answer("🚫 Shortlink Mode Deactivated! FSUB is now primary.", show_alert=True)
    else:
        await db.update_group_settings(chat_id, {'is_shortlink_active': True})
        await query.answer("✅ Shortlink Mode Activated!", show_alert=True)
    
    # Return to Earning Menu
    await earning_settings(client, query)

@Client.on_callback_query(filters.regex(r^"alert_req"))
async def alert_requirements(client, query):
    await query.answer("❌ Requirements not met!\nAdd FSub channel & get 100+ members.", show_alert=True)

# --- 7. CONFIGURE SHORTENERS (SLOTS) ---
@Client.on_callback_query(filters.regex(r^"set_slots#"))
async def configure_slots(client, query):
    chat_id = int(query.data.split("#")[1])
    group_data = await db.get_group_settings(chat_id)
    shorteners = group_data.get('shorteners', {})
    
    current_mode = group_data.get('shortener_mode', 'dynamic').capitalize()
    
    # Helper Links
    help_text_map = {
        'Dynamic': "How Dynamic mode works",
        'Together': "How Together mode works",
        'Smart': "How Smart mode works"
    }
    help_text = help_text_map.get(current_mode, "How it works")

    text = f"⚙️ **Configure Shorteners**\nSelect a slot to Edit or Add."
    
    # Slot Buttons Logic
    slots_btns = []
    for i in range(1, 4): # Slots 1, 2, 3
        s_data = shorteners.get(str(i))
        if s_data:
            btn_text = f"✏️ Edit Slot {i} ({s_data['site']})"
            cb = f"edit_slot#{chat_id}#{i}"
        else:
            btn_text = f"➕ Add Slot {i}"
            cb = f"add_slot#{chat_id}#{i}"
        slots_btns.append([InlineKeyboardButton(btn_text, callback_data=cb)])
        
        # Clear button if exists
        if s_data:
             slots_btns.append([InlineKeyboardButton(f"🗑️ Clear Slot {i}", callback_data=f"del_slot#{chat_id}#{i}")])

    footer_btns = [
        [InlineKeyboardButton("🧪 Test connected Shorteners", callback_data=f"test_sl#{chat_id}")],
        [InlineKeyboardButton("📘 How to connect shortener", url="https://t.me/YourChannel")], # Replace link
        [InlineKeyboardButton(f"ℹ️ {help_text}", url="https://t.me/YourChannel")], # Replace link
        [InlineKeyboardButton("🔙 Back to shortener settings", callback_data=f"set_smode#{chat_id}")]
    ]
    
    final_markup = InlineKeyboardMarkup(slots_btns + footer_btns)
    await query.message.edit_text(text, reply_markup=final_markup)

# --- 8. ADD/EDIT SLOT HANDLER ---
# Note: Input lene ke liye ForceReply ya Listener chahiye.
# Simple way: Bot message karega "Send API & URL" aur next message pakdega.
# Yahan hum basics dikha rahe hain.

@Client.on_callback_query(filters.regex(r^"add_slot#") | filters.regex(r^"edit_slot#"))
async def input_slot_req(client, query):
    _, chat_id, slot = query.data.split("#")
    
    # Iske liye ek Listener Logic chahiye hota hai.
    # User ko bolo: "Send format: website.com api_key"
    await query.message.edit_text(
        f"📝 **Configuring Slot {slot}**\n\n"
        f"Send the Website and API Key in this format:\n"
        f"`website.com your_api_key`\n\n"
        f"Example: `gplinks.com 12345abcdef`\n\n"
        f"👇 Reply to this message within 60 seconds.",
    )
    
    # Listen for reply
    try:
        reply = await client.listen(chat_id=query.message.chat.id, user_id=query.from_user.id, timeout=60)
        if reply.text:
            try:
                site, api = reply.text.split(" ", 1)
                await db.add_shortener(chat_id, slot, site, api)
                await reply.reply_text(f"✅ **Slot {slot} Updated!**\nSite: {site}")
                # Return to menu
                await configure_slots(client, query)
            except:
                await reply.reply_text("❌ Invalid Format! Try again.")
                await configure_slots(client, query)
    except Exception as e:
        await query.message.reply_text("❌ Timeout! Please try again.")
        await configure_slots(client, query)

@Client.on_callback_query(filters.regex(r^"del_slot#"))
async def delete_slot(client, query):
    _, chat_id, slot = query.data.split("#")
    await db.remove_shortener(chat_id, slot)
    await query.answer(f"🗑️ Slot {slot} Cleared!", show_alert=True)
    await configure_slots(client, query)

@Client.on_callback_query(filters.regex(r^"test_sl#"))
async def test_shorteners(client, query):
    await query.answer("🧪 Testing connections... (Feature in progress)", show_alert=True)

# --- BACK HOME ---
@Client.on_callback_query(filters.regex(r^"set_back_home"))
async def back_home(client, query):
    await settings_command(client, query.message)

