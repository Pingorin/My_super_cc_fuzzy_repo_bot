from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media

def btn_parser(files):
    buttons = []
    for file in files:
        f_name = file['file_name']
        
        # यहाँ हम files_search से मिला 'link_id' उपयोग करेंगे
        # link_id एक छोटा नंबर है (जैसे 501, 502)
        link_id = file['link_id']
        
        # Callback Data बहुत छोटा बनेगा: get_501
        buttons.append([InlineKeyboardButton(text=f"📂 {f_name}", callback_data=f"get_{link_id}")])
    return buttons

@Client.on_message(filters.text & filters.group & filters.incoming)
async def auto_filter(client, message):
    query = message.text
    
    if len(query) < 2: return

    try:
        # Collection 2 (Search) में ढूंढें
        files = await Media.get_search_results(query)
        
        if not files:
            return # कोई फाइल नहीं मिली

        buttons = btn_parser(files)
        
        await message.reply_text(
            f"✅ **Found {len(files)} results for** `{query}`:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"Search Error: {e}")

# --- Callback Handler (The Most Important Part) ---
@Client.on_callback_query(filters.regex(r"^get_"))
async def get_file_handler(client, callback_query):
    try:
        # 1. बटन से link_id निकालें (जैसे get_123 से 123)
        link_id = int(callback_query.data.split("_")[1])
        
        # 2. Collection 1 (Data) से message_id और chat_id मंगवाएं
        file_data = await Media.get_file_details(link_id)
        
        if not file_data:
            return await callback_query.answer("File database से हट चुकी है ❌", show_alert=True)
            
        msg_id = file_data['msg_id']
        chat_id = file_data['chat_id']

        # 3. फाइल फॉरवर्ड करें (copy_message ज्यादा सुरक्षित और साफ है)
        # copy_message से 'Forwarded from' टैग नहीं आता, caption बना रहता है।
        await client.copy_message(
            chat_id=callback_query.message.chat.id,
            from_chat_id=chat_id,
            message_id=msg_id,
            caption=f"📂 Here is your file\n\n🤖 Powered by AutoFilter" # अगर आप कस्टम कैप्शन चाहते हैं
        )
        
        await callback_query.answer()
        
    except Exception as e:
        print(f"File Send Error: {e}")
        await callback_query.answer("File भेजने में समस्या आई (शायद चैनल से डिलीट हो गई हो)", show_alert=True)
