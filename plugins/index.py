import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from info import ADMINS

# Global Variable for Memory
INDEX_CACHE = {}

# --- STEP 1: Command Handler ---
@Client.on_message(filters.command("index") & filters.user(ADMINS))
async def step_one_index(bot, message):
    print(f"DEBUG: /index command received from {message.from_user.id}")
    INDEX_CACHE[message.from_user.id] = {
        'state': 'waiting_forward',
        'chat_id': None,
        'last_msg_id': 0,
        'skip': 0
    }
    await message.reply_text(
        "**🆔 Step 1: Forward Last Message**\n\n"
        "Apne Movie Channel se **Last Message** forward kijiye."
    )

# --- STEP 2: Forward Handler ---
@Client.on_message(filters.forwarded & filters.user(ADMINS))
async def step_two_forward(bot, message):
    user_id = message.from_user.id
    print(f"DEBUG: Forward received from {user_id}")
    
    if user_id in INDEX_CACHE and INDEX_CACHE[user_id]['state'] == 'waiting_forward':
        try:
            if message.forward_from_chat:
                target_chat_id = message.forward_from_chat.id
                last_msg_id = message.forward_from_message_id
            else:
                return await message.reply("❌ Ye Channel ka message nahi hai. Direct Channel se forward karein.")
        except Exception as e:
            return await message.reply(f"❌ Error: {e}")

        INDEX_CACHE[user_id]['chat_id'] = target_chat_id
        INDEX_CACHE[user_id]['last_msg_id'] = last_msg_id
        INDEX_CACHE[user_id]['state'] = 'waiting_skip'

        await message.reply_text(
            f"✅ **Channel Detected:** `{target_chat_id}`\n"
            f"📄 **Last ID:** `{last_msg_id}`\n\n"
            f"**🆔 Step 2:** Ab **Skip Number** (e.g., 0) likh kar bhejein."
        )

# --- STEP 3: Skip Number Handler (SUPER DEBUG) ---
@Client.on_message(filters.text & filters.user(ADMINS))
async def step_three_skip(bot, message):
    user_id = message.from_user.id
    text = message.text
    print(f"DEBUG: Text received from {user_id}: {text}")

    # Agar user ka koi session hi nahi hai (Bot Restarted)
    if user_id not in INDEX_CACHE:
        # Sirf numbers par reply karein taaki normal chat disturb na ho
        if text.isdigit():
            await message.reply("⚠️ **Session Expired!**\n\nBot restart hone ki wajah se memory saaf ho gayi hai.\nKripya dobara `/index` command dein.")
        return

    # Agar session hai, check karein ki wo kis state mein hai
    state = INDEX_CACHE[user_id]['state']
    
    if state == 'waiting_skip':
        if not text.isdigit():
            return await message.reply("❌ Sirf Number bhejein (Example: 0)")
        
        skip = int(text)
        INDEX_CACHE[user_id]['skip'] = skip
        INDEX_CACHE[user_id]['state'] = 'ready'
        
        data = INDEX_CACHE[user_id]
        total = data['last_msg_id'] - skip
        
        buttons = [[
            InlineKeyboardButton("🚀 Start Indexing", callback_data="start_index"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")
        ]]
        
        await message.reply_text(
            f"📊 **Ready to Index**\nTotal Files: {total}\nSkip: {skip}\n\nStart karu?",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# --- STEP 4: Start Indexing ---
@Client.on_callback_query(filters.regex("^start_index"))
async def start_indexing_callback(bot, query):
    user_id = query.from_user.id
    
    if user_id not in INDEX_CACHE:
        return await query.answer("Bot Restarted. Dobara /index karein.", show_alert=True)

    data = INDEX_CACHE[user_id]
    # Cache clear kar rahe hain taaki memory free ho
    del INDEX_CACHE[user_id]
    
    chat_id = data['chat_id']
    last_id = data['last_msg_id']
    skip = data['skip']
    
    await query.message.edit_text("⏳ **Initializing...**")
    
    # Counters
    stats = {'saved': 0, 'dup': 0, 'err': 0, 'del': 0}
    status_msg = query.message
    
    # Batch Processing
    current = skip + 1
    BATCH_SIZE = 200
    
    try:
        while current <= last_id:
            end = min(current + BATCH_SIZE, last_id + 1)
            ids = list(range(current, end))
            
            try:
                msgs = await bot.get_messages(chat_id, ids)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except Exception as e:
                await status_msg.edit(f"❌ Error: {e}")
                return

            for m in msgs:
                if not m or m.empty:
                    stats['del'] += 1
                    continue
                
                media = m.document or m.video or m.audio
                if media:
                    res = await Media.save_file(media)
                    if res == 'saved': stats['saved'] += 1
                    elif res == 'duplicate': stats['dup'] += 1
                    else: stats['err'] += 1
                else:
                    stats['del'] += 1

            # Update Status every batch
            try:
                await status_msg.edit(
                    f"⚙️ **Indexing...**\n"
                    f"Scan: {min(end, last_id)}/{last_id}\n"
                    f"✅ Saved: {stats['saved']}\n"
                    f"♻️ Dup: {stats['dup']}"
                )
            except: pass
            
            current += BATCH_SIZE

    except Exception as e:
        await status_msg.reply(f"❌ Error: {e}")

    await status_msg.edit(
        f"✅ **Complete!**\nFiles: {stats['saved']}\nDups: {stats['dup']}\nSkipped: {stats['del']}"
    )

@Client.on_callback_query(filters.regex("^cancel_index"))
async def cancel(bot, query):
    if query.from_user.id in INDEX_CACHE: del INDEX_CACHE[query.from_user.id]
    await query.message.edit("❌ Cancelled")
