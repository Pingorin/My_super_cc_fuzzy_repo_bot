import os
import logging
import time
import asyncio
import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from database.users_chats_db import db
from database.ia_filterdb import Media
import info 
from info import ADMINS, IS_VERIFY
from utils import temp, get_shortlink 
from Script import script 

# Configure Logging
logger = logging.getLogger(__name__)

# Constants
START_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg"

# --- 🛠️ HELPER FUNCTIONS ---

def get_size(size):
    """Converts bytes to human readable format."""
    if not size: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def get_status():
    """Returns greeting based on current time."""
    now = datetime.datetime.now()
    hour = now.hour
    if 0 <= hour < 12:
        return "Good Morning"
    elif 12 <= hour < 18:
        return "Good Afternoon"
    else:
        return "Good Evening"

async def send_shortener_alert(client, chat_id, site_domain):
    """Sends an alert to admins if a shortener fails."""
    try:
        try:
            chat_id_int = int(str(chat_id))
            chat = await client.get_chat(chat_id_int)
            group_name = chat.title
            group_id = chat.id
        except:
            group_name = "Unknown Group"
            group_id = chat_id

        msg = (
            f"⚠️ **Shortener Alert** ⚠️\n\n"
            f"Group: **{group_name}** (`{group_id}`).\n"
            f"Shortener: **{site_domain}** failed or is slow.\n"
            f"**Action:** Check API Key or Website Status."
        )
        for admin_id in ADMINS:
            try: await client.send_message(chat_id=int(admin_id), text=msg)
            except: pass
    except: pass

async def get_active_shorteners(chat_id):
    """Fetches active shorteners for the group or defaults."""
    group_settings = await db.get_group_settings(chat_id)
    if group_settings:
        group_shorteners = group_settings.get('shorteners', {})
        active = {}
        if group_shorteners.get('1'): active['1'] = group_shorteners['1']
        if group_shorteners.get('2'): active['2'] = group_shorteners['2']
        if group_shorteners.get('3'): active['3'] = group_shorteners['3']
        if active: return active

    default_shorteners = {}
    if info.SHORTLINK_URL_1 and info.SHORTLINK_API_1: default_shorteners['1'] = {'site': info.SHORTLINK_URL_1, 'api': info.SHORTLINK_API_1}
    if info.SHORTLINK_URL_2 and info.SHORTLINK_API_2: default_shorteners['2'] = {'site': info.SHORTLINK_URL_2, 'api': info.SHORTLINK_API_2}
    if info.SHORTLINK_URL_3 and info.SHORTLINK_API_3: default_shorteners['3'] = {'site': info.SHORTLINK_URL_3, 'api': info.SHORTLINK_API_3}
    return default_shorteners

# --- 🛠️ GROUP OBSERVER ---
@Client.on_message(filters.group, group=-1)
async def auto_save_group_handler(client, message):
    """Automatically saves group ID to database on any message."""
    try: await db.add_group(message.chat.id)
    except: pass

# --- 🔐 VERIFICATION LOGIC ---

async def grant_full_access(user_id, chat_id):
    """Grants access based on group settings (duration) and resets levels."""
    group_settings = await db.get_group_settings(chat_id)
    mode = group_settings.get('shortener_mode', 'dynamic') if group_settings else 'dynamic'
    
    if mode == 'smart': 
        duration = group_settings.get('time_smart', 86400)
    elif mode == 'together': 
        active_slots = await get_active_shorteners(chat_id)
        if len(active_slots) >= 3:
            duration = group_settings.get('time_together_3', 86400)
        else:
            duration = group_settings.get('time_together', 604800)
    else: 
        duration = group_settings.get('time_dynamic', 86400) 

    await db.update_verify_status(user_id, chat_id, 0, duration)
    await db.update_verify_status(user_id, chat_id, 1, is_reset=True)
    await db.update_verify_status(user_id, chat_id, 2, is_reset=True)
    await db.update_verify_status(user_id, chat_id, 3, is_reset=True)

