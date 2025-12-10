import logging
from pyrogram import Client, filters
from database.ia_filterdb import Media
from info import CHANNELS

# Logger setup
logger = logging.getLogger(__name__)

@Client.on_message(filters.chat(CHANNELS) & (filters.document | filters.video | filters.audio))
async def live_indexing(bot, message):
    # Media nikalo
    media = message.document or message.video or message.audio
    if not media:
        return

    # Hum 'save_batch' use karenge kyunki usme 'Duplicate Check' 
    # aur 'Cleaning Logic' (Text Remove) pehle se laga hua hai.
    # Hum bas ek item ki list banakar bhej denge.
    
    try:
        # Pass as list: [(media, message)]
        saved, dups = await Media.save_batch([(media, message)])
        
        if saved:
            print(f"✅ Auto-Indexed: {message.id} | {message.chat.title}")
            # Optional: Agar aap chahein to Bot confirmation msg bhej sakta hai (Log channel me)
            # await bot.send_message(LOG_CHANNEL, f"✅ New File Indexed: {media.file_name}")
            
        elif dups:
            print(f"♻️ Duplicate Skipped: {message.id}")
            
    except Exception as e:
        print(f"❌ Auto-Index Error: {e}")
