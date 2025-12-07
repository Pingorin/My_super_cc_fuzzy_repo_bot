import os
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
from info import ADMINS
from utils import temp  # Username lene ke liye

logger = logging.getLogger(__name__)

# 1. Start Image Link
START_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg"

# --- UTILITY: Size Converter ---
def get_size(size):
    if not size: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

# --- COMMAND: /start ---
@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    # 1. User ko Database me Add karo (Zaruri hai Stats ke liye)
    if message.chat.type == "private":
        await db.add_user(message.from_user.id)
    
    # 2. Start Message Text
    text = f"""Hello {message.from_user.mention} 👋,

Main ek **Auto Filter Bot** hu. 
Muje apne group me add karo movies aur series provide karne ke liye.

Niche diye gaye buttons check karein 👇"""

    # 3. Buttons (Username temp.U_NAME se aayega)
    buttons = [[
        InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')
    ],[
        InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'),
        InlineKeyboardButton('💸 ᴘʀᴇᴍɪᴜᴍ', callback_data='buy_premium')
    ],[
        InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛʜ ʙᴏᴛ 🚫', callback_data='earn'),
        InlineKeyboardButton('🤝 ʀᴇꜰᴇʀʀᴀʟ 🤝', callback_data='refer')
    ]]
    
    # 4. Message Send Karna (Photo ke saath)
    await message.reply_photo(
        photo=START_IMG,
        caption=text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# --- HANDLER: New Group Join ---
@Client.on_message(filters.new_chat_members)
async def new_chat(client, message):
    try:
        bot_id = (await client.get_me()).id
        new_members = [u.id for u in message.new_chat_members]
        
        if bot_id in new_members:
            await db.add_group(message.chat.id)
            await message.reply_text(
                "Thanks for adding me! 🥳\n"
                "Main ab is group me files provide karunga.\n\n"
                "Admin mujhe **Admin Rights** de dein taaki main sahi se kaam kar saku."
            )
    except Exception as e:
        logger.error(f"Error in New Chat: {e}")

# --- COMMAND: /stats (Admin Only) ---
@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_handler(client, message):
    msg = await message.reply_text("📊 **Fetching Statistics...** Please wait.")
    
    try:
        total_users = await db.total_users_count()
        total_groups = await db.total_groups_count()
        total_files = await Media.total_files_count()
        db_bytes = await Media.get_db_size()
        db_size_str = get_size(db_bytes)
        
        await msg.edit_text(
            f"🤖 **SYSTEM STATISTICS** 📊\n\n"
            f"👤 **Total Users:** `{total_users}`\n"
            f"👥 **Total Groups:** `{total_groups}`\n"
            f"📂 **Total Files:** `{total_files}`\n\n"
            f"💾 **Database Used:** `{db_size_str}`\n"
            f"⚡ **CPU/RAM:** Running Smoothly"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error fetching stats: {e}")
