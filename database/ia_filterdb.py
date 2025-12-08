import logging
from pyrogram import Client, filters
from pyrogram.errors import PeerIdInvalid, ChannelInvalid
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

# ✅ Robust File Handler (With Auto-Retry)
@Client.on_callback_query(filters.regex(r"^get_"))
async def get_file_handler(client, callback_query):
    try:
        link_id = int(callback_query.data.split("_")[1])
        
        file_data = await Media.get_file_details(link_id)
        
        if not file_data:
            return await callback_query.answer("❌ File delete ho gayi hai.", show_alert=True)
            
        msg_id = file_data['msg_id']
        chat_id = file_data['chat_id']

        try:
            # ✅ Try to Copy Message
            await client.copy_message(
                chat_id=callback_query.message.chat.id,
                from_chat_id=chat_id,
                message_id=msg_id
            )
        except (PeerIdInvalid, ChannelInvalid):
            # ⚠️ Agar Peer ID error aaya, to hum connection refresh karenge
            try:
                # 1. Force fetch chat info (Isse connection ban jayega)
                await client.get_chat(chat_id)
                
                # 2. Retry Copy
                await client.copy_message(
                    chat_id=callback_query.message.chat.id,
                    from_chat_id=chat_id,
                    message_id=msg_id
                )
            except Exception as e:
                # Agar ab bhi nahi hua, to user ko bolo forward kare
                print(f"Retry Failed: {e}")
                return await callback_query.answer(
                    "⚠️ Connection Lost!\n\nKripya apne Movie Channel se koi ek message Bot ko Forward karein taaki connection refresh ho sake.", 
                    show_alert=True
                )
        
        await callback_query.answer()
        
    except Exception as e:
        print(f"File Send Error: {e}")
        await callback_query.answer(f"❌ Error: {e}", show_alert=True)
