import logging
from pyrogram import Client, filters
from database.ia_filterdb import Media

# Logger setup
logger = logging.getLogger(__name__)

# ✅ UPDATE: Removed 'CHANNELS' filter. 
# Now listens to ANY Channel where bot is Admin.
@Client.on_message(filters.channel & (filters.document | filters.video)) 
async def live_indexing(bot, message):
    """
    Automatically saves files from ANY channel where the bot is added.
    """
    media = message.document or message.video 
    if not media:
        return

    try:
        # We use save_batch with a single item list to reuse existing logic
        saved, dups = await Media.save_batch([(media, message)])
        
        if saved:
            chat_title = message.chat.title if message.chat else "Unknown Chat"
            logger.info(f"✅ Auto-Indexed: {message.id} | {chat_title}")
            
    except Exception as e:
        logger.error(f"❌ Auto-Index Error: {e}")
