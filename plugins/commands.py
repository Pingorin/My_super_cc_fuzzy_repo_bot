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

# --- 🧠 PRIORITY LOGIC HELPER ---
async def get_active_shorteners(chat_id):
    """
    Decides whether to use Group Settings (Priority 1) or Default Info (Priority 2).
    """
    # 1. Check Group Database
    group_settings = await db.get_group_settings(chat_id)
    
    if group_settings:
        group_shorteners = group_settings.get('shorteners', {})
        # Agar Group me EK BHI shortener set hai (Slot 1, 2, ya 3)
        if group_shorteners and (group_shorteners.get('1') or group_shorteners.get('2') or group_shorteners.get('3')):
            return group_shorteners # ✅ Use Group Custom Settings

    # 2. Fallback to Default (Info.py)
    default_shorteners = {}
    
    if info.SHORTLINK_URL_1 and info.SHORTLINK_API_1:
        default_shorteners['1'] = {'site': info.SHORTLINK_URL_1, 'api': info.SHORTLINK_API_1}
    
    if info.SHORTLINK_URL_2 and info.SHORTLINK_API_2:
        default_shorteners['2'] = {'site': info.SHORTLINK_URL_2, 'api': info.SHORTLINK_API_2}
        
    if info.SHORTLINK_URL_3 and info.SHORTLINK_API_3:
        default_shorteners['3'] = {'site': info.SHORTLINK_URL_3, 'api': info.SHORTLINK_API_3}

    return default_shorteners # ✅ Use Default Info

# --- 🧠 HELPER: GRANT ACCESS & RESET LOOP ---
async def grant_full_access(user_id, chat_id):
    """
    Grants access based on the configured Time Mode and Resets levels for the next loop.
    """
    group_settings = await db.get_group_settings(chat_id)
    mode = group_settings.get('shortener_mode', 'dynamic') if group_settings else 'dynamic'
    
    # Decide Duration based on Mode
    if mode == 'smart':
        duration = group_settings.get('time_smart', 86400) # Default 24h
    else:
        # Dynamic & Together use this time
        duration = group_settings.get('time_dynamic', 86400) 

    # 1. Give Full Access (Level 0)
    await db.update_verify_status(user_id, chat_id, 0, duration)
    
    # 2. 🔥 RESET LEVELS 1, 2, 3 🔥
    # Taki jab cycle expire ho, to Bot wapis V1 se shuru kare
    await db.update_verify_status(user_id, chat_id, 1, is_reset=True)
    await db.update_verify_status(user_id, chat_id, 2, is_reset=True)
    await db.update_verify_status(user_id, chat_id, 3, is_reset=True)

# --- 🧠 MASTER VERIFICATION LOGIC ---
async def check_verification(client, user_id, chat_id, link_id, message_obj):
    if not IS_VERIFY:
        return True 

    # 1. Check Full Access (Level 0)
    if await db.get_verify_status(user_id, chat_id):
        return True 

    # 🔥 Get Settings & Active Shorteners
    group_settings = await db.get_group_settings(chat_id)
    mode = group_settings.get('shortener_mode', 'dynamic') if group_settings else 'dynamic'
    active_slots = await get_active_shorteners(chat_id)
    current_time = time.time()

    # ==================================================================
    # 🌟 MODE 1: SMART (Waterfall with Gaps)
    # ==================================================================
    if mode == 'smart':
        gap1 = group_settings.get('time_gap1', 300) # Default 5 mins
        gap2 = group_settings.get('time_gap2', 300)

        # -- Slot 1 --
        if active_slots.get('1'):
            v1_time = await db.get_level_time(user_id, chat_id, 1)
            
            if v1_time == 0:
                # Try Generating Link
                res = await attempt_send_link(user_id, chat_id, link_id, message_obj, 1, active_slots['1'])
                if res == "SENT": return False
                # If res == "SKIP", code continues to Slot 2
            
            # Check Gap 1 (Only if Slot 2 exists)
            elif active_slots.get('2'):
                if (v1_time + gap1) > current_time: return True # Gap Valid -> Access

        # -- Slot 2 --
        if active_slots.get('2'):
            v2_time = await db.get_level_time(user_id, chat_id, 2)
            
            if v2_time == 0:
                res = await attempt_send_link(user_id, chat_id, link_id, message_obj, 2, active_slots['2'])
                if res == "SENT": return False
                # If res == "SKIP", code continues to Slot 3
            
            # Check Gap 2 (Only if Slot 3 exists)
            elif active_slots.get('3'):
                if (v2_time + gap2) > current_time: return True # Gap Valid -> Access

        # -- Slot 3 --
        if active_slots.get('3'):
            v3_time = await db.get_level_time(user_id, chat_id, 3)
            
            if v3_time == 0:
                res = await attempt_send_link(user_id, chat_id, link_id, message_obj, 3, active_slots['3'])
                if res == "SENT": return False

    # ==================================================================
    # 🚀 MODE 2: DYNAMIC (Sequential - No Gaps)
    # 1 -> verify -> 2 -> verify -> 3 -> verify -> Access
    # ==================================================================
    else: 
        # -- Slot 1 --
        if active_slots.get('1'):
            # Only check if not verified yet
            if await db.get_level_time(user_id, chat_id, 1) == 0:
                res = await attempt_send_link(user_id, chat_id, link_id, message_obj, 1, active_slots['1'])
                if res == "SENT": return False 
                # If res == "SKIP", it falls through immediately to Slot 2

        # -- Slot 2 --
        if active_slots.get('2'):
            if await db.get_level_time(user_id, chat_id, 2) == 0:
                res = await attempt_send_link(user_id, chat_id, link_id, message_obj, 2, active_slots['2'])
                if res == "SENT": return False 

        # -- Slot 3 --
        if active_slots.get('3'):
            if await db.get_level_time(user_id, chat_id, 3) == 0:
                res = await attempt_send_link(user_id, chat_id, link_id, message_obj, 3, active_slots['3'])
                if res == "SENT": return False 

    # --- ALL STEPS DONE ---
    await grant_full_access(user_id, chat_id)
    return True

