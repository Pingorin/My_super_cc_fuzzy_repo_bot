import os
import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
import info 
from info import ADMINS # ✅ Admin Import Fixed
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

# --- HELPER: DYNAMIC VERIFICATION CHECK ---
# Ye function check karega ki info.py me kitne shortener set hain
# Aur user ne kitne complete kar liye hain.
async def check_verification(client, user_id, chat_id, link_id, message_obj):
    if not info.IS_VERIFY:
        return True # System OFF

    # --- LEVEL 1 ---
    if info.SHORTLINK_URL_1 and info.SHORTLINK_API_1:
        if not await db.get_verify_status(user_id, chat_id, 1):
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_1_{user_id}_{chat_id}_{link_id}"
            
            # User ko wait karvao
            msg = await message_obj.reply_text("🔎 Checking Verification Level 1... ⏳")
            short_url = await get_shortlink(verify_url, info.SHORTLINK_URL_1, info.SHORTLINK_API_1)
            await msg.delete()
            
            btn = [[InlineKeyboardButton("🚀 Verify Level 1", url=short_url)]]
            await message_obj.reply_text(
                f"⚠️ **Verification Required (1/?)**\n\n"
                f"Is Group ke liye verification zaroori hai.\n"
                f"Pehle Level 1 complete karein.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return False # Verification incomplete

    # --- LEVEL 2 ---
    if info.SHORTLINK_URL_2 and info.SHORTLINK_API_2:
        if not await db.get_verify_status(user_id, chat_id, 2):
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_2_{user_id}_{chat_id}_{link_id}"
            
            msg = await message_obj.reply_text("🔎 Checking Verification Level 2... ⏳")
            short_url = await get_shortlink(verify_url, info.SHORTLINK_URL_2, info.SHORTLINK_API_2)
            await msg.delete()
            
            btn = [[InlineKeyboardButton("🚀 Verify Level 2", url=short_url)]]
            await message_obj.reply_text(
                f"⚠️ **Verification Required (2/?)**\n\n"
                f"✅ Level 1 Passed!\n"
                f"Ab Level 2 complete karein.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return False

    # --- LEVEL 3 ---
    if info.SHORTLINK_URL_3 and info.SHORTLINK_API_3:
        if not await db.get_verify_status(user_id, chat_id, 3):
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_3_{user_id}_{chat_id}_{link_id}"
            
            msg = await message_obj.reply_text("🔎 Checking Verification Level 3... ⏳")
            short_url = await get_shortlink(verify_url, info.SHORTLINK_URL_3, info.SHORTLINK_API_3)
            await msg.delete()
            
            btn = [[InlineKeyboardButton("🔥 Verify Level 3 (Final)", url=short_url)]]
            await message_obj.reply_text(
                f"⚠️ **Final Verification (3/3)**\n\n"
                f"✅ Level 2 Passed!\n"
                f"Ye aakhri step hai, fir file milegi.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return False

    return True # Sab levels clear hain!


@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    if message.chat.type == "private":
        await db.add_user(message.from_user.id)

    # ✅ CASE 1: Verification Return
    # Format: verify_LEVEL_USERID_CHATID_LINKID
    if len(message.command) > 1 and message.command[1].startswith("verify_"):
        try:
            data = message.command[1].split("_")
            level = int(data[1])
            verify_id = data[2]
            chat_id = data[3]
            link_id = int(data[4]) if len(data) > 4 else 0
            
            if str(verify_id) != str(message.from_user.id):
                return await message.reply("❌ Ye link apke liye nahi hai.")
            
            # 1. Update DB (Current Level ke liye)
            await db.update_verify_status(message.from_user.id, chat_id, level)

            # 2. Check Next Step (Smart Check)
            # Ye function dekhega ki kya koi aur level baki hai?
            is_all_clear = await check_verification(client, message.from_user.id, chat_id, link_id, message)
            
            if is_all_clear:
                await message.reply(
                    f"✅ **Verification Complete!**\n\n"
                    f"You are verified for **24 hours** in this group. 🚀"
                )

                # 3. Auto Send File
                if link_id != 0:
                    file_data = await Media.get_file_details(link_id)
                    search_data = await Media.search_col.find_one({'link_id': link_id})
                    
                    if not file_data:
                        return await message.reply("❌ File Database se delete ho gayi hai.")
                    
                    file_id = file_data.get('file_id')
                    if not file_id:
                        return await message.reply("❌ Error: File ID missing.")

                    db_caption = search_data.get('caption')
                    if not db_caption:
                        db_caption = f"📂 <b>{search_data.get('file_name')}</b>"
                    
                    final_caption = f"{db_caption}\n{script.CUSTOM_FOOTER}"

                    try:
                        await client.send_cached_media(
                            chat_id=message.from_user.id,
                            file_id=file_id, 
                            caption=final_caption,
                            parse_mode=enums.ParseMode.HTML
                        )
                    except Exception as e:
                        await message.reply(f"❌ Failed to send file automatically.\nError: `{e}`")
            
            return
        except Exception as e:
            return await message.reply(f"❌ Verification Error: {e}")

    # ✅ CASE 2: File Request (Get File)
    # Format: /start get_LINKID_CHATID
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        
        try:
            data = message.command[1].split("_")
            link_id = int(data[1])
            
            # Group ID nikalo
            src_chat_id = data[2] if len(data) > 2 else str(message.chat.id)
            
            # --- SMART VERIFICATION CHECK ---
            is_all_clear = await check_verification(client, message.from_user.id, src_chat_id, link_id, message)
            
            if not is_all_clear:
                return # Agar verify baki hai to yahi ruk jao

            # --- SEND FILE (Agar sab clear hai) ---
            file_data = await Media.get_file_details(link_id)
            search_data = await Media.search_col.find_one({'link_id': link_id})
            
            if not file_data:
                return await message.reply("❌ File Database se delete ho gayi hai.")
            
            file_id = file_data.get('file_id')
            
            if not file_id:
                return await message.reply("❌ Error: Is file ki ID database me nahi hai.")

            db_caption = search_data.get('caption')
            if not db_caption:
                db_caption = f"📂 <b>{search_data.get('file_name')}</b>"
            
            final_caption = f"{db_caption}\n{script.CUSTOM_FOOTER}"

            try:
                await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=file_id, 
                    caption=final_caption,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                await message.reply(f"❌ Failed to send file.\nError: `{e}`")
                    
        except Exception as e:
            await message.reply(f"❌ Error: {e}")
        return

    # ✅ CASE 3: Normal Start
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

# --- New Group Handler ---
@Client.on_message(filters.new_chat_members)
async def new_chat(client, message):
    try:
        bot_id = (await client.get_me()).id
        if bot_id in [u.id for u in message.new_chat_members]:
            await db.add_group(message.chat.id)
            await message.reply_text("Thanks for adding me! Admin bana do please.")
    except: pass

# --- Stats ---
@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_handler(client, message):
    msg = await message.reply_text("📊 Fetching...")
    try:
        users = await db.total_users_count()
        groups = await db.total_groups_count()
        files = await Media.total_files_count()
        size = get_size(await Media.get_db_size())
        await msg.edit_text(f"📊 **STATS**\nUsers: {users}\nGroups: {groups}\nFiles: {files}\nDB Size: {size}")
    except Exception as e:
        await msg.edit_text(f"Error: {e}")

# --- ADMIN COMMAND: Set Specific Shortener ---
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
    
    await message.reply(f"✅ **Level {level} Shortener Updated!**\nSite: `{site}`")
