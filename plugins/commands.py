import os
import logging
import time
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
import info 
from info import ADMINS, IS_VERIFY
from utils import temp, get_shortlink 
from Script import script 

logger = logging.getLogger(__name__)
START_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg"

def get_size(size):
    if not size: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

# --- 🛠️ AUTO-SAVE GROUP ---
@Client.on_message(filters.group, group=-1)
async def auto_save_group_handler(client, message):
    try: await db.add_group(message.chat.id)
    except: pass

# --- 🚨 ALERT SYSTEM ---
async def send_shortener_alert(client, chat_id, site_domain):
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
            f"Shortener: **{site_domain}** failed/slow.\n"
            f"**Action:** Check API Key or Website Status."
        )
        for admin_id in ADMINS:
            try: await client.send_message(chat_id=int(admin_id), text=msg)
            except: pass
    except: pass

# --- 🧠 PRIORITY LOGIC ---
async def get_active_shorteners(chat_id):
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

# --- 🧠 GRANT ACCESS ---
async def grant_full_access(user_id, chat_id):
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

# --- 🧠 VERIFICATION LOGIC ---
async def check_verification(client, user_id, chat_id, link_id, message_obj):
    if not IS_VERIFY: return True 
    if await db.get_verify_status(user_id, chat_id): return True 

    group_settings = await db.get_group_settings(chat_id)
    mode = group_settings.get('shortener_mode', 'dynamic') if group_settings else 'dynamic'
    active_slots = await get_active_shorteners(chat_id)
    current_time = time.time()

    # TOGETHER MODE
    if mode == 'together':
        buttons = []
        info_text = "⚠️ **Verification Required**\n\nComplete the steps below:\n"
        wait_msg = await message_obj.reply_text("Generating Links... ⏳")
        
        if active_slots.get('1') and await db.get_level_time(user_id, chat_id, 1) == 0:
            link = await generate_single_link(client, chat_id, user_id, link_id, 1, active_slots['1'])
            if link: 
                buttons.append([InlineKeyboardButton(f"🔗 Verify Link 1 ({active_slots['1']['site']})", url=link)])
                info_text += f"\n1️⃣ **Step 1:** Remaining"
            else:
                await db.update_verify_status(user_id, chat_id, 1, is_reset=False) 
                info_text += f"\n1️⃣ **Step 1:** ✅ Auto-Skipped"

        if active_slots.get('2') and await db.get_level_time(user_id, chat_id, 2) == 0:
            link = await generate_single_link(client, chat_id, user_id, link_id, 2, active_slots['2'])
            if link:
                buttons.append([InlineKeyboardButton(f"🔗 Verify Link 2 ({active_slots['2']['site']})", url=link)])
                info_text += f"\n2️⃣ **Step 2:** Remaining"
            else:
                await db.update_verify_status(user_id, chat_id, 2, is_reset=False)
                info_text += f"\n2️⃣ **Step 2:** ✅ Auto-Skipped"

        if active_slots.get('3') and await db.get_level_time(user_id, chat_id, 3) == 0:
            link = await generate_single_link(client, chat_id, user_id, link_id, 3, active_slots['3'])
            if link:
                buttons.append([InlineKeyboardButton(f"🔗 Verify Link 3 ({active_slots['3']['site']})", url=link)])
                info_text += f"\n3️⃣ **Step 3:** Remaining"
            else:
                await db.update_verify_status(user_id, chat_id, 3, is_reset=False)
                info_text += f"\n3️⃣ **Step 3:** ✅ Auto-Skipped"

        await wait_msg.delete()
        if buttons:
            await message_obj.reply_text(info_text, reply_markup=InlineKeyboardMarkup(buttons))
            return False
        else:
            await grant_full_access(user_id, chat_id)
            return True

    # Smart/Dynamic Mode
    elif mode == 'smart':
        gap1 = group_settings.get('time_gap1', 300)
        gap2 = group_settings.get('time_gap2', 300)

        if active_slots.get('1'):
            v1_time = await db.get_level_time(user_id, chat_id, 1)
            if v1_time == 0:
                res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 1, active_slots['1'])
                if res == "SENT": return False
            elif active_slots.get('2') and (v1_time + gap1) > current_time: return True 

        if active_slots.get('2'):
            v2_time = await db.get_level_time(user_id, chat_id, 2)
            if v2_time == 0:
                res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 2, active_slots['2'])
                if res == "SENT": return False
            elif active_slots.get('3') and (v2_time + gap2) > current_time: return True 

        if active_slots.get('3'):
            v3_time = await db.get_level_time(user_id, chat_id, 3)
            if v3_time == 0:
                res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 3, active_slots['3'])
                if res == "SENT": return False

    else: # Dynamic
        if active_slots.get('1') and await db.get_level_time(user_id, chat_id, 1) == 0:
            res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 1, active_slots['1'])
            if res == "SENT": return False 

        if active_slots.get('2') and await db.get_level_time(user_id, chat_id, 2) == 0:
            res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 2, active_slots['2'])
            if res == "SENT": return False 

        if active_slots.get('3') and await db.get_level_time(user_id, chat_id, 3) == 0:
            res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 3, active_slots['3'])
            if res == "SENT": return False 

    await grant_full_access(user_id, chat_id)
    return True

