import os
import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
from info import ADMINS, IS_VERIFY, SHORTLINK_URL, SHORTLINK_API, VERIFY_EXPIRE
import info 
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

# --- SMART START HANDLER ---
@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    if message.chat.type == "private":
        await db.add_user(message.from_user.id)

    # ✅ CASE 1: Verification Return (Auto Send + Group Specific)
    # Format: /start verify_USERID_CHATID_LINKID
    if len(message.command) > 1 and message.command[1].startswith("verify_"):
        try:
            # Command breakdown: verify, userid, chatid, linkid
            data = message.command[1].split("_")
            verify_id = data[1]
            chat_id = data[2] # The Group ID for which verification is done
            
            # Security Check
            if str(verify_id) != str(message.from_user.id):
                return await message.reply("❌ Ye link apke liye nahi hai.")
            
            # 1. Update Database (Mark user as verified for this group)
            await db.update_verify_status(message.from_user.id, chat_id)
            
            await message.reply(
                f"✅ **Verification Successful!**\n\n"
                f"You are verified for **24 hours** for that group. 🚀"
            )

            # 2. 🔥 AUTO SEND FILE LOGIC 🔥
            # Check if LINKID exists in the command
            if len(data) > 3:
                link_id = int(data[3])
                
                # Fetch File Details
                file_data = await Media.get_file_details(link_id)
                search_data = await Media.search_col.find_one({'link_id': link_id})
                
                if not file_data:
                    return await message.reply("❌ File Database se delete ho gayi hai.")
                
                file_id = file_data.get('file_id')
                if not file_id:
                    return await message.reply("❌ Error: File ID missing.")

                # Prepare Caption
                db_caption = search_data.get('caption')
                if not db_caption:
                    db_caption = f"📂 <b>{search_data.get('file_name')}</b>"
                
                final_caption = f"{db_caption}\n{script.CUSTOM_FOOTER}"

                # Send File Immediately
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

    # ✅ CASE 2: File Request (Deep Link with Chat ID)
    # Format: /start get_LINKID_CHATID
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        
        try:
            data = message.command[1].split("_")
            link_id = int(data[1])
            
            # Extract Chat ID (if present in link) to check specific group verification
            # If coming from a direct link without group info, default to user's chat ID
            src_chat_id = data[2] if len(data) > 2 else str(message.chat.id)
            
            # --- 🔒 GROUP SPECIFIC VERIFICATION CHECK ---
            if IS_VERIFY:
                # Check if user is verified for 'src_chat_id'
                is_verified = await db.get_verify_status(message.from_user.id, src_chat_id)
                
                if not is_verified:
                    # Generate Link: verify_USERID_CHATID_LINKID
                    # We embed 'link_id' so we can auto-send the file later
                    verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{message.from_user.id}_{src_chat_id}_{link_id}"
                    
                    msg = await message.reply_text("Generating secure link... ⏳")
                    short_url = await get_shortlink(verify_url)
                    await msg.delete()
                    
                    btn = [[InlineKeyboardButton("✅ Click Here To Verify", url=short_url)]]
                    await message.reply_text(
                        f"⚠️ **Verification Required!**\n\n"
                        f"Aapne is Group ke liye verify nahi kiya hai.\n"
                        f"File paane ke liye pehle verify karein.\n\n"
                        f"_(Har group ka verification alag hai)_",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                    return 
            # -----------------------------

            # Standard File Sending (If already verified)
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

# --- Set Shortener ---
@Client.on_message(filters.command("set_shortner") & filters.user(ADMINS))
async def set_shortner(client, message):
    if len(message.command) < 3:
        return await message.reply("❌ **Usage:** `/set_shortner website.com api_key`")
    
    new_site = message.command[1]
    new_api = message.command[2]

    info.SHORTLINK_URL = new_site
    info.SHORTLINK_API = new_api
    
    await message.reply(
        f"✅ **Shortener Updated!**\n"
        f"Website: `{new_site}`\n"
        f"API: `{new_api}`\n\n"
        f"⚠️ Note: Restart required for permanent change."
    )
