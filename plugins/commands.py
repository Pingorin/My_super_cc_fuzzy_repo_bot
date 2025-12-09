import os
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
from info import ADMINS
from utils import temp
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

    # ✅ CASE 1: File Request (Deep Link: /start get_123)
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        try:
            link_id = int(message.command[1].split("_")[1])
            
            # Database Fetch
            file_data = await Media.get_file_details(link_id)
            search_data = await Media.search_col.find_one({'link_id': link_id})
            
            if not file_data:
                return await message.reply("❌ File Database se delete ho gayi hai.")
                
            msg_id = file_data['msg_id']
            chat_id = file_data['chat_id']

            # Caption Logic
            db_caption = search_data.get('caption')
            if not db_caption:
                db_caption = f"📂 <b>{search_data.get('file_name')}</b>"
            
            final_caption = f"{db_caption}\n{script.CUSTOM_FOOTER}"

            # 🚀 CHANGE: "Sending File..." msg hata diya gaya hai.
            # Ab seedha file bheji jayegi (No Delay)
            
            try:
                await client.copy_message(
                    chat_id=message.from_user.id,
                    from_chat_id=chat_id,
                    message_id=msg_id,
                    caption=final_caption,
                    parse_mode=enums.ParseMode.HTML
                )
            except PeerIdInvalid:
                try:
                    await client.get_chat(chat_id)
                    await client.copy_message(
                        chat_id=message.from_user.id,
                        from_chat_id=chat_id,
                        message_id=msg_id,
                        caption=final_caption,
                        parse_mode=enums.ParseMode.HTML
                    )
                except:
                    await message.reply("⚠️ Bot Channel access nahi kar pa raha.")
                    
        except Exception as e:
            await message.reply(f"❌ Error: {e}")
        return

    # ✅ CASE 2: Normal Start (Welcome Message)
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
