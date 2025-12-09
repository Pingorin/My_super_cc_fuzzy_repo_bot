import logging
import re
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from pyrogram.errors import PeerIdInvalid
from Script import script

# --- Utility: File Size Converter ---
def get_size(size):
    if not size: return ""
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

# --- Utility: HTML Cleaner (Button ke liye) ---
def clean_html(text):
    """Button text me Bold/Italic tags nahi chalte, unhe hatana padega"""
    if not text: return None
    return re.sub(r"<.*?>", "", text)

# --- Main Auto Filter Logic ---
@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index"]))
async def auto_filter(client, message):
    query = message.text
    if len(query) < 2: return

    try:
        files = await Media.get_search_results(query)
        if not files:
            await message.reply_text(f"❌ **No results found for:** `{query}`")
            return

        # ✅ Query pass kar rahe hain taaki match kar sakein
        buttons = btn_parser(files, query)
        
        await message.reply_text(
            f"✅ **Found {len(files)} results for** `{query}`:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"Search Error: {e}")
        await message.reply_text(f"❌ Error: {e}")

# --- Button Parser (Smart Logic) ---
def btn_parser(files, query):
    buttons = []
    for file in files:
        file_name = file['file_name']
        caption = clean_html(file.get('caption')) # Caption saaf kiya
        link_id = file.get('link_id')
        f_size = file.get('file_size', 0)
        
        size_str = get_size(f_size)
        
        # --- 🧠 SMART DISPLAY LOGIC ---
        
        # Default: File Name dikhayenge
        display_name = file_name
        
        # Logic: Agar Search Query 'File Name' me nahi hai...
        # Lekin 'Caption' me maujood hai...
        # To Button par Caption dikhao!
        if caption:
            if query.lower() not in file_name.lower() and query.lower() in caption.lower():
                display_name = caption
        
        # -----------------------------

        # Button Text: Name [Size]
        # (Naam lamba ho to thoda kat diya jata hai automatically)
        btn_text = f"📂 {display_name} [{size_str}]"
        
        if link_id is not None:
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"get_{link_id}")])
            
    return buttons

# --- Callback Handler (File Sending) ---
@Client.on_callback_query(filters.regex(r"^get_"))
async def get_file_handler(client, callback_query):
    try:
        link_id = int(callback_query.data.split("_")[1])
        
        file_data = await Media.get_file_details(link_id)
        search_data = await Media.search_col.find_one({'link_id': link_id})
        
        if not file_data:
            return await callback_query.answer("❌ File not found.", show_alert=True)
            
        file_id = file_data.get('file_id')
        msg_id = file_data['msg_id']
        chat_id = file_data['chat_id']

        # Caption Logic (Message ke liye)
        db_caption = search_data.get('caption')
        if not db_caption:
            db_caption = f"📂 <b>{search_data.get('file_name')}</b>"
            
        # Footer Add karo
        final_caption = f"{db_caption}\n{script.CUSTOM_FOOTER}"

        # Send File
        try:
            # Priority 1: send_cached_media (Agar File ID hai)
            if file_id:
                await client.send_cached_media(
                    chat_id=callback_query.message.chat.id,
                    file_id=file_id,
                    caption=final_caption,
                    parse_mode=enums.ParseMode.HTML
                )
            else:
                # Fallback: Copy Message
                await client.copy_message(
                    chat_id=callback_query.message.chat.id,
                    from_chat_id=chat_id,
                    message_id=msg_id,
                    caption=final_caption,
                    parse_mode=enums.ParseMode.HTML
                )
        except PeerIdInvalid:
            try:
                await client.get_chat(chat_id)
                if file_id:
                    await client.send_cached_media(chat_id=callback_query.message.chat.id, file_id=file_id, caption=final_caption, parse_mode=enums.ParseMode.HTML)
                else:
                    await client.copy_message(chat_id=callback_query.message.chat.id, from_chat_id=chat_id, message_id=msg_id, caption=final_caption, parse_mode=enums.ParseMode.HTML)
            except:
                 return await callback_query.answer("⚠️ Connection lost. Forward a message to bot.", show_alert=True)

        await callback_query.answer()
        
    except Exception as e:
        print(f"File Send Error: {e}")
        await callback_query.answer(f"❌ Error: {e}", show_alert=True)
