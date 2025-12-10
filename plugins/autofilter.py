import logging
import time
import re
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
    
    raw_query = message.text
    if len(raw_query) < 2: return

    # --- 🧹 ADVANCED CLEANING (Apki List Ke Hisab Se) ---
    
    # Is regex me wo sab words hain jo apne bataye:
    # 1. Requests: please, pls, plz, ples, send, give, gib, find, chahiye
    # 2. Actions: send me
    # 3. Common: movie, new, latest, full movie, file, link
    # 4. Greetings: hello, hi, bro, bhai, sir, bruh
    # 5. Languages: hindi, tamil, malayalam, eng
    # 6. Extras: with subtitles, hd
    
    clean_regex = r"\b(please|pls|plz|ples|send(\s+me)?|give|gib|find|chahiye|movie|new|latest|full\s+movie|file|link|hello|hi|bro|bhai|sir|bruh|hindi|tamil|malayalam|eng|with\s+subtitles|hd)\b"
    
    # Replace junk with empty space
    query = re.sub(clean_regex, "", raw_query, flags=re.IGNORECASE)
    
    # Extra spaces hatao
    query = re.sub(r"\s+", " ", query).strip()
    
    # Fallback: Agar sab kuch delete ho gaya (e.g. user ne sirf "Hello Sir" likha tha)
    if len(query) < 2:
        query = raw_query
    # ----------------------------------------

    # ✅ Timer Start
    start_time = time.time()

    try:
        files = await Media.get_search_results(query)
        
        end_time = time.time()
        time_taken = round(end_time - start_time, 2)

        if not files:
            await message.reply_text(
                f"⚡ **Hey {message.from_user.mention}!**\n"
                f"❌ **No results found for:** `{query}`\n"
                f"⏳ **Time Taken:** {time_taken} seconds"
            )
            return

        buttons = btn_parser(files, query)
        
        msg_text = (
            f"⚡ **Hey {message.from_user.mention}!**\n"
            f"👻 **Here are your results for:** `{query}`\n"
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
            url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}"
            buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    return buttons
