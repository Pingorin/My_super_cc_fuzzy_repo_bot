import logging
import time
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.errors import UserNotParticipant
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
    
    # Determine Duration
    if mode == 'smart': 
        duration = group_settings.get('time_smart', 86400)
    elif mode == 'together': 
        active_slots = await get_active_shorteners(chat_id)
        if len(active_slots) >= 3:
            duration = group_settings.get('time_together_3', 86400) # 3 Links
        else:
            duration = group_settings.get('time_together', 604800) # 1-2 Links
    else: 
        duration = group_settings.get('time_dynamic', 86400) 

    # Set Verified Status
    await db.update_verify_status(user_id, chat_id, 0, duration)
    
    # Reset Individual Levels for next cycle
    await db.update_verify_status(user_id, chat_id, 1, is_reset=True)
    await db.update_verify_status(user_id, chat_id, 2, is_reset=True)
    await db.update_verify_status(user_id, chat_id, 3, is_reset=True)

async def check_verification(client, user_id, chat_id, link_id, message_obj):
    """Checks verification status and handles the flow (Together/Smart/Dynamic)."""
    if not IS_VERIFY: return True 
    if await db.get_verify_status(user_id, chat_id): return True 

    group_settings = await db.get_group_settings(chat_id)
    mode = group_settings.get('shortener_mode', 'dynamic') if group_settings else 'dynamic'
    active_slots = await get_active_shorteners(chat_id)
    current_time = time.time()

    # --- MODE: TOGETHER (All Links in One Message) ---
    if mode == 'together':
        buttons = []
        info_text = "⚠️ **Verification Required**\n\nComplete the steps below to access files:\n"
        wait_msg = await message_obj.reply_text("Generating Verification Links... ⏳")
        
        # Slot 1
        if active_slots.get('1') and await db.get_level_time(user_id, chat_id, 1) == 0:
            link = await generate_single_link(client, chat_id, user_id, link_id, 1, active_slots['1'])
            if link: 
                buttons.append([InlineKeyboardButton(f"🔗 Verify Link 1 ({active_slots['1']['site']})", url=link)])
                info_text += f"\n1️⃣ **Step 1:** Remaining ❌"
            else:
                await db.update_verify_status(user_id, chat_id, 1, is_reset=False) 
                info_text += f"\n1️⃣ **Step 1:** ✅ Auto-Skipped (Error)"

        # Slot 2
        if active_slots.get('2') and await db.get_level_time(user_id, chat_id, 2) == 0:
            link = await generate_single_link(client, chat_id, user_id, link_id, 2, active_slots['2'])
            if link:
                buttons.append([InlineKeyboardButton(f"🔗 Verify Link 2 ({active_slots['2']['site']})", url=link)])
                info_text += f"\n2️⃣ **Step 2:** Remaining ❌"
            else:
                await db.update_verify_status(user_id, chat_id, 2, is_reset=False)
                info_text += f"\n2️⃣ **Step 2:** ✅ Auto-Skipped (Error)"

        # Slot 3
        if active_slots.get('3') and await db.get_level_time(user_id, chat_id, 3) == 0:
            link = await generate_single_link(client, chat_id, user_id, link_id, 3, active_slots['3'])
            if link:
                buttons.append([InlineKeyboardButton(f"🔗 Verify Link 3 ({active_slots['3']['site']})", url=link)])
                info_text += f"\n3️⃣ **Step 3:** Remaining ❌"
            else:
                await db.update_verify_status(user_id, chat_id, 3, is_reset=False)
                info_text += f"\n3️⃣ **Step 3:** ✅ Auto-Skipped (Error)"

        await wait_msg.delete()

        if buttons:
            await message_obj.reply_text(info_text, reply_markup=InlineKeyboardMarkup(buttons))
            return False
        else:
            await grant_full_access(user_id, chat_id)
            return True

    # --- MODE: SMART (Time Gap between Links) ---
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

    # --- MODE: DYNAMIC (Sequential Links) ---
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

# --- 🚫 FSUB CHECK (SMART & STRICT RESTART PROOF) ---

