import logging
import time # ✅ Timer ke liye import
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from utils import temp 

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

    # ✅ Timer Start
    start_time = time.time()

    try:
        files = await Media.get_search_results(query)
        
        # ✅ Timer End
        end_time = time.time()
        time_taken = round(end_time - start_time, 2) # Seconds calculate kiye

        if not files:
            # Agar file nahi mili, to bhi time dikhayenge
            await message.reply_text(
                f"⚡ **Hey {message.from_user.mention}!**\n"
                f"❌ **No results found.**\n"
                f"⏳ **Time Taken:** {time_taken} seconds"
            )
            return

        buttons = btn_parser(files, query)
        
        # ✅ Aapka Custom Message Style
        msg_text = (
            f"⚡ **Hey {message.from_user.mention}!**\n"
            f"👻 **Here are your results...**\n"
            f"⏳ **Time Taken:** {time_taken} seconds"
        )
        
        await message.reply_text(
            text=msg_text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        print(f"Search Error: {e}")
        await message.reply_text(f"❌ Error: {e}")

def btn_parser(files, query):
    buttons = []
    for file in files:
        f_name = file['file_name']
        caption = file.get('caption')
        link_id = file.get('link_id')
        f_size = file.get('file_size', 0)
        
        display_name = f_name 
        if caption:
            q = query.lower()
            n = f_name.lower()
            c = caption.lower()
            if q not in n and q in c:
                clean_cap = caption.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
                if len(clean_cap) > 60: clean_cap = clean_cap[:57] + "..."
                display_name = clean_cap

        size_str = get_size(f_size)
        btn_text = f"📂 {display_name} [{size_str}]"
        
        if link_id is not None:
            # Deep Link URL
            url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}"
            buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    return buttons
