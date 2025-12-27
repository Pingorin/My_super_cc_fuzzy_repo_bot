import logging
from pyrogram import Client, filters, enums
from database.ia_filterdb import Media

# Logger setup
logger = logging.getLogger(__name__)

# ✅ UPDATED: Removed specific 'CHANNELS' filter.
# Now using 'filters.channel' to listen to ALL channels the bot is in.
@Client.on_message(filters.channel & (filters.document | filters.video)) 
async def live_indexing(bot, message):
    
    # Check for media availability
    media = message.document or message.video 
    if not media:
        return

    # Optional: Ignore protected content (files that can't be forwarded/saved)
    if message.protected:
        return

    try:
        # Save Batch expects a list of tuples: [(media, message)]
        saved, dups = await Media.save_batch([(media, message)])
        
        if saved:
            logger.info(f"✅ Auto-Indexed: {message.id} | {message.chat.title}")
        elif dups:
            # Uncomment below line if you want to see duplicate logs
            logger.info(f"♻️ Duplicate Skipped: {message.id} | {message.chat.title}")
            pass
            
    except Exception as e:
        logger.error(f"❌ Auto-Index Error in {message.chat.title}: {e}")
