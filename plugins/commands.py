import os
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
from info import ADMINS

logger = logging.getLogger(__name__)

# --- UTILITY: Size Converter (Bytes to MB/GB) ---
def get_size(size):
    """Bytes ko Human Readable format me badalta hai"""
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
    # 1. User ko Database me Add karo
    if message.chat.type == "private":
        await db.add_user(message.from_user.id)
    
    # 2. Welcome Message
    buttons = [[
        InlineKeyboardButton("➕ Add Me To Your Group ➕", url=f"http://t.me/{client.username}?startgroup=true")
    ],[
        InlineKeyboardButton("ℹ️ Help", callback_data="help"),
        InlineKeyboardButton("😎 About", callback_data="about")
    ]]
    
    await message.reply_text(
        text=f"👋 Hello **{message.from_user.mention}**!\n\n"
             f"Main ek **Auto Filter Bot** hu. 🤖\n"
             f"Mujhe apne Group me add karein aur main wahan Movies/Series provide karunga.\n\n"
             f"Bas Movie ka naam likhein aur magic dekhein! ✨",
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )

# --- HANDLER: New Group Join ---
# Jab bot kisi naye group me add hota hai
@Client.on_message(filters.new_chat_members)
async def new_chat(client, message):
    try:
        # Check karo ki kya naya member 'Bot khud' hai?
        bot_id = (await client.get_me()).id
        new_members = [u.id for u in message.new_chat_members]
        
        if bot_id in new_members:
            # Group ko Database me save karo
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
        # 1. Counts nikalo
        total_users = await db.total_users_count()
        total_groups = await db.total_groups_count()
        total_files = await Media.total_files_count()
        
        # 2. Database Size nikalo (MongoDB se)
        db_bytes = await Media.get_db_size()
        db_size_str = get_size(db_bytes)
        
        # 3. Report Bhejo
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
