import logging
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from Script import script  # ✅ Import Script file

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

        buttons = btn_parser(files)
        
        await message.reply_text(
            f"✅ **Found {len(files)} results for** `{query}`:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"Search Error: {e}")
        await message.reply_text(f"❌ Error: {e}")

# --- Button Parser ---
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

# --- Callback Handler (The Main Magic) ---
@Client.on_callback_query(filters.regex(r"^get_"))
async def get_file_handler(client, callback_query):
    try:
        link_id = int(callback_query.data.split("_")[1])
        
        # 1. Database se details nikalo
        file_data = await Media.get_file_details(link_id)
        # Search collection se caption nikalo (Jo humne clean kiya tha)
        search_data = await Media.search_col.find_one({'link_id': link_id})
        
        if not file_data:
            return await callback_query.answer("❌ File not found.", show_alert=True)
            
        msg_id = file_data['msg_id']
        chat_id = file_data['chat_id']

        # 2. CAPTION LOGIC (Original + Footer)
        db_caption = search_data.get('caption')
        
        # Agar caption nahi hai to filename use karo
        if not db_caption:
            db_caption = f"📂 <b>{search_data.get('file_name')}</b>"
            
        # ✅ Footer Add karo
        final_caption = f"{db_caption}\n{script.CUSTOM_FOOTER}"

        # 3. Send File (Caption Override ke sath)
        await client.copy_message(
            chat_id=callback_query.message.chat.id,
            from_chat_id=chat_id,
            message_id=msg_id,
            caption=final_caption, # Yahan naya caption jayega
            parse_mode=enums.ParseMode.HTML
        )
        
        await callback_query.answer()
        
    except Exception as e:
        print(f"File Send Error: {e}")
        # Agar error aaye (jaise PeerIdInvalid), user ko guide karo
        await callback_query.answer("⚠️ Error: Bot Channel access nahi kar pa raha. Message Forward karo.", show_alert=True)
