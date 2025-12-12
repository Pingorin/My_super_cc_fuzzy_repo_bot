import os
import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
import info 
from info import ADMINS # ✅ FIXED: Explicitly imported ADMINS
from utils import temp, get_shortlink 
from Script import script 

logger = logging.getLogger(__name__)
START_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg"

# --- HELPER: CHECK NEXT VERIFICATION ---
async def check_verification(client, user_id, chat_id, link_id, message_obj):
    if not info.IS_VERIFY:
        return True 

    # --- LEVEL 1 CHECK ---
    if info.SHORTLINK_URL_1 and info.SHORTLINK_API_1:
        if not await db.get_verify_status(user_id, chat_id, 1):
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_1_{user_id}_{chat_id}_{link_id}"
            
            processing_msg = await message_obj.reply_text("🔎 Checking Verification Level 1... ⏳")
            short_url = await get_shortlink(verify_url, info.SHORTLINK_URL_1, info.SHORTLINK_API_1)
            await processing_msg.delete()
            
            btn = [[InlineKeyboardButton("Verify Level 1", url=short_url)]]
            await message_obj.reply_text(
                "⚠️ **Verification Required (1/?)**\n\nPehle Level 1 complete karein.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return False 

    # --- LEVEL 2 CHECK ---
    if info.SHORTLINK_URL_2 and info.SHORTLINK_API_2:
        if not await db.get_verify_status(user_id, chat_id, 2):
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_2_{user_id}_{chat_id}_{link_id}"
            
            processing_msg = await message_obj.reply_text("🔎 Checking Verification Level 2... ⏳")
            short_url = await get_shortlink(verify_url, info.SHORTLINK_URL_2, info.SHORTLINK_API_2)
            await processing_msg.delete()
            
            btn = [[InlineKeyboardButton("Verify Level 2", url=short_url)]]
            await message_obj.reply_text(
                "⚠️ **Verification Required (2/?)**\n\nLevel 1 Done! ✅\nAb Level 2 complete karein.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return False

    # --- LEVEL 3 CHECK ---
    if info.SHORTLINK_URL_3 and info.SHORTLINK_API_3:
        if not await db.get_verify_status(user_id, chat_id, 3):
            verify_url = f"https://t.me/{temp.U_NAME}?start=verify_3_{user_id}_{chat_id}_{link_id}"
            
            processing_msg = await message_obj.reply_text("🔎 Checking Verification Level 3... ⏳")
            short_url = await get_shortlink(verify_url, info.SHORTLINK_URL_3, info.SHORTLINK_API_3)
            await processing_msg.delete()
            
            btn = [[InlineKeyboardButton("Verify Level 3", url=short_url)]]
            await message_obj.reply_text(
                "⚠️ **Final Verification (3/3)**\n\nLevel 2 Done! ✅\nYe last step hai, fir file milegi.",
                reply_markup=InlineKeyboardMarkup(btn)
            )
            return False

    return True 


@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    if message.chat.type == "private":
        await db.add_user(message.from_user.id)

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

            # Update DB
            await db.update_verify_status(message.from_user.id, chat_id, level)

            # Check Next Level
            is_all_clear = await check_verification(client, message.from_user.id, chat_id, link_id, message)
            
            if is_all_clear:
                await message.reply(f"✅ **Verification Complete!**\n\nYou are fully verified for this group. 🚀")
                
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
            src_chat_id = data[2] if len(data) > 2 else message.chat.id
            
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

    # Case 3: Normal Start
    text = f"Hello {message.from_user.mention} 👋,\nMain ek **Auto Filter Bot** hu."
    buttons = [[InlineKeyboardButton('⚙ Features', callback_data='features')]]
    await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))


# --- ADMIN COMMANDS ---

# ✅ FIXED: Added ADMINS in imports, so this works now
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

@Client.on_message(filters.new_chat_members)
async def new_chat(client, message):
    try:
        bot_id = (await client.get_me()).id
        if bot_id in [u.id for u in message.new_chat_members]:
            await db.add_group(message.chat.id)
            await message.reply_text("Thanks for adding me!")
    except: pass

@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_handler(client, message):
    try:
        users = await db.total_users_count()
        files = await Media.total_files_count()
        await message.reply_text(f"📊 **STATS**\nUsers: {users}\nFiles: {files}")
    except: pass
