import logging
from pyrogram import Client, filters
from database.ia_filterdb import Media
from info import CHANNELS

# Logger setup
logger = logging.getLogger(__name__)

# ✅ CHANGE: 'filters.audio' hata diya gaya hai.
# Ab sirf Document aur Video hi automatic save honge.
@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video)) 
async def live_indexing(bot, message):
    # ✅ CHANGE: Yahan bhi audio hata diya
    media = message.document or message.video 
    if not media:
        return

    try:
        saved, dups = await Media.save_batch([(media, message)])
        
        if saved:
            print(f"✅ Auto-Indexed: {message.id} | {message.chat.title}")
        elif dups:
            print(f"♻️ Duplicate Skipped: {message.id}")
            
    except Exception as e:
        print(f"❌ Auto-Index Error: {e}")