async def check_fsub(client, user_id, message_obj):
    # 1. Parse Source Chat ID
    src_chat_id = None
    if len(message_obj.command) > 1:
        try:
            parts = message_obj.command[1].split("_")
            if len(parts) >= 3:
                src_chat_id = int(parts[-1]) 
        except: pass
    
    if not src_chat_id: return True

    # 2. Database se Settings Nikalo
    group_data = await db.get_group_settings(src_chat_id)
    if not group_data: return True

    # Check Slot '1' by default
    fsub_channels = group_data.get('fsub_channels', {})
    fsub_id = fsub_channels.get('1')

    if not fsub_id: return True 

    try:
        fsub_id = int(fsub_id)
        
        # --- 🛡️ CHECKING LOGIC ---
        try:
            # Step A: Direct Check
            member = await client.get_chat_member(fsub_id, user_id)
        
        except UserNotParticipant:
            # User is NOT in channel -> Block & Send Link
            return await send_join_link(client, message_obj, fsub_id)
            
        except Exception as e:
            # Step B: Technical Error (Restart/PeerInvalid/Connection)
            try:
                await client.get_chat(fsub_id) # 🔄 Refresh Peer Cache
                member = await client.get_chat_member(fsub_id, user_id) # Retry
            except UserNotParticipant:
                return await send_join_link(client, message_obj, fsub_id)
            except Exception as e2:
                # Step C: Still failing? Block to be safe.
                print(f"Technical Fsub Error: {e2}")
                return await send_join_link(client, message_obj, fsub_id)

        # Step D: Status Check
        if member.status in [
            enums.ChatMemberStatus.MEMBER, 
            enums.ChatMemberStatus.ADMINISTRATOR, 
            enums.ChatMemberStatus.OWNER,
            enums.ChatMemberStatus.RESTRICTED 
        ]:
            return True # Access Granted
        
        # If Left/Kicked -> Send Link
        return await send_join_link(client, message_obj, fsub_id)

    except Exception as e:
        print(f"Critical Fsub Logic Error: {e}")
        return await send_join_link(client, message_obj, fsub_id)

