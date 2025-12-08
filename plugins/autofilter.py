import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from pyrogram.errors import PeerIdInvalid

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

# ✅ UPDATED: Using send_cached_media
@Client.on_callback_query(filters.regex(r"^get_"))
async def get_file_handler(client, callback_query):
    try:
        link_id = int(callback_query.data.split("_")[1])
        
        # 1. Get File Details (including file_id)
        file_data = await Media.get_file_details(link_id)
        search_data = await Media.search_col.find_one({'link_id': link_id}) # Caption ke liye
        
        if not file_data:
            return await callback_query.answer("❌ File not found in DB.", show_alert=True)
            
        file_id = file_data.get('file_id') # ✅ Ab ye milega
        
        # Caption Logic
        caption = None
        if search_data and search_data.get('caption'):
            caption = search_data['caption']
        else:
            caption = f"📂 **{search_data.get('file_name')}**"

        if not file_id:
            # Fallback agar purana data ho
            return await callback_query.answer("❌ File ID missing. Re-index required.", show_alert=True)

        try:
            # ✅ YOUR REQUEST: send_cached_media
            await client.send_cached_media(
                chat_id=callback_query.message.chat.id,
                file_id=file_id,
                caption=caption
            )
        except PeerIdInvalid:
             # Retry Logic
            try:
                chat_id = file_data['chat_id']
                await client.get_chat(chat_id) # Refresh connection
                await client.send_cached_media(
                    chat_id=callback_query.message.chat.id,
                    file_id=file_id,
                    caption=caption
                )
            except:
                 return await callback_query.answer("⚠️ Connection lost. Forward a message to bot.", show_alert=True)

        await callback_query.answer()
        
    except Exception as e:
        print(f"File Send Error: {e}")
        await callback_query.answer(f"❌ Error: {e}", show_alert=True)
