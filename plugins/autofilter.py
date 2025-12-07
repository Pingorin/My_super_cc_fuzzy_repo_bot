import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media

def get_size(size):
    if not size: return ""
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index"]))
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
        await message.reply_text(f"❌ Error: {e}")

def btn_parser(files):
    buttons = []
    for file in files:
        f_name = file['file_name']
        link_id = file.get('link_id')
        f_size = file.get('file_size', 0)
        size_str = get_size(f_size)
        btn_text = f"📂 {f_name} [{size_str}]"
        
        if link_id is not None:
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"get_{link_id}")])
    return buttons

# ✅ STEP 2 & 3: Using copy_message
@Client.on_callback_query(filters.regex(r"^get_"))
async def get_file_handler(client, callback_query):
    try:
        link_id = int(callback_query.data.split("_")[1])
        
        # 1. Fetch file location from DB
        file_data = await Media.get_file_details(link_id)
        
        if not file_data:
            return await callback_query.answer("❌ File not found in DB (Re-index required).", show_alert=True)
            
        msg_id = file_data['msg_id']
        chat_id = file_data['chat_id'] # This is the Channel ID

        # 2. Use copy_message instead of send_document
        await client.copy_message(
            chat_id=callback_query.message.chat.id, # Bhejna kahan hai (User ko)
            from_chat_id=chat_id,                   # Uthana kahan se hai (Channel se)
            message_id=msg_id                       # Kaunsa message
        )
        
        await callback_query.answer()
        
    except Exception as e:
        print(f"File Send Error: {e}")
        # Agar bot admin nahi hai ya channel access nahi kar pa raha
        await callback_query.answer(f"❌ Error: Bot Channel access nahi kar pa raha. Make sure Bot is Admin in Channel.", show_alert=True)
