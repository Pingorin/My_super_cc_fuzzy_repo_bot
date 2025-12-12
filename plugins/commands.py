import os
import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
import info 
from info import ADMINS # ✅ CRITICAL IMPORT (Prevents NameError)
from utils import temp, get_shortlink 
from Script import script 
from pyrogram.errors import PeerIdInvalid

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

# --- 🧠 DYNAMIC VERIFICATION CHECKER ---
# This function checks which level is pending.
# It skips levels that are not configured in info.py.
async def get_next_verification(user_id, chat_id):
    if not info.IS_VERIFY:
        return None # Verification System OFF

    # Check Level 1
    if info.SHORTLINK_URL_1 and info.SHORTLINK_API_1:
        if not await db.get_verify_status(user_id, chat_id, 1):
            return {
                'level': 1,
                'site': info.SHORTLINK_URL_1,
                'api': info.SHORTLINK_API_1
            }

    # Check Level 2
    if info.SHORTLINK_URL_2 and info.SHORTLINK_API_2:
        if not await db.get_verify_status(user_id, chat_id, 2):
            return {
                'level': 2,
                'site': info.SHORTLINK_URL_2,
                'api': info.SHORTLINK_API_2
            }

    # Check Level 3
    if info.SHORTLINK_URL_3 and info.SHORTLINK_API_3:
        if not await db.get_verify_status(user_id, chat_id, 3):
            return {
                'level': 3,
                'site': info.SHORTLINK_URL_3,
                'api': info.SHORTLINK_API_3
            }

    return None # All Configured Levels Passed!

# --- SMART START HANDLER ---
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

            # 1. Update Database for THIS level
            await db.update_verify_status(message.from_user.id, chat_id, level)

            # 2. Check Next Step (Smart Logic)
            next_step = await get_next_verification(message.from_user.id, chat_id)
            
            # If Next Step exists -> Send Link
            if next_step:
                lvl = next_step['level']
                site = next_step['site']
                api = next_step['api']
                
                # Next Link Generate
                verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{lvl}_{message.from_user.id}_{chat_id}_{link_id}"
                
                msg = await message.reply_text(f"✅ Level {level} Passed!\nGenerating Level {lvl} Link... ⏳")
                short_url = await get_shortlink(verify_url, site, api)
                await msg.delete()
                
                btn = [[InlineKeyboardButton(f"🚀 Verify Level {lvl}", url=short_url)]]
                await message.reply_text(
                    f"⚠️ **Verification Required ({lvl}/?)**\n\nAb agla level complete karein.",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                return 

            # 3. All Clear -> Send File
            await message.reply(f"✅ **Verification Complete!**\n\nYou are verified for this group. 🚀")
            
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
                    await message.reply(f"❌ Failed to send file.\nError: `{e}`")
            return

        except Exception as e:
            return await message.reply(f"❌ Verification Error: {e}")

    # ✅ CASE 2: File Request (Deep Link)
    # Format: get_LINKID_CHATID
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        try:
            data = message.command[1].split("_")
            link_id = int(data[1])
            src_chat_id = data[2] if len(data) > 2 else str(message.chat.id)
            
            # --- DYNAMIC CHECK ---
            next_step = await get_next_verification(message.from_user.id, src_chat_id)
            
            # If Verification needed
            if next_step:
                lvl = next_step['level']
                site = next_step['site']
                api = next_step['api']
                
                verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{lvl}_{message.from_user.id}_{src_chat_id}_{link_id}"
                
                msg = await message.reply_text(f"Generating Verification Link Level {lvl}... ⏳")
                short_url = await get_shortlink(verify_url, site, api)
                await msg.delete()
                
                btn = [[InlineKeyboardButton(f"Verify Level {lvl}", url=short_url)]]
                await message.reply_text(
                    f"⚠️ **Verification Required!**\n\nIs group se file lene ke liye verify karein.",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                return 

            # --- SEND FILE ---
            file_data = await Media.get_file_details(link_id)
            search_data = await Media.search_col.find_one({'link_id': link_id})
            
            if not file_data: return await message.reply("❌ File Database se delete ho gayi hai.")
            file_id = file_data.get('file_id')
            if not file_id: return await message.reply("❌ Error: File ID missing.")

            db_caption = search_data.get('caption')
            if not db_caption: db_caption = f"📂 <b>{search_data.get('file_name')}</b>"
            
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

    # CASE 3: Normal Start
    text = f"Hello {message.from_user.mention} 👋,\nMain ek **Auto Filter Bot** hu."
    buttons = [[InlineKeyboardButton('⚙ Features', callback_data='features')]]
    await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))


# --- ADMIN COMMAND: Set Specific Shortener ---
# Usage: /set_shortner 1 website.com api_key
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

# --- Stats & New Chat ---
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