# --- Helper Function to Send Link ---
async def send_join_link(client, message_obj, channel_id):
    try:
        # creates_join_request=True -> Admin Approval Mode
        invite_link = await client.create_chat_invite_link(channel_id, creates_join_request=True)
        
        btn = [
            [InlineKeyboardButton("📢 Request to Join Channel", url=invite_link.invite_link)],
            [InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{temp.U_NAME}?start={message_obj.command[1]}")]
        ]
        await message_obj.reply_text(
            "⚠️ **Access Denied!**\n\n"
            "You must **Request to Join** our update channel to access this file.\n"
            "Click the button below and wait for approval.",
            reply_markup=InlineKeyboardMarkup(btn)
        )
        return False
    except Exception as e:
        print(f"Link Gen Error: {e}")
        return True # If link generation fails, let user pass

# --- 🎮 COMMAND HANDLERS ---

# 1. SET FSUB COMMAND (UPDATED & FIXED)
@Client.on_message(filters.command("set_fsub") & filters.group)
async def set_fsub_command(client, message):
    # 1. Admin Check
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
        return await message.reply("❌ Sirf Admins ye command use kar sakte hain.")

    # 2. Input Check
    if len(message.command) < 2:
        return await message.reply("⚠️ **Usage:** `/set_fsub -100xxxxxxx`\n(Channel ID daalein)")

    try:
        channel_id = int(message.command[1])
    except:
        return await message.reply("❌ Invalid ID! ID sirf numbers me honi chahiye (e.g. -100...).")

    # 3. Channel Admin Check (Sabse Zaruri)
    msg = await message.reply("🔎 Checking Channel...")
    try:
        chat = await client.get_chat(channel_id)
        bot_member = await client.get_chat_member(channel_id, "me")
        
        if bot_member.status != enums.ChatMemberStatus.ADMINISTRATOR:
            return await msg.edit(f"❌ **Error:** Main us Channel (`{chat.title}`) me Admin nahi hoon.\nPehle mujhe wahan Admin banayein.")
            
    except Exception as e:
        return await msg.edit(f"❌ **Error:** Main us channel ko access nahi kar pa raha.\nCheck karein ki kya main wahan add hoon?\nError: `{e}`")

    # 4. Save to DB (Slot '1')
    try:
        await db.update_fsub_channel(message.chat.id, "1", channel_id)
        await msg.edit(f"✅ **Success!**\nForce Subscribe Channel set to: **{chat.title}**\nID: `{channel_id}`")
    except Exception as e:
        await msg.edit(f"❌ Database Error: {e}")

# 2. REMOVE FSUB COMMAND (NEW)
@Client.on_message(filters.command(["del_fsub", "remove_fsub"]) & filters.group)
async def remove_fsub_manual(client, message):
    # 1. Admin Check
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
        return await message.reply("❌ Sirf Admins ye command use kar sakte hain.")

    # 2. Remove from DB
    try:
        await db.remove_fsub_channel(message.chat.id, "1")
        await message.reply("🗑️ **Success!**\nForce Subscribe Channel remove kar diya gaya hai.")
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

# 3. START COMMAND
@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    # --- Private Chat Logic ---
    if message.chat.type == enums.ChatType.PRIVATE:
        await db.add_user(message.from_user.id)
        
        # 🛑 FSUB CHECK (First Priority)
        if len(message.command) > 1:
            is_allowed = await check_fsub(client, message.from_user.id, message)
            if not is_allowed: return 

    # --- Group Chat Logic ---
    elif message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await db.add_group(message.chat.id)
        if len(message.command) == 1:
            return await message.reply("✅ Bot is Alive & Settings Saved!")

    # ✅ VERIFICATION RETURN LOGIC (verify_level_userid_chatid_linkid)
    if len(message.command) > 1 and message.command[1].startswith("verify_"):
        try:
            data = message.command[1].split("_")
            level = int(data[1])
            verify_id = data[2]
            chat_id = data[3]
            link_id = int(data[4]) if len(data) > 4 else 0
            
            if str(verify_id) != str(message.from_user.id): 
                return await message.reply("❌ **Invalid Link!** This link is not for you.")
            
            # Update DB that this level is done
            await db.update_verify_status(message.from_user.id, chat_id, level)
            
            # Check if more verification is needed
            is_all_clear = await check_verification(client, message.from_user.id, chat_id, link_id, message)
            
            if is_all_clear:
                await message.reply(f"✅ **Verification Successful!**\n\nAccess Granted. 📂")
                if link_id != 0:
                    file_data = await Media.get_file_details(link_id)
                    search_data = await Media.search_col.find_one({'link_id': link_id})
                    if file_data and file_data.get('file_id'):
                        caption = search_data.get('caption', f"📂 <b>{search_data.get('file_name')}</b>")
                        try: await client.send_cached_media(chat_id=message.from_user.id, file_id=file_data.get('file_id'), caption=f"{caption}\n{script.CUSTOM_FOOTER}", parse_mode=enums.ParseMode.HTML)
                        except Exception as e: await message.reply(f"❌ Error sending file: `{e}`")
            return
        except Exception as e: return await message.reply(f"❌ Error during verification: {e}")

    # ✅ FILE RETRIEVAL LOGIC (get_linkid_chatid)
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        try:
            data = message.command[1].split("_")
            link_id = int(data[1])
            src_chat_id = data[2] if len(data) > 2 else str(message.chat.id)
            
            # Check Verification Status
            is_all_clear = await check_verification(client, message.from_user.id, src_chat_id, link_id, message)
            if not is_all_clear: return 

            # Send File
            file_data = await Media.get_file_details(link_id)
            search_data = await Media.search_col.find_one({'link_id': link_id})
            if not file_data: return await message.reply("❌ **File Not Found.** It may have been deleted.")
            
            caption = search_data.get('caption', f"📂 <b>{search_data.get('file_name')}</b>")
            try: await client.send_cached_media(chat_id=message.from_user.id, file_id=file_data.get('file_id'), caption=f"{caption}\n{script.CUSTOM_FOOTER}", parse_mode=enums.ParseMode.HTML)
            except Exception as e: await message.reply(f"❌ Error sending file: `{e}`")
        except Exception as e: await message.reply(f"❌ Error: {e}")
        return

    # ✅ STANDARD START MESSAGE
    if message.chat.type == enums.ChatType.PRIVATE:
        text = f"Hello {message.from_user.mention} 👋,\nI am a Powerul Auto Filter Bot with Verification Support."
        buttons = [
            [InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')],
            [InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'), InlineKeyboardButton('💸 ᴘʀᴇᴍɪᴜᴍ', callback_data='buy_premium')],
            [InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛʜ ʙᴏᴛ 🚫', callback_data='earn'), InlineKeyboardButton('🤝 ʀᴇꜰᴇʀʀᴀʟ 🤝', callback_data='refer')]
        ]
        await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command("connect") & filters.group)
async def connect_handler(client, message):
    try:
        user_id = message.from_user.id
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]: return await message.reply("❌ **Admin Only.** You cannot use this.")
        await db.add_group(message.chat.id)
        await message.reply_text(f"✅ **Successfully Connected!**\nGroup ID: `{message.chat.id}` saved.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@Client.on_message(filters.new_chat_members)
async def new_chat(client, message):
    try:
        if (await client.get_me()).id in [u.id for u in message.new_chat_members]:
            await message.reply_text("Thanks for adding me! 👋\n\nPromote me to Admin and type /connect to setup.")
    except: pass

@Client.on_message(filters.command("set_shortner") & filters.user(ADMINS))
async def set_shortner_dynamic(client, message): 
    await message.reply("⚠️ This command is deprecated. Please use /settings in PM to configure shorteners.")

@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_handler(client, message):
    try:
        msg = await message.reply("Fetching stats...")
        users = await db.total_users_count()
        groups = await db.total_groups_count()
        files = await Media.total_files_count()
        await msg.edit(f"📊 **BOT STATISTICS**\n\n👤 **Users:** {users}\n👥 **Groups:** {groups}\n📂 **Files Indexed:** {files}")
    except Exception as e: 
        await message.reply(f"Error: {e}")