# --- HELPER: ATTEMPT TO SEND LINK (WITH AUTO-SKIP) ---
async def attempt_send_link(user_id, chat_id, link_id, message_obj, level, slot_data):
    """
    Tries to generate a link.
    Returns: "SENT" if successful, "SKIP" if site is down.
    """
    site = slot_data['site']
    api = slot_data['api']
    
    verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{level}_{user_id}_{chat_id}_{link_id}"
    
    # Send "Checking" message
    wait_msg = await message_obj.reply_text(f"Generating Verification Link {level}... ⏳")
    
    # Try Generating
    short_url = await get_shortlink(site, api, verify_url)
    await wait_msg.delete()
    
    if short_url:
        # ✅ SUCCESS
        btn = [[InlineKeyboardButton(f"🚀 Verify Level {level}", url=short_url)]]
        
        # Custom Texts
        if level == 1:
            text = f"⚠️ **Verification Required (1/?)**\n\n**Shortener:** {site}\nFile paane ke liye Step 1 complete karein."
        elif level == 2:
            text = f"⚠️ **Level 1 Verified! ✅**\n\n**Shortener:** {site}\nAb Level 2 complete karein."
        else:
            text = f"⚠️ **Final Step (3/3)**\n\n**Shortener:** {site}\nYe aakhri step hai."

        await message_obj.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))
        return "SENT"
    
    else:
        # ❌ FAIL (AUTO-SKIP)
        await message_obj.reply_text(f"⚠️ **Alert:** {site} is down or invalid. Skipping this step...")
        return "SKIP"


# --- HANDLERS ---

@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    # ✅ CASE 0: Register
    if message.chat.type == enums.ChatType.PRIVATE:
        await db.add_user(message.from_user.id)
    elif message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await db.add_group(message.chat.id)

    # ✅ CASE 1: Verification Return
    if len(message.command) > 1 and message.command[1].startswith("verify_"):
        try:
            data = message.command[1].split("_")
            level = int(data[1])
            verify_id = data[2]
            chat_id = data[3]
            link_id = int(data[4]) if len(data) > 4 else 0
            
            if str(verify_id) != str(message.from_user.id):
                return await message.reply("❌ Ye link apke liye nahi hai.")
            
            # Update Database
            await db.update_verify_status(message.from_user.id, chat_id, level)

            # Check Next Step
            is_all_clear = await check_verification(client, message.from_user.id, chat_id, link_id, message)
            
            if is_all_clear:
                await message.reply(f"✅ **Verification Successful!**\n\nAapko file access mil gaya hai. 📂")
                
                # Auto Send File
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

    # ✅ CASE 2: File Request
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        try:
            data = message.command[1].split("_")
            link_id = int(data[1])
            src_chat_id = data[2] if len(data) > 2 else str(message.chat.id)
            
            # Smart Check
            is_all_clear = await check_verification(client, message.from_user.id, src_chat_id, link_id, message)
            
            if not is_all_clear:
                return 

            # Send File
            file_data = await Media.get_file_details(link_id)
            search_data = await Media.search_col.find_one({'link_id': link_id})
            if not file_data: return await message.reply("❌ File Database se delete ho gayi hai.")
            file_id = file_data.get('file_id')
            if not file_id: return await message.reply("❌ Error: File ID missing.")

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

    # ✅ CASE 3: Start Message
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
    else:
        await message.reply("✅ Bot is Alive & Settings Saved!")

# --- CONNECT & NEW CHAT ---
@Client.on_message(filters.command("connect") & filters.group)
async def connect_handler(client, message):
    try:
        user_id = message.from_user.id
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]:
            return await message.reply("❌ **Only Group Admins can use this command!**")

        await db.add_group(message.chat.id)
        chat_title = message.chat.title
        await message.reply_text(
            f"✅ **Successfully Connected!**\n\nI am now operational in **{chat_title}**.\nConfigure me in PM using /settings",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⚙️ Settings", url=f"https://t.me/{temp.U_NAME}")]])
        )
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
    await message.reply("⚠️ Note: Use /settings in PM for Group-Specific Settings.")

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
