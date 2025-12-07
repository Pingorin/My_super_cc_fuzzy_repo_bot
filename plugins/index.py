import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from info import ADMINS

# Global Variables
INDEX_CACHE = {}
RUNNING_TASKS = {}

# --- STEP 1: Command Handler ---
@Client.on_message(filters.command("index") & filters.user(ADMINS), group=-1)
async def step_one_index(bot, message):
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
@Client.on_message(filters.forwarded & filters.user(ADMINS), group=-1)
async def step_two_forward(bot, message):
    user_id = message.from_user.id
    
    if user_id in INDEX_CACHE and INDEX_CACHE[user_id]['state'] == 'waiting_forward':
        try:
            if message.forward_from_chat:
                INDEX_CACHE[user_id]['chat_id'] = message.forward_from_chat.id
                INDEX_CACHE[user_id]['last_msg_id'] = message.forward_from_message_id
                INDEX_CACHE[user_id]['state'] = 'waiting_skip'
                await message.reply_text(f"✅ **Detected!**\nLast ID: `{message.forward_from_message_id}`\n\n**🆔 Step 2:** Ab **Skip Number** (e.g., 235) bhejein.")
            else:
                await message.reply("❌ Ye Channel ka message nahi hai. Direct Channel se forward karein.")
        except Exception as e:
            return await message.reply(f"❌ Error: {e}")

# --- STEP 3: Skip Number Handler ---
@Client.on_message(filters.regex(r"^\d+$") & filters.user(ADMINS), group=-1)
async def step_three_skip(bot, message):
    user_id = message.from_user.id
    if user_id not in INDEX_CACHE: return
    
    if INDEX_CACHE[user_id]['state'] == 'waiting_skip':
        skip = int(message.text)
        INDEX_CACHE[user_id]['skip'] = skip
        INDEX_CACHE[user_id]['state'] = 'ready'
        
        data = INDEX_CACHE[user_id]
        total = data['last_msg_id'] - skip
        
        buttons = [[
            InlineKeyboardButton("🚀 Start Indexing", callback_data="start_index"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")
        ]]
        
        await message.reply_text(
            f"📊 **Ready to Index**\nTotal Range: {total}\nSkip Previous: {skip}\n\nStart karu?",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

# --- STEP 4: Start Indexing (Smart Counter Logic) ---
@Client.on_callback_query(filters.regex("^start_index"))
async def start_index(bot, query):
    user_id = query.from_user.id
    
    if user_id not in INDEX_CACHE:
        return await query.answer("Session expired. Dobara /index karein.", show_alert=True)
    
    data = INDEX_CACHE[user_id]
    del INDEX_CACHE[user_id]
    
    RUNNING_TASKS[user_id] = True
    
    await query.message.edit_text("⏳ **Initializing...**")
    
    chat_id = data['chat_id']
    last_id = data['last_msg_id']
    skip = data['skip']
    current = skip + 1
    
    # ✅ CHANGE: Saved count ko 'skip' se shuru karo
    stats = {
        'saved': skip,  # Agar 235 skip kiya, to count 235 se shuru hoga
        'new_saved': 0, # Ye batayega ki abhi kitni nayi save hui
        'dup': 0, 
        'err': 0
    }
    
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Indexing", callback_data="cancel_index")]])
    
    try:
        while current <= last_id:
            if user_id not in RUNNING_TASKS: break 

            end = min(current + 200, last_id + 1)
            try:
                msgs = await bot.get_messages(chat_id, list(range(current, end)))
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except:
                break 

            for m in msgs:
                if not m or m.empty: continue
                media = m.document or m.video or m.audio
                if media:
                    res = await Media.save_file(media, m) 
                    if res == 'saved': 
                        stats['saved'] += 1
                        stats['new_saved'] += 1
                    elif res == 'duplicate': 
                        # Duplicate hai matlab ye bhi saved hi hai, bas dobara save nahi kiya
                        stats['saved'] += 1 
                        stats['dup'] += 1
                    else: 
                        stats['err'] += 1

            try: 
                await query.message.edit(
                    f"⚙️ **Running...**\n"
                    f"📥 Total Scanned: {min(end, last_id)} / {last_id}\n"
                    f"✅ **Total Saved: {stats['saved']}**\n"
                    f"🆕 Newly Added: {stats['new_saved']}\n"
                    f"♻️ Duplicates Found: {stats['dup']}",
                    reply_markup=cancel_btn
                )
            except: pass
            
            current += 200
            
    except Exception as e:
        await query.message.reply(f"Error: {e}")

    if user_id in RUNNING_TASKS: del RUNNING_TASKS[user_id]

    await query.message.edit(
        f"✅ **Indexing Complete!**\n\n"
        f"📂 **Total Files in DB: {stats['saved']}**\n"
        f"🆕 New Files Added: {stats['new_saved']}\n"
        f"♻️ Duplicates Skipped: {stats['dup']}\n"
        f"⚠️ Errors: {stats['err']}"
    )

@Client.on_callback_query(filters.regex("^cancel_index"))
async def cancel(bot, query):
    user_id = query.from_user.id
    if user_id in INDEX_CACHE:
        del INDEX_CACHE[user_id]
        await query.message.edit("❌ Setup Cancelled.")
        return
    if user_id in RUNNING_TASKS:
        del RUNNING_TASKS[user_id]
        await query.answer("Stopping...", show_alert=True)
        await query.message.edit("🛑 **Indexing Stopped by User.**")
        return
    await query.answer("Nothing to cancel.")
