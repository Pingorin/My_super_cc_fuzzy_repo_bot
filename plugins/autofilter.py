import logging
from pyrogram import Client, filters
from database.ia_filterdb import Media
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Logs me print karne ke liye
logger = logging.getLogger(__name__)

def btn_parser(files):
    buttons = []
    for file in files:
        f_name = file['file_name']
        f_size = file['file_size'] # Size convert karna ho to utils use karein
        f_id = file['file_id']
        
        # Button: [File Name]
        buttons.append([InlineKeyboardButton(text=f"📂 {f_name}", callback_data=f"sendfile#{f_id}")])
    return buttons

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index"]))
async def auto_filter(client, message):
    
    query = message.text
    # Agar message chhota hai to ignore karo
    if len(query) < 2:
        return

    print(f"DEBUG: Searching for '{query}' from user {message.from_user.id}")

    try:
        # Database Search
        files = await Media.get_search_results(query)
        
        if not files:
            # DEBUG: Agar file nahi mili to user ko batao
            # (Baad me aap is line ko hata sakte hain taaki group me shor na ho)
            await message.reply_text(f"❌ **No results found for:** `{query}`\n\nCheck spelling or try another keyword.")
            return

        # Buttons banao
        buttons = btn_parser(files)
        
        await message.reply_text(
            f"✅ **Found {len(files)} results for** `{query}`:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"Search Error: {e}")
        await message.reply_text(f"❌ Error: {e}")

# --- Callback Handler (File Bhejne ke liye) ---
@Client.on_callback_query(filters.regex(r"^sendfile#"))
async def send_file_handler(client, callback_query):
    try:
        file_id = callback_query.data.split("#")[1]
        
        # File bhejo
        await callback_query.message.reply_document(
            document=file_id,
            caption="🤖 **File Sent by AutoFilter Bot**"
        )
        await callback_query.answer()
        
    except Exception as e:
        print(f"Send File Error: {e}")
        await callback_query.answer("❌ File bhejne me error aaya.", show_alert=True)
