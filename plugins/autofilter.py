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

        # ✅ CHANGE: 'query' bhi pass kar rahe hain check karne ke liye
        buttons = btn_parser(files, query)
        
        await message.reply_text(
            f"✅ **Found {len(files)} results for** `{query}`:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"Search Error: {e}")
        await message.reply_text(f"❌ Error: {e}")

# --- SMART BUTTON PARSER ---
def btn_parser(files, query):
    buttons = []
    for file in files:
        f_name = file['file_name']
        caption = file.get('caption')
        link_id = file.get('link_id')
        f_size = file.get('file_size', 0)
        
        # --- 🧠 SMART LOGIC START ---
        display_name = f_name # Default: File Name dikhao
        
        # Check: Agar User ka search word File Name me NAHI hai...
        # Lekin Caption me HAI... to Caption dikhao.
        if caption:
            q = query.lower() # User ki search (small letters)
            n = f_name.lower() # File Name (small letters)
            c = caption.lower() # Caption (small letters)
            
            # Agar naam me match nahi hua, par caption me match ho gaya
            if q not in n and q in c:
                display_name = caption
        # --- SMART LOGIC END ---

        # Size Add karo
        size_str = get_size(f_size)
        btn_text = f"📂 {display_name} [{size_str}]"
        
        if link_id is not None:
            buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"get_{link_id}")])
    return buttons

@Client.on_callback_query(filters.regex(r"^get_"))
async def get_file_handler(client, callback_query):
    try:
        link_id = int(callback_query.data.split("_")[1])
        
        file_data = await Media.get_file_details(link_id)
        # Caption ke liye search data bhi nikalo
        search_data = await Media.search_col.find_one({'link_id': link_id})
        
        if not file_data:
            return await callback_query.answer("❌ File not found.", show_alert=True)
            
        msg_id = file_data['msg_id']
        chat_id = file_data['chat_id']
        file_id = file_data.get('file_id') # For send_cached_media

        # Caption Selection for Sending File
        # (Yahan bhi hum wahi bhejenge jo database me saaf hokar save hua tha)
        final_caption = None
        if search_data and search_data.get('caption'):
            final_caption = search_data['caption']
        else:
            final_caption = f"📂 **{search_data.get('file_name')}**"

        # Using copy_message (Best method)
        try:
            await client.copy_message(
                chat_id=callback_query.message.chat.id,
                from_chat_id=chat_id,
                message_id=msg_id,
                caption=final_caption 
            )
        except PeerIdInvalid:
            try:
                await client.get_chat(chat_id)
                await client.copy_message(
                    chat_id=callback_query.message.chat.id,
                    from_chat_id=chat_id,
                    message_id=msg_id,
                    caption=final_caption
                )
            except:
                 return await callback_query.answer("⚠️ Connection lost. Forward msg to bot.", show_alert=True)

        await callback_query.answer()
        
    except Exception as e:
        print(f"File Send Error: {e}")
        await callback_query.answer(f"❌ Error: {e}", show_alert=True)
