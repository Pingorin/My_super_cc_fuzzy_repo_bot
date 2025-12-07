import logging
from pyrogram import Client, filters
from database.ia_filterdb import Media
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

def btn_parser(files):
    buttons = []
    for file in files:
        f_name = file['file_name']
        
        # ✅ FIX: Use the short Database ID (_id) instead of long file_id
        db_id = str(file['_id']) 
        
        # Now the data is short (e.g., sendfile#64d123...) and fits in the limit
        buttons.append([InlineKeyboardButton(text=f"📂 {f_name}", callback_data=f"sendfile#{db_id}")])
    return buttons

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index"]))
async def auto_filter(client, message):
    
    query = message.text
    if len(query) < 2: return

    try:
        files = await Media.get_search_results(query)
        
        if not files:
            await message.reply_text(f"❌ **No results found for:** `{query}`")
            return

        buttons = btn_parser(files)
        
        await message.reply_text(
            f"✅ **Found {len(files)} results for** `{query}`:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"Search Error: {e}")

# --- Callback Handler (Updated for Short ID) ---
@Client.on_callback_query(filters.regex(r"^sendfile#"))
async def send_file_handler(client, callback_query):
    try:
        # 1. Get the Short ID from button
        _id = callback_query.data.split("#")[1]
        
        # 2. Ask Database for the full file info using Short ID
        file_info = await Media.get_file_by_id(_id)
        
        if not file_info:
            return await callback_query.answer("❌ File Database me nahi mili.", show_alert=True)
            
        file_id = file_info['file_id']
        # Use saved caption, or default if none
        caption = file_info.get('caption', "🤖 **File Sent by AutoFilter Bot**")

        # 3. Send the file
        await callback_query.message.reply_document(
            document=file_id,
            caption=caption
        )
        await callback_query.answer()
        
    except Exception as e:
        print(f"Send File Error: {e}")
        await callback_query.answer(f"❌ Error: {e}", show_alert=True)
