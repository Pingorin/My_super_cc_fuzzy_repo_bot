import logging
import time
import re
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from utils import temp, btn_parser # ✅ btn_parser ab utils se aayega

def get_size(size):
    if not size: return ""
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index", "set_shortner", "settings"]))
async def auto_filter(client, message):
    
    raw_query = message.text
    if len(raw_query) < 2: return

    # --- 🧹 CLEANING LOGIC ---
    clean_regex = r"\b(please|pls|plz|ples|send(\s+me)?|give|gib|find|chahiye|movie|new|latest|full\s+movie|file|link|hello|hi|bro|bhai|sir|bruh|hindi|tamil|malayalam|eng|with\s+subtitles|hd)\b"
    
    query = re.sub(clean_regex, "", raw_query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()
    
    if len(query) < 2:
        query = raw_query
    # -------------------------

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

        # ✅ CRITICAL UPDATE: 'message.chat.id' pass kiya
        # Isse button ke link me Group ID chali jayegi (Per-Group Verify ke liye)
        buttons = btn_parser(files, message.chat.id, query)
        
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

# Note: btn_parser function yahan se hata diya gaya hai
# kyunki wo ab 'utils.py' se import ho raha hai.
