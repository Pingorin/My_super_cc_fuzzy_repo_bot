import logging
from pyrogram import Client, filters
from database.ia_filterdb import Media
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

def btn_parser(files):
    buttons = []
    for file in files:
        f_name = file['file_name']
        
        # ✅ FIX 1: Use Short Database ID (_id) to fix BUTTON_DATA_INVALID
        db_id = str(file['_id']) 
        
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

# --- Callback Handler (Robust Version) ---
@Client.on_callback_query(filters.regex(r"^sendfile#"))
async def send_file_handler(client, callback_query):
    try:
        _id = callback_query.data.split("#")[1]
        
        # 1. Get File Info
        file_info = await Media.get_file_by_id(_id)
        
        if not file_info:
            return await callback_query.answer("❌ File not found in DB.", show_alert=True)
            
        file_id = file_info['file_id']
        caption = file_info.get('caption', "🤖 **File Sent by AutoFilter Bot**")

        # ✅ FIX 2: Use 'reply_cached_media' 
        # This automatically handles both Videos and Documents, fixing the "Expected DOCUMENT" error.
        try:
            await callback_query.message.reply_cached_media(
                file_id=file_id,
                caption=caption
            )
        except Exception as e:
            # Fallback if cached media fails (rare)
            print(f"Cached Media Failed: {e}")
            await callback_query.message.reply_document(
                document=file_id,
                caption=caption
            )
            
        await callback_query.answer()
        
    except Exception as e:
        print(f"Send File Error: {e}")
        await callback_query.answer(f"❌ Error: {e}", show_alert=True)
