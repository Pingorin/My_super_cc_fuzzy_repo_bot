import logging
from pyrogram import Client, filters
from database.ia_filterdb import Media
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

def btn_parser(files):
    buttons = []
    for file in files:
        f_name = file['file_name']
        
        # ✅ FIX: File ID ki jagah Database ID (_id) use karein jo chhota hota hai
        db_id = str(file['_id']) 
        
        # Button callback ab chhota hoga (e.g., sendfile#64d123...)
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

# --- Callback Handler (File Bhejne ke liye) ---
@Client.on_callback_query(filters.regex(r"^sendfile#"))
async def send_file_handler(client, callback_query):
    try:
        # 1. Button se Short ID nikalo
        _id = callback_query.data.split("#")[1]
        
        # 2. Database se Asli File ID maango
        file_info = await Media.get_file_by_id(_id)
        
        if not file_info:
            return await callback_query.answer("File nahi mili (Deleted?)", show_alert=True)
            
        file_id = file_info['file_id']
        caption = file_info.get('caption', "🤖 **File Sent by AutoFilter Bot**")

        # 3. File Bhejo
        await callback_query.message.reply_document(
            document=file_id,
            caption=caption
        )
        await callback_query.answer()
        
    except Exception as e:
        print(f"Send File Error: {e}")
        await callback_query.answer("❌ Error sending file.", show_alert=True)
