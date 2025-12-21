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

# --- 🛠️ AUTO-SAVE GROUP (GROUP OBSERVER) ---
@Client.on_message(filters.group, group=-1)
async def auto_save_group_handler(client, message):
    try: await db.add_group(message.chat.id)
    except: pass

# --- 🚨 HELPER: SEND ALERT TO ADMIN ---
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
            f"Shortener **{site_domain}** failed to respond.\n"
            f"**Action:** Check configuration."
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
    active_slots = await get_active_shorteners(chat_id)
    count = len(active_slots)

    if mode == 'smart': duration = group_settings.get('time_smart', 86400)
    elif mode == 'together': 
        if count >= 3: duration = group_settings.get('time_together_3', 86400)
        else: duration = group_settings.get('time_together', 604800)
    else: duration = group_settings.get('time_dynamic', 86400) 

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
        info_text = "⚠️ **Verification Required**\n\nComplete steps to access:\n"
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

    # SMART MODE
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

    # DYNAMIC MODE
    else: 
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
        
        if level == 1:
            text = f"⚠️ **Verification Required (1/?)**\n\n**Shortener:** {site}\nFile paane ke liye Step 1 complete karein."
        elif level == 2:
            text = f"⚠️ **Level 1 Verified! ✅**\n\n**Shortener:** {site}\nAb Level 2 complete karein."
        else:
            text = f"⚠️ **Final Step (3/3)**\n\n**Shortener:** {site}\nYe aakhri step hai."
            
        await message_obj.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))
        return "SENT"
    else:
        # ❌ FAILED (ALERT ADMIN & SKIP)
        await send_shortener_alert(client, chat_id, site)
        await message_obj.reply_text(f"⚠️ **Alert:** {site} is down or invalid. Skipping this step... ⏩")
        return "SKIP"

