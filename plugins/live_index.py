import logging
import asyncio
from pyrogram import Client, filters
from database.ia_filterdb import Media
from info import ADMINS

# Logger setup
logger = logging.getLogger(__name__)

# 🔥 BATCHING QUEUE (The Waiting Room)
AUTO_INDEX_QUEUE = []
QUEUE_LOCK = asyncio.Lock()

# 🕒 BACKGROUND TASK (Dynamic Turbo Gatekeeper)
async def flush_index_queue():
    global AUTO_INDEX_QUEUE
    
    BATCH_SIZE = 200 
    
    while True:
        async with QUEUE_LOCK:
            queue_length = len(AUTO_INDEX_QUEUE)
            if queue_length > 0:
                # Bheed me se pehli 200 files uthao
                batch_to_save = AUTO_INDEX_QUEUE[:BATCH_SIZE]
                AUTO_INDEX_QUEUE = AUTO_INDEX_QUEUE[BATCH_SIZE:]
            else:
                batch_to_save = []
                
        if batch_to_save:
            try:
                # DB me bulk write (Takes ~0.5s)
                saved, dups = await Media.save_batch(batch_to_save)
                remaining = len(AUTO_INDEX_QUEUE) 
                
                if saved > 0 or dups > 0:
                    logger.info(f"🚀 Auto-Batch -> Saved: {saved} | Dups: {dups} | Remaining in Queue: {remaining}")
            except Exception as e:
                logger.error(f"❌ Auto-Batch Error: {e}")
                
            # 🔥 TURBO MODE: Files process karne ke baad sirf 0.5 second ruko, fir agli 200 uthao!
            await asyncio.sleep(0.5)
            
        else:
            # 🐢 IDLE MODE: Agar queue me kuch nahi hai, toh 5 second wait karo (CPU Save)
            await asyncio.sleep(5)


# ✅ LIVE LISTENER: Ye sirf files ko queue me daalega
@Client.on_message(filters.channel & (filters.document | filters.video)) 
async def live_indexing(bot, message):
    """
    Automatically saves files from ANY channel where the bot is added (with Turbo Queue system).
    """
    # 1. 🛡️ Crash Protection Check
    if not message or getattr(message, "empty", False):
        return

    # 2. 🛡️ Anti-Spam Security Check
    # Ye check karega ki is channel me aapka koi main Admin add hai ya nahi.
    # Agar koi anjaan aadmi bot ko apne channel me add karega toh bot ignore kar dega.
    try:
        chat_admins = [admin.user.id async for admin in bot.get_chat_members(message.chat.id, filter=filters.ChatMembersFilter.ADMINISTRATORS)]
        if not any(admin_id in chat_admins for admin_id in ADMINS):
            return
    except Exception:
        pass 

    media = message.document or message.video 
    if not media:
        return

    # 3. 📥 File ko Queue (Waiting list) me daal do
    async with QUEUE_LOCK:
        AUTO_INDEX_QUEUE.append((media, message))

