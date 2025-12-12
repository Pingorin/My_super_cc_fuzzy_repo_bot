import os
import logging
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
from info import ADMINS, IS_VERIFY, SHORTLINK_URL, SHORTLINK_API, VERIFY_EXPIRE
import info # ✅ Global update ke liye module import kiya
from utils import temp, get_shortlink # ✅ get_shortlink import kiya
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

    # ✅ CASE 1: Verification Return (User link click karke wapis aya)
    # Format: /start verify_123456789
    if len(message.command) > 1 and message.command[1].startswith("verify_"):
        try:
            _, verify_id = message.command[1].split("_", 1)
            # Security Check: Kya verify ID user ki ID se match karti hai?
            if str(verify_id) != str(message.from_user.id):
                return await message.reply("❌ Ye link apke liye nahi hai.")
            
            # Database Update
            await db.update_verify_status(message.from_user.id)
            
            await message.reply(
                f"✅ **Verification Successful!**\n\n"
                f"Ab aap agle **24 ghante** tak unlimited files download kar sakte hain! 🚀\n"
                f"Wapis jakar file link par click karein."
            )
            return
        except Exception as e:
            return await message.reply(f"❌ Verification Error: {e}")

    # ✅ CASE 2: File Request (Deep Link: /start get_123)
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        
        # --- 🔒 VERIFICATION CHECK START ---
        if IS_VERIFY:
            # Database se status check karo
            is_verified = await db.get_verify_status(message.from_user.id)
            
            if not is_verified:
                # 1. Verify Link Generate karo
                verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{message.from_user.id}"
                
                msg = await message.reply_text("Please wait, generating verification link... ⏳")
                short_url = await get_shortlink(verify_url)
                await msg.delete()
                
                # 2. Button bhejo
                btn = [[InlineKeyboardButton("✅ Click Here To Verify", url=short_url)]]
                await message.reply_text(
                    f"⚠️ **Verification Required!**\n\n"
                    f"Aapka token expire ho gaya hai.\n"
                    f"File paane ke liye pehle verify karein.\n\n"
                    f"_(Sirf 1 baar verify karein aur 24 ghante enjoy karein)_",
                    reply_markup=InlineKeyboardMarkup(btn)
                )
                return # Yahi rok do, file mat bhejo
        # --- 🔒 VERIFICATION CHECK END ---

        try:
            link_id = int(message.command[1].split("_")[1])
            
            # Database Fetch
            file_data = await Media.get_file_details(link_id)
            search_data = await Media.search_col.find_one({'link_id': link_id})
            
            if not file_data:
                return await message.reply("❌ File Database se delete ho gayi hai.")
            
            file_id = file_data.get('file_id')
            
            if not file_id:
                return await message.reply("❌ Error: Is file ki ID database me nahi hai. Admin ko Re-Index karna padega.")

            # Caption Logic
            db_caption = search_data.get('caption')
            if not db_caption:
                db_caption = f"📂 <b>{search_data.get('file_name')}</b>"
            
            final_caption = f"{db_caption}\n{script.CUSTOM_FOOTER}"

            # 🚀 Use 'send_cached_media'
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

    # ✅ CASE 3: Normal Start (Welcome Message)
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

# --- 🛠 ADMIN COMMAND: Set Shortener ---
@Client.on_message(filters.command("set_shortner") & filters.user(ADMINS))
async def set_shortner(client, message):
    if len(message.command) < 3:
        return await message.reply("❌ **Usage:** `/set_shortner website.com api_key`")
    
    new_site = message.command[1]
    new_api = message.command[2]

    # Update info module variables
    info.SHORTLINK_URL = new_site
    info.SHORTLINK_API = new_api
    
    # Note: utils.py ko restart ke bina update karna mushkil hota hai, 
    # lekin naye request naye variables use karenge agar utils dynamic hai.
    # Agar turant asar na dikhe to bot restart karna padega.
    
    await message.reply(
        f"✅ **Shortener Updated!**\n"
        f"Website: `{new_site}`\n"
        f"API: `{new_api}`\n\n"
        f"⚠️ Note: Agar link generate nahi ho raha, to `/restart` karein."
    )