# --- 🔥 PER-GROUP FSUB CHECK LOGIC 🔥 ---
async def check_fsub(client, user_id, message_obj):
    # 1. Identify Source Group from Start Command
    src_chat_id = None
    if len(message_obj.command) > 1:
        try:
            # Format: start=verify_level_userid_CHATID_linkid OR start=get_linkid_CHATID
            parts = message_obj.command[1].split("_")
            if len(parts) > 3: src_chat_id = int(parts[3]) 
            elif len(parts) > 2 and parts[0] == "get": src_chat_id = int(parts[2])
        except: pass
    
    if not src_chat_id: return True # No group context, allow.

    # 2. Fetch Group Settings
    group_settings = await db.get_group_settings(src_chat_id)
    if not group_settings: return True
    
    fsub_channels = group_settings.get('fsub_channels', {})
    if not fsub_channels: return True # No Fsub set

    # 3. Check Slots 1, 2, 3
    for slot, channel_id in fsub_channels.items():
        channel_id = int(channel_id)
        
        # A. Check Member Status
        try:
            member = await client.get_chat_member(channel_id, user_id)
            if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                continue # Joined
        except: pass 

        # B. Check Pending (Requested) Status
        if await db.is_user_pending(user_id, channel_id):
            continue # Requested

        # C. Not Joined & Not Pending -> BLOCK
        try:
            chat_info = await client.get_chat(channel_id)
            link = chat_info.invite_link or await client.export_chat_invite_link(channel_id)
            
            btn = [[InlineKeyboardButton(f"📢 Request to Join Channel {slot}", url=link)]]
            original_param = message_obj.command[1] if len(message_obj.command) > 1 else "start"
            btn.append([InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{temp.U_NAME}?start={original_param}")])

            await message_obj.reply_text(
                f"⚠️ **Access Denied!**\n\n"
                f"You must join our channel (Slot {slot}) to access this file.\n"
                f"**Note:** Click 'Request to Join' and then 'Try Again'.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return False # Stop here

        except Exception as e:
            print(f"Fsub Error: {e}")
            continue

    return True

# --- HANDLERS ---

@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    # ✅ Step 0: Register User & Group
    if message.chat.type == enums.ChatType.PRIVATE:
        await db.add_user(message.from_user.id)
        
        # 🔥 FSUB CHECK LOGIC (Executed BEFORE Verification) 🔥
        if len(message.command) > 1:
            is_allowed = await check_fsub(client, message.from_user.id, message)
            if not is_allowed: return # Stop execution here

    elif message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await db.add_group(message.chat.id)
        if len(message.command) == 1:
            return await message.reply("✅ Bot is Alive & Settings Saved!")

    # ✅ Step 1: Verification Return
    if len(message.command) > 1 and message.command[1].startswith("verify_"):
        try:
            data = message.command[1].split("_")
            level = int(data[1])
            verify_id = data[2]
            chat_id = data[3]
            link_id = int(data[4]) if len(data) > 4 else 0
            
            if str(verify_id) != str(message.from_user.id):
                return await message.reply("❌ Ye link apke liye nahi hai.")
            
            await db.update_verify_status(message.from_user.id, chat_id, level)
            is_all_clear = await check_verification(client, message.from_user.id, chat_id, link_id, message)
            
            if is_all_clear:
                await message.reply(f"✅ **Verification Successful!**\n\nAapko file access mil gaya hai. 📂")
                if link_id != 0:
                    file_data = await Media.get_file_details(link_id)
                    search_data = await Media.search_col.find_one({'link_id': link_id})
                    if file_data and file_data.get('file_id'):
                        db_caption = search_data.get('caption', f"📂 <b>{search_data.get('file_name')}</b>")
                        final_caption = f"{db_caption}\n{script.CUSTOM_FOOTER}"
                        try:
                            await client.send_cached_media(
                                chat_id=message.from_user.id,
                                file_id=file_data.get('file_id'), 
                                caption=final_caption,
                                parse_mode=enums.ParseMode.HTML
                            )
                        except Exception as e:
                            await message.reply(f"❌ Error: `{e}`")
            return
        except Exception as e:
            return await message.reply(f"❌ Verification Error: {e}")

    # ✅ Step 2: File Request
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        try:
            data = message.command[1].split("_")
            link_id = int(data[1])
            src_chat_id = data[2] if len(data) > 2 else str(message.chat.id)
            
            is_all_clear = await check_verification(client, message.from_user.id, src_chat_id, link_id, message)
            
            if not is_all_clear:
                return 

            file_data = await Media.get_file_details(link_id)
            search_data = await Media.search_col.find_one({'link_id': link_id})
            if not file_data: return await message.reply("❌ File Database se delete ho gayi hai.")
            file_id = file_data.get('file_id')

            db_caption = search_data.get('caption', f"📂 <b>{search_data.get('file_name')}</b>")
            final_caption = f"{db_caption}\n{script.CUSTOM_FOOTER}"

            try:
                await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=file_id, 
                    caption=final_caption,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                await message.reply(f"❌ Error: `{e}`")
        except Exception as e:
            await message.reply(f"❌ Error: {e}")
        return

    # ✅ Step 3: Normal Start (Welcome Message)
    if message.chat.type == enums.ChatType.PRIVATE:
        text = f"""Hello {message.from_user.mention} 👋,

Main ek **Auto Filter Bot** hu. 
Muje apne group me add karo movies aur series provide karne ke liye.

Niche diye gaye buttons check karein 👇"""

        buttons = [[
            InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')
        ],[
            InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'),
            InlineKeyboardButton('💸 ᴘʀᴇᴍɪᴜᴍ', callback_data='buy_premium')
        ],[
            InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛʜ ʙᴏᴛ 🚫', callback_data='earn'),
            InlineKeyboardButton('🤝 ʀᴇꜰᴇʀʀᴀʟ 🤝', callback_data='refer')
        ]]
        
        await message.reply_photo(
            photo=START_IMG,
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# --- COMMANDS ---
@Client.on_message(filters.command("connect") & filters.group)
async def connect_handler(client, message):
    try:
        user_id = message.from_user.id
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
            return await message.reply("❌ **Only Group Admins can use this command!**")
        await db.add_group(message.chat.id)
        chat_title = message.chat.title
        await message.reply_text(f"✅ **Successfully Connected to {chat_title}!**")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@Client.on_message(filters.new_chat_members)
async def new_chat(client, message):
    try:
        bot_id = (await client.get_me()).id
        for member in message.new_chat_members:
            if member.id == bot_id:
                await message.reply_text("Thanks for adding me! Promote me & type /connect")
    except: pass

@Client.on_message(filters.command("set_shortner") & filters.user(ADMINS))
async def set_shortner_dynamic(client, message):
    await message.reply("⚠️ Use /settings in PM.")

@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_handler(client, message):
    try:
        users = await db.total_users_count()
        groups = await db.total_groups_count()
        files = await Media.total_files_count()
        size = get_size(await Media.get_db_size())
        await message.reply_text(f"📊 **STATS**\nUsers: {users}\nGroups: {groups}\nFiles: {files}\nDB Size: {size}")
    except Exception as e:
        await message.reply_text(f"Error: {e}")
