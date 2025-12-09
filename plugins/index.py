import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from info import ADMINS

INDEX_CACHE = {}
RUNNING_TASKS = {}

@Client.on_message(filters.command("delete_all") & filters.user(ADMINS), group=-1)
async def delete_database_handler(bot, message):
    btn = [[
        InlineKeyboardButton("✅ YES, Delete All", callback_data="confirm_delete"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")
    ]]
    await message.reply_text("⚠️ **WARNING:** Kya aap Saara Data Delete karna chahte hain?", reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex("^confirm_delete"))
async def confirm_delete_handler(bot, query):
    if query.from_user.id not in ADMINS: return
    await query.message.edit_text("⏳ **Deleting Database...**")
    try:
        await Media.db.drop_collection("files_data")
        await Media.db.drop_collection("files_search")
        await Media.db.drop_collection("counters")
        await Media.ensure_indexes()
        await query.message.edit_text("✅ **Reset Successful!**")
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {e}")

@Client.on_message(filters.command("index") & filters.user(ADMINS), group=-1)
async def step_one_index(bot, message):
    INDEX_CACHE[message.from_user.id] = {
        'state': 'waiting_forward',
        'chat_id': None, 'last_msg_id': 0, 'skip': 0
    }
    await message.reply_text("**🆔 Step 1:** Apne Channel se **Last Message** forward kijiye.")

@Client.on_message(filters.forwarded & filters.user(ADMINS), group=-1)
async def step_two_forward(bot, message):
    user_id = message.from_user.id
    if user_id in INDEX_CACHE and INDEX_CACHE[user_id]['state'] == 'waiting_forward':
        if message.forward_from_chat:
            INDEX_CACHE[user_id]['chat_id'] = message.forward_from_chat.id
            INDEX_CACHE[user_id]['last_msg_id'] = message.forward_from_message_id
            INDEX_CACHE[user_id]['state'] = 'waiting_skip'
            await message.reply_text(f"✅ **Detected!** Last ID: `{message.forward_from_message_id}`\n\n**Step 2:** Skip Number bhejein (e.g. 0).")
        else:
            await message.reply("❌ Direct Channel se forward karein.")

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
            InlineKeyboardButton("🚀 FAST Start", callback_data="start_index"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")
        ]]
        await message.reply_text(f"📊 **Ready (Ultra Fast Mode)**\nTotal: {total}", reply_markup=InlineKeyboardMarkup(buttons))

# --- ULTRA FAST INDEXING LOGIC ---
@Client.on_callback_query(filters.regex("^start_index"))
async def start_index(bot, query):
    user_id = query.from_user.id
    if user_id not in INDEX_CACHE: return await query.answer("Expired.", show_alert=True)
    
    data = INDEX_CACHE[user_id]
    del INDEX_CACHE[user_id]
    RUNNING_TASKS[user_id] = True
    
    await query.message.edit_text("🚀 **Initializing Ultra-Fast Indexing...**")
    
    chat_id = data['chat_id']
    last_id = data['last_msg_id']
    current = data['skip'] + 1
    
    stats = {
        'total': 0, 'saved': data['skip'], 'dup': 0, 'skip': 0
    }
    
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")]])
    BATCH_SIZE = 200

    try:
        while current <= last_id:
            if user_id not in RUNNING_TASKS: break 

            end = min(current + BATCH_SIZE, last_id + 1)
            ids_to_fetch = list(range(current, end))
            
            try:
                # 1. Fetch
                msgs = await bot.get_messages(chat_id, ids_to_fetch)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except Exception as e:
                await query.message.edit(f"❌ Error fetching: {e}")
                break

            batch_tasks = [] # List for Bulk Save
            
            for m in msgs:
                stats['total'] += 1
                if not m or m.empty: continue
                
                # Sirf Video/Docs
                media = m.document or m.video 
                if media:
                    batch_tasks.append((media, m))
                else:
                    stats['skip'] += 1

            # 2. BULK SAVE (Yahan Magic Hoga)
            if batch_tasks:
                saved, dups = await Media.save_batch(batch_tasks)
                stats['saved'] += saved
                stats['dup'] += dups

            # 3. Status Update
            try: 
                msg_text = (
                    f"🚀 **Ultra-Fast Indexing...**\n"
                    f"📥 Scanned: {min(end, last_id)} / {last_id}\n"
                    f"✅ **Saved:** {stats['saved']}\n"
                    f"♻️ **Duplicates:** {stats['dup']}\n"
                    f"🗑️ Skipped: {stats['skip']}"
                )
                await query.message.edit(msg_text, reply_markup=cancel_btn)
            except: pass
            
            current += BATCH_SIZE
            
    except Exception as e:
        await query.message.reply(f"Error: {e}")

    if user_id in RUNNING_TASKS: del RUNNING_TASKS[user_id]
    
    await query.message.edit(f"✅ **Complete!**\nTotal Saved: {stats['saved']}\nDuplicates: {stats['dup']}")

@Client.on_callback_query(filters.regex("^cancel_index"))
async def cancel(bot, query):
    user_id = query.from_user.id
    if user_id in INDEX_CACHE: del INDEX_CACHE[user_id]
    if user_id in RUNNING_TASKS: del RUNNING_TASKS[user_id]
    await query.message.edit("🛑 Stopped.")
