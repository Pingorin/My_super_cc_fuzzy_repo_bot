import os
import logging
import time
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
import info 
from info import ADMINS, IS_VERIFY, VERIFY_TIME, VERIFY_GAP1, VERIFY_GAP2
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

# --- 🧠 HELPER: GRANT ACCESS & RESET LOOP ---
async def grant_full_access(user_id, chat_id):
    # 1. Give Full Access (Level 0) for 24 Hours
    await db.update_verify_status(user_id, chat_id, 0, VERIFY_TIME)
    
    # 2. 🔥 RESET LEVELS 1, 2, 3 🔥
    # Taki jab 24 ghante baad Level 0 expire ho, to Bot wapis V1 se shuru kare
    await db.update_verify_status(user_id, chat_id, 1, is_reset=True)
    await db.update_verify_status(user_id, chat_id, 2, is_reset=True)
    await db.update_verify_status(user_id, chat_id, 3, is_reset=True)

# --- 🧠 SMART WATERFALL LOGIC ---
async def check_verification(client, user_id, chat_id, link_id, message_obj):
    if not IS_VERIFY:
        return True 

    # 1. Check Full Access (Level 0)
    if await db.get_verify_status(user_id, chat_id):
        return True 

    current_time = time.time()

    # --- LEVEL 1 CHECK ---
    if info.SHORTLINK_URL_1 and info.SHORTLINK_API_1:
        v1_time = await db.get_level_time(user_id, chat_id, 1)
        
        if v1_time == 0:
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_1_{user_id}_{chat_id}_{link_id}"
            msg = await message_obj.reply_text("Generating Level 1 Link... ⏳")
            short_url = await get_shortlink(verify_url, info.SHORTLINK_URL_1, info.SHORTLINK_API_1)
            await msg.delete()
            
            btn = [[InlineKeyboardButton("🚀 Verify Level 1", url=short_url)]]
            await message_obj.reply_text(
                "⚠️ **Verification Required (1/?)**\n\nFile paane ke liye Step 1 complete karein.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return False
        
        # Level 1 Done. Check V2.
        if info.SHORTLINK_URL_2 and info.SHORTLINK_API_2:
            gap_left = (v1_time + VERIFY_GAP1) - current_time
            if gap_left > 0: return True 
        else:
            await grant_full_access(user_id, chat_id)
            return True

    # --- LEVEL 2 CHECK ---
    if info.SHORTLINK_URL_2 and info.SHORTLINK_API_2:
        v2_time = await db.get_level_time(user_id, chat_id, 2)
        
        if v2_time == 0:
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_2_{user_id}_{chat_id}_{link_id}"
            msg = await message_obj.reply_text("Generating Level 2 Link... ⏳")
            short_url = await get_shortlink(verify_url, info.SHORTLINK_URL_2, info.SHORTLINK_API_2)
            await msg.delete()
            
            btn = [[InlineKeyboardButton("🚀 Verify Level 2", url=short_url)]]
            await message_obj.reply_text(
                "⚠️ **Verification Expired!**\n\nLevel 1 ka time khatam.\nAb Level 2 verify karein file paane ke liye.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return False
        
        # Level 2 Done. Check V3.
        if info.SHORTLINK_URL_3 and info.SHORTLINK_API_3:
            gap_left = (v2_time + VERIFY_GAP2) - current_time
            if gap_left > 0: return True
        else:
            await grant_full_access(user_id, chat_id)
            return True

    # --- LEVEL 3 CHECK ---
    if info.SHORTLINK_URL_3 and info.SHORTLINK_API_3:
        v3_time = await db.get_level_time(user_id, chat_id, 3)
        
        if v3_time == 0:
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_3_{user_id}_{chat_id}_{link_id}"
            msg = await message_obj.reply_text("Generating Final Link... ⏳")
            short_url = await get_shortlink(verify_url, info.SHORTLINK_URL_3, info.SHORTLINK_API_3)
            await msg.delete()
            
            btn = [[InlineKeyboardButton("🔥 Verify Final Level", url=short_url)]]
            await message_obj.reply_text(
                "⚠️ **Final Verification**\n\nLevel 2 ka time khatam.\nYe aakhri step hai, fir Full Access milega.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return False

    # --- ALL STEPS DONE ---
    await grant_full_access(user_id, chat_id)
    return True


# --- HANDLERS ---

@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    # ✅ CASE 0: Register User or Group
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

    # ✅ CASE 3: Normal Start (Welcome Message)
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
        # Group Alive Msg
        await message.reply("✅ Bot is Alive & Settings Saved!")

# --- 2. CONNECT COMMAND ---
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
            f"✅ **Successfully Connected!**\n\n"
            f"I am now fully operational in **{chat_title}**.\n\n"
            f"You can now configure my settings via the `/settings` command in my PM.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Configure Settings", url=f"https://t.me/{temp.U_NAME}")]
            ])
        )
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

# --- 3. NEW GROUP ADDED HANDLER ---
@Client.on_message(filters.new_chat_members)
async def new_chat(client, message):
    try:
        bot_id = (await client.get_me()).id
        for member in message.new_chat_members:
            if member.id == bot_id:
                await message.reply_text(
                    "✅ **Thank you for adding me!**\n\n"
                    "To get started, please **promote me to an administrator**, "
                    "then type `/connect` to activate me."
                )
    except Exception as e:
        logger.error(f"Error in new_chat: {e}")

# --- ADMIN COMMANDS & STATS ---
@Client.on_message(filters.command("set_shortner") & filters.user(ADMINS))
async def set_shortner_dynamic(client, message):
    if len(message.command) < 4:
        return await message.reply("❌ **Usage:** `/set_shortner <1/2/3> website.com api_key`")
    level = message.command[1]
    site = message.command[2]
    api = message.command[3]
    
    if level == "1":
        info.SHORTLINK_URL_1 = site
        info.SHORTLINK_API_1 = api
    elif level == "2":
        info.SHORTLINK_URL_2 = site
        info.SHORTLINK_API_2 = api
    elif level == "3":
        info.SHORTLINK_URL_3 = site
        info.SHORTLINK_API_3 = api
    else:
        return await message.reply("❌ Level must be 1, 2, or 3.")
    await message.reply(f"✅ **Level {level} Updated!**\nSite: `{site}`")

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