# --- LINK HELPERS ---
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
        text = f"⚠️ **Verification Required ({level}/?)**\n\n**Shortener:** {site}"
        if level == 3: text = f"⚠️ **Final Step (3/3)**\n\n**Shortener:** {site}"
        await message_obj.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))
        return "SENT"
    else:
        await send_shortener_alert(client, chat_id, site)
        await message_obj.reply_text(f"⚠️ **Alert:** {site} is down. Skipping... ⏩")
        return "SKIP"

# --- 🔥 FSUB CHECK (PER GROUP ISOLATION) 🔥 ---
async def check_fsub(client, user_id, message_obj):
    # 1. GROUP ID EXTRACT KARNA (Sabse Important)
    # Link format: https://t.me/bot?start=get_12345_-100123456789
    # Yahan "-100123456789" Group ID hai.
    src_chat_id = None
    if len(message_obj.command) > 1:
        try:
            parts = message_obj.command[1].split("_")
            if len(parts) > 3: src_chat_id = int(parts[3]) 
            elif len(parts) > 2 and parts[0] == "get": src_chat_id = int(parts[2])
        except: pass
    
    # Agar link me Group ID nahi hai, to Fsub check mat karo (skip)
    if not src_chat_id: return True 

    # 2. US SPECIFIC GROUP KI SETTINGS NIKALNA
    group_settings = await db.get_group_settings(src_chat_id)
    if not group_settings: return True
    
    fsub_channels = group_settings.get('fsub_channels', {})
    if not fsub_channels: return True 

    # 3. Check All Slots
    missing_slots = []

    for slot, channel_id in fsub_channels.items():
        channel_id = int(channel_id)
        
        # A. Member?
        is_member = False
        try:
            member = await client.get_chat_member(channel_id, user_id)
            if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                is_member = True
        except: pass 

        # B. Pending?
        is_pending = False
        if not is_member:
            if await db.is_user_pending(user_id, channel_id):
                is_pending = True

        # C. Agar Member bhi nahi aur Pending bhi nahi -> Missing list me daalo
        if not is_member and not is_pending:
            missing_slots.append((slot, channel_id))

    # 4. Agar koi missing slot hai, to Button Dikhao
    if missing_slots:
        buttons = []
        for slot, channel_id in missing_slots:
            try:
                # 
                # Join Request Link Create karo
                link_obj = await client.create_chat_invite_link(channel_id, creates_join_request=True)
                link = link_obj.invite_link
                buttons.append([InlineKeyboardButton(f"📢 Request to Join Channel {slot}", url=link)])
            except Exception as e:
                print(f"Error generating link for {channel_id}: {e}")
        
        # Try Again Button
        original_param = message_obj.command[1] if len(message_obj.command) > 1 else "start"
        buttons.append([InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{temp.U_NAME}?start={original_param}")])

        await message_obj.reply_text(
            f"⚠️ **Access Denied!**\n\n"
            f"You must request to join the following channel(s) to access this file.\n"
            f"**Note:** Click 'Request to Join', then click 'Try Again'.",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return False # Blocked

    return True # Allowed

# --- HANDLERS ---

@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    if message.chat.type == enums.ChatType.PRIVATE:
        await db.add_user(message.from_user.id)
        
        # 🛑 FSUB CHECK (First Priority)
        if len(message.command) > 1:
            is_allowed = await check_fsub(client, message.from_user.id, message)
            if not is_allowed: return 

    elif message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await db.add_group(message.chat.id)
        if len(message.command) == 1:
            return await message.reply("✅ Bot is Alive & Settings Saved!")

    # ✅ VERIFY RETURN
    if len(message.command) > 1 and message.command[1].startswith("verify_"):
        try:
            data = message.command[1].split("_")
            level = int(data[1])
            verify_id = data[2]
            chat_id = data[3]
            link_id = int(data[4]) if len(data) > 4 else 0
            if str(verify_id) != str(message.from_user.id): return await message.reply("❌ Wrong Link.")
            
            await db.update_verify_status(message.from_user.id, chat_id, level)
            is_all_clear = await check_verification(client, message.from_user.id, chat_id, link_id, message)
            
            if is_all_clear:
                await message.reply(f"✅ **Verification Successful!**\n\nAccess Granted. 📂")
                if link_id != 0:
                    file_data = await Media.get_file_details(link_id)
                    search_data = await Media.search_col.find_one({'link_id': link_id})
                    if file_data and file_data.get('file_id'):
                        caption = search_data.get('caption', f"📂 <b>{search_data.get('file_name')}</b>")
                        try: await client.send_cached_media(chat_id=message.from_user.id, file_id=file_data.get('file_id'), caption=f"{caption}\n{script.CUSTOM_FOOTER}", parse_mode=enums.ParseMode.HTML)
                        except Exception as e: await message.reply(f"❌ Error: `{e}`")
            return
        except Exception as e: return await message.reply(f"❌ Error: {e}")

    # ✅ FILE REQUEST
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        try:
            data = message.command[1].split("_")
            link_id = int(data[1])
            src_chat_id = data[2] if len(data) > 2 else str(message.chat.id)
            is_all_clear = await check_verification(client, message.from_user.id, src_chat_id, link_id, message)
            if not is_all_clear: return 

            file_data = await Media.get_file_details(link_id)
            search_data = await Media.search_col.find_one({'link_id': link_id})
            if not file_data: return await message.reply("❌ File Not Found.")
            
            caption = search_data.get('caption', f"📂 <b>{search_data.get('file_name')}</b>")
            try: await client.send_cached_media(chat_id=message.from_user.id, file_id=file_data.get('file_id'), caption=f"{caption}\n{script.CUSTOM_FOOTER}", parse_mode=enums.ParseMode.HTML)
            except Exception as e: await message.reply(f"❌ Error: `{e}`")
        except Exception as e: await message.reply(f"❌ Error: {e}")
        return

    # ✅ START MSG
    if message.chat.type == enums.ChatType.PRIVATE:
        text = f"Hello {message.from_user.mention} 👋,\nI am an Auto Filter Bot."
        buttons = [
            [InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')],
            [InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'), InlineKeyboardButton('💸 ᴘʀᴇᴍɪᴜᴍ', callback_data='buy_premium')],
            [InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛʜ ʙᴏᴛ 🚫', callback_data='earn'), InlineKeyboardButton('🤝 ʀᴇꜰᴇʀʀᴀʟ 🤝', callback_data='refer')]
        ]
        await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))

# --- COMMANDS ---
@Client.on_message(filters.command("connect") & filters.group)
async def connect_handler(client, message):
    try:
        user_id = message.from_user.id
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]: return await message.reply("❌ Admin Only.")
        await db.add_group(message.chat.id)
        await message.reply_text(f"✅ **Successfully Connected!**")
    except: pass

@Client.on_message(filters.new_chat_members)
async def new_chat(client, message):
    try:
        if (await client.get_me()).id in [u.id for u in message.new_chat_members]:
            await message.reply_text("Thanks! Promote me & type /connect")
    except: pass

@Client.on_message(filters.command("set_shortner") & filters.user(ADMINS))
async def set_shortner_dynamic(client, message): await message.reply("⚠️ Use /settings in PM.")

@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_handler(client, message):
    try:
        users = await db.total_users_count()
        groups = await db.total_groups_count()
        files = await Media.total_files_count()
        await message.reply_text(f"📊 **STATS**\nUsers: {users}\nGroups: {groups}\nFiles: {files}")
    except: pass
