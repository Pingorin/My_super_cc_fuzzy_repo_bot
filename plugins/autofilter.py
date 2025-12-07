import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media

# PM aur Group dono me allow karne ke liye
@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index"]))
async def auto_filter(client, message):
    query = message.text
    
    if len(query) < 2: return

    try:
        # Search Collection
        files = await Media.get_search_results(query)
        
        if not files:
            # Agar file nahi mili to user ko batao (Silent mat raho)
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
        link_id = file['link_id']
        
        # Callback Data: get_123
        buttons.append([InlineKeyboardButton(text=f"📂 {f_name}", callback_data=f"get_{link_id}")])
    return buttons

# --- Callback Handler ---
@Client.on_callback_query(filters.regex(r"^get_"))
async def get_file_handler(client, callback_query):
    try:
        link_id = int(callback_query.data.split("_")[1])
        
        # File Details nikalo
        file_data = await Media.get_file_details(link_id)
        
        if not file_data:
            return await callback_query.answer("❌ File Database se delete ho gayi hai.", show_alert=True)
            
        msg_id = file_data['msg_id']
        chat_id = file_data['chat_id']

        # File Forward karo
        await client.copy_message(
            chat_id=callback_query.message.chat.id,
            from_chat_id=chat_id,
            message_id=msg_id,
            caption=f"📂 **File Delivered!**\n\n🤖 Powered by AutoFilter"
        )
        
        await callback_query.answer()
        
    except Exception as e:
        print(f"File Send Error: {e}")
        await callback_query.answer(f"❌ Error: {e}", show_alert=True)