async def check_verification(client, user_id, chat_id, link_id, message_obj):
    """Checks verification status and handles the flow."""
    if not IS_VERIFY: return True 
    if await db.get_verify_status(user_id, chat_id): return True 

    group_settings = await db.get_group_settings(chat_id)
    mode = group_settings.get('shortener_mode', 'dynamic') if group_settings else 'dynamic'
    active_slots = await get_active_shorteners(chat_id)
    current_time = time.time()

    if mode == 'together':
        buttons = []
        info_text = "⚠️ **Verification Required**\n\nComplete the steps below to access files:\n"
        wait_msg = await message_obj.reply_text("Generating Verification Links... ⏳")
        
        for i in ['1', '2', '3']:
            if active_slots.get(i) and await db.get_level_time(user_id, chat_id, int(i)) == 0:
                link = await generate_single_link(client, chat_id, user_id, link_id, int(i), active_slots[i])
                if link: 
                    buttons.append([InlineKeyboardButton(f"🔗 Verify Link {i} ({active_slots[i]['site']})", url=link)])
                    info_text += f"\n{i}️⃣ **Step {i}:** Remaining ❌"
                else:
                    await db.update_verify_status(user_id, chat_id, int(i), is_reset=False) 
                    info_text += f"\n{i}️⃣ **Step {i}:** ✅ Auto-Skipped (Error)"
        
        await wait_msg.delete()
        if buttons:
            await message_obj.reply_text(info_text, reply_markup=InlineKeyboardMarkup(buttons))
            return False
        else:
            await grant_full_access(user_id, chat_id)
            return True

    elif mode == 'smart':
        gap1 = group_settings.get('time_gap1', 300)
        gap2 = group_settings.get('time_gap2', 300)
        gaps = {1: gap1, 2: gap2}

        for i in [1, 2, 3]:
            if active_slots.get(str(i)):
                v_time = await db.get_level_time(user_id, chat_id, i)
                if v_time == 0:
                    res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, i, active_slots[str(i)])
                    if res == "SENT": return False
                elif active_slots.get(str(i+1)) and (v_time + gaps.get(i, 300)) > current_time: 
                    return True 

    else: 
        for i in [1, 2, 3]:
            if active_slots.get(str(i)) and await db.get_level_time(user_id, chat_id, i) == 0:
                res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, i, active_slots[str(i)])
                if res == "SENT": return False 

    await grant_full_access(user_id, chat_id)
    return True

# --- LINK GENERATORS ---

async def generate_single_link(client, chat_id, user_id, link_id, level, slot_data):
    site = slot_data['site']
    api = slot_data['api']
    verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{level}_{user_id}_{chat_id}_{link_id}"
    short_url = await get_shortlink(site, api, verify_url)
    if not short_url:
        await send_shortener_alert(client, chat_id, site)
        return None
    return short_url

async def attempt_send_link(client, user_id, chat_id, link_id, message_obj, level, slot_data):
    site = slot_data['site']
    api = slot_data['api']
    verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{level}_{user_id}_{chat_id}_{link_id}"
    wait_msg = await message_obj.reply_text(f"Generating Verification Link {level}... ⏳")
    short_url = await get_shortlink(site, api, verify_url)
    await wait_msg.delete()
    
    if short_url:
        btn = [[InlineKeyboardButton(f"🚀 Verify Level {level}", url=short_url)]]
        text = f"⚠️ **Verification Required ({level}/?)**\n\n**Shortener:** {site}\n_Click the button below to verify and continue._"
        if level == 3: text = f"⚠️ **Final Step (3/3)**\n\n**Shortener:** {site}\n_Almost there! Verify this to unlock files._"
        await message_obj.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))
        return "SENT"
    else:
        await send_shortener_alert(client, chat_id, site)
        await message_obj.reply_text(f"⚠️ **Alert:** Shortener {site} is down. Skipping Level {level}... ⏩")
        return "SKIP"

