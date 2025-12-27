import logging
from pyrogram import Client, filters, enums
from database.ia_filterdb import Media

# Logger setup
logger = logging.getLogger(__name__)

# ✅ LOGIC CHANGE: 
# Removed 'filters.chat(CHANNELS)'
# Added 'filters.channel' to listen to ALL channels
# Added 'filters.audio' as requested

@Client.on_message(filters.channel & (filters.document | filters.video | filters.audio)) 
async def live_indexing(bot, message):
    
    # Determine which media type is present
    media = message.document or message.video or message.audio
    
    # Safety check
    if not media:
        return

    try:
        # Save to Database
        # We wrap it in a list [(media, message)] because save_batch expects a list
        saved, dups = await Media.save_batch([(media, message)])
        
        # Optional: Log successful saves
        if saved:
            logger.info(f"✅ Auto-Indexed: {message.chat.title} [{message.chat.id}] - Msg ID: {message.id}")
            
    except Exception as e:
        logger.error(f"❌ Auto-Index Error in {message.chat.title}: {e}")