# --- 🚫 FSUB CHECK ---

async def check_fsub(client, user_id, message_obj):
    src_chat_id = None
    if len(message_obj.command) > 1:
        try:
            parts = message_obj.command[1].split("_")
            if len(parts) > 3: src_chat_id = int(parts[3]) 
            elif len(parts) > 2 and parts[0] == "get": src_chat_id = int(parts[2])
        except: pass
    
    if not src_chat_id: return True 
    group_settings = await db.get_group_settings(src_chat_id)
    if not group_settings: return True
    fsub_channels = group_settings.get('fsub_channels', {})
    if not fsub_channels: return True 

    for slot, channel_id in fsub_channels.items():
        channel_id = int(channel_id)
        try:
            member = await client.get_chat_member(channel_id, user_id)
            if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                continue 
        except: pass 

        if str(slot) != '3' and await db.is_user_pending(user_id, channel_id):
            continue 

        try:
            if str(slot) == '3':
                link_obj = await client.create_chat_invite_link(channel_id, creates_join_request=False)
                link = link_obj.invite_link
                btn_text = "📢 Join Update Channel"
                msg_text = f"⚠️ **Access Denied!**\n\nYou must **Join** our update channel to access this file."
            else:
                link_obj = await client.create_chat_invite_link(channel_id, creates_join_request=True)
                link = link_obj.invite_link
                btn_text = f"📢 Request to Join Channel"
                msg_text = f"⚠️ **Access Denied!**\n\nYou must **Request to Join** our update channel (Slot {slot}) to access this file."

            btn = [[InlineKeyboardButton(btn_text, url=link)]]
            original_param = message_obj.command[1] if len(message_obj.command) > 1 else "start"
            btn.append([InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{temp.U_NAME}?start={original_param}")])
            await message_obj.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(btn))
            return False 
        except Exception as e:
            logger.error(f"Fsub Error: {e}")
            continue
    return True

# --- 🎮 COMMAND HANDLERS ---

@Client.on_message(filters.command('settings'))
async def settings(client, message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id: return

    if message.chat.type == enums.ChatType.PRIVATE:
        msg = await message.reply_text("<b>♻️ ᴄʜᴇᴄᴋɪɴɢ ʏᴏᴜʀ ᴀᴅᴍɪɴ ʀɪɢʜᴛs ɪɴ ᴀʟʟ ɢʀᴏᴜᴘs... ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...</b>")
        
        try:
            all_chats = await db.get_all_chats()
            my_groups = []
            
            async for chat in all_chats:
                try:
                    chat_id = int(chat['id'])
                    member = await client.get_chat_member(chat_id, user_id)
                    if member.status in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
                        my_groups.append(chat)
                except Exception as e:
                    logger.debug(f"Settings check error for {chat.get('id')}: {e}")
                    pass
            
            if not my_groups:
                await msg.edit("<b>☹️ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ᴀɴʏ ɢʀᴏᴜᴘ ᴡʜᴇʀᴇ ɪ ᴀᴍ ᴘʀᴇsᴇɴᴛ.</b>")
                return
                
            btn = [[InlineKeyboardButton(f"{group['title']}", callback_data=f"open_settings#{group['id']}")] for group in my_groups]
            btn.append([InlineKeyboardButton('ᴄʟᴏsᴇ', callback_data='close_data')])
            
            await msg.edit("<b>⚙️ sᴇʟᴇᴄᴛ ᴛʜᴇ ɢʀᴏᴜᴘ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴄᴏɴғɪɢᴜʀᴇ:</b>", reply_markup=InlineKeyboardMarkup(btn))
        except Exception as e:
            await msg.edit(f"❌ Error: {e}")

@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    if message.chat.type == enums.ChatType.PRIVATE:
        await db.add_user(message.from_user.id)
        if len(message.command) > 1:
            is_allowed = await check_fsub(client, message.from_user.id, message)
            if not is_allowed: return 

    elif message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        status = get_status()
        await message.reply_text(f"<b>🔥 Yes {status},\nHow can I help you?</b>")

        if (str(message.chat.id)).startswith("-100") and not await db.get_chat(message.chat.id):
            total = await client.get_chat_members_count(message.chat.id)
            user = message.from_user.mention if message.from_user else "Unknown"
            try: group_link = await message.chat.export_invite_link()
            except: group_link = "N/A"

            if info.LOG_CHANNEL:
                try:
                    bot_info = await client.get_me()
                    msg_text = script.NEW_GROUP_TXT.format(f"https://t.me/{bot_info.username}", message.chat.title, message.chat.id, message.chat.username or "None", group_link, total, user)
                    await client.send_message(info.LOG_CHANNEL, msg_text, disable_web_page_preview=True)
                except: pass
            
            await db.add_chat(message.chat.id, message.chat.title)
        else:
            await db.add_group(message.chat.id)

        if len(message.command) == 1: return 

    # Verification Logic
    if len(message.command) > 1 and message.command[1].startswith("verify_"):
        try:
            data = message.command[1].split("_")
            level, v_id, c_id = int(data[1]), data[2], data[3]
            l_id = int(data[4]) if len(data) > 4 else 0
            
            if str(v_id) != str(message.from_user.id): return await message.reply("❌ Invalid Link!")
            
            await db.update_verify_status(message.from_user.id, c_id, level)
            if await check_verification(client, message.from_user.id, c_id, l_id, message):
                await message.reply(f"✅ **Verification Successful!**")
                if l_id != 0:
                    file_data = await Media.get_file_details(l_id)
                    search_data = await Media.search_col.find_one({'link_id': l_id})
                    if file_data:
                        caption = search_data.get('caption', f"📂 <b>{search_data.get('file_name')}</b>")
                        await client.send_cached_media(chat_id=message.from_user.id, file_id=file_data['file_id'], caption=f"{caption}\n{script.CUSTOM_FOOTER}")
            return
        except: return

    # File Retrieval Logic
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        try:
            data = message.command[1].split("_")
            l_id, s_id = int(data[1]), data[2] if len(data) > 2 else str(message.chat.id)
            if not await check_verification(client, message.from_user.id, s_id, l_id, message): return 
            file_data = await Media.get_file_details(l_id)
            search_data = await Media.search_col.find_one({'link_id': l_id})
            if file_data:
                caption = search_data.get('caption', f"📂 <b>{search_data.get('file_name')}</b>")
                await client.send_cached_media(chat_id=message.from_user.id, file_id=file_data['file_id'], caption=f"{caption}\n{script.CUSTOM_FOOTER}")
        except: pass
        return

    if message.chat.type == enums.ChatType.PRIVATE:
        text = f"Hello {message.from_user.mention} 👋,\nI am a Powerul Auto Filter Bot with Verification Support."
        buttons = [[InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')],
                   [InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'), InlineKeyboardButton('💸 ᴘʀᴇᴍɪᴜᴍ', callback_data='buy_premium')],
                   [InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛʜ ʙᴏᴛ 🚫', callback_data='earn'), InlineKeyboardButton('🤝 ʀᴇꜰᴇʀʀᴀʟ 🤝', callback_data='refer')]]
        await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command("connect") & filters.group)
async def connect_handler(client, message):
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]: return 
        await db.add_group(message.chat.id)
        await message.reply_text(f"✅ Connected: `{message.chat.id}`")
    except: pass

@Client.on_message(filters.new_chat_members)
async def new_chat(client, message):
    if (await client.get_me()).id in [u.id for u in message.new_chat_members]:
        await message.reply_text("Thanks for adding me! 👋\nPromote me to Admin and type /connect to setup.")

@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_handler(client, message):
    users, groups, files = await db.total_users_count(), await db.total_groups_count(), await Media.total_files_count()
    await message.reply(f"📊 **STATS**\n👤 Users: {users}\n👥 Groups: {groups}\n📂 Files: {files}")
