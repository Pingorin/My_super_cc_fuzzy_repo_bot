import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from info import ADMINS

INDEX_CACHE = {}
RUNNING_TASKS = {}

# ==============================================================================
# 🗑️ SMART DELETE MANAGER (Surgical Strike)
# ==============================================================================
@Client.on_message(filters.command(["delete_all", "deleteall"]) & filters.user(ADMINS), group=-1)
async def delete_database_handler(bot, message):
    buttons = []
    
    # DB 1 Button (Master)
    buttons.append([InlineKeyboardButton("🗑️ Delete DB 1 (Master + Cache)", callback_data="ask_delete_1")])
    
    # DB 2 Button 
    if Media.has_db2:
        buttons.append([InlineKeyboardButton("🗑️ Delete DB 2", callback_data="ask_delete_2")])
        
    # DB 3 Button 
    if Media.has_db3:
        buttons.append([InlineKeyboardButton("🗑️ Delete DB 3", callback_data="ask_delete_3")])
    
    # Delete ALL Button
    buttons.append([InlineKeyboardButton("💥 Delete ALL Databases (Total Wipe)", callback_data="ask_delete_all")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")])
    
    await message.reply_text("⚠️ **Database Manager:**\nAap kis database ka data clear karna chahte hain?", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^ask_delete_(.*)"))
async def ask_delete_handler(bot, query):
    if query.from_user.id not in ADMINS: return
    db_choice = query.data.split("_")[2]
    
    btn = [[
        InlineKeyboardButton("✅ YES, I am Sure!", callback_data=f"confirm_delete_{db_choice}"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")
    ]]
    
    target_name = "ALL Databases" if db_choice == "all" else f"Database {db_choice}"
    await query.message.edit_text(
        f"⚠️ **FINAL WARNING:**\n"
        f"Kya aap sach me **{target_name}** ka saara data delete karna chahte hain?\n\n"
        f"*(Sirf movies aur links jayenge, Search Indexes aur Settings safe rahenge)*", 
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query(filters.regex(r"^confirm_delete_(.*)"))
async def confirm_delete_handler(bot, query):
    if query.from_user.id not in ADMINS: return
    db_choice = query.data.split("_")[2]
    
    await query.message.edit_text(f"⏳ **Deleting Data from {db_choice.upper()}...**")
    try:
        # 🟢 CLEAR DB 1
        if db_choice in ['1', 'all']:
            await Media.search_col1.delete_many({}) 
            await Media.data_col1.delete_many({})
            # 🔥 COUNTER RESET: Zero se wapas start karne ke liye
            await Media.counters.update_many({}, {"$set": {"sequence_value": 0}})
            
            await Media.search_cache.delete_many({})
            await Media.temp_searches.delete_many({})
        
        # 🔵 CLEAR DB 2
        if db_choice in ['2', 'all'] and Media.has_db2:
            await Media.search_col2.delete_many({})
            await Media.data_col2.delete_many({})
            
        # 🟣 CLEAR DB 3
        if db_choice in ['3', 'all'] and Media.has_db3:
            await Media.search_col3.delete_many({})
            await Media.data_col3.delete_many({})
        
        # Agar current Active DB hi uda diya, toh wapas DB 1 par set kar do
        current_active = await Media.get_active_index_db()
        if db_choice == 'all' or str(current_active) == db_choice:
            await Media.set_active_index_db(1)
        
        target_name = "All Databases" if db_choice == "all" else f"Database {db_choice}"
        await query.message.edit_text(f"✅ **{target_name} Reset Successfully!**\nDatabase ekdum fresh ho chuka hai.")
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {e}")

# ==============================================================================
# 🚀 ULTRA FAST INDEXING SYSTEM
# ==============================================================================
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
            await message.reply_text(f"✅ **Detected!** Last ID: `{message.forward_from_message_id}`\n\n**Step 2:** Skip Number bhejein (Agar shuru se karna hai toh `0` likhein).")
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
        
        active_db = await Media.get_active_index_db()
        
        buttons = [[
            InlineKeyboardButton("🚀 FAST Start", callback_data="start_index"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")
        ]]
        await message.reply_text(f"📊 **Ready (Ultra Fast Mode)**\nTotal Files: {total}\n🎯 **Target:** `Database {active_db}`", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex("^start_index"))
async def start_index(bot, query):
    user_id = query.from_user.id
    if user_id not in INDEX_CACHE: return await query.answer("Session Expired.", show_alert=True)
    
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
                msgs = await bot.get_messages(chat_id, ids_to_fetch)
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
                continue
            except Exception as e:
                await query.message.edit(f"❌ Error fetching: {e}")
                break

            batch_tasks = [] 
            
            for m in msgs:
                stats['total'] += 1
                if not m or getattr(m, "empty", False): continue
                
                media = m.document or m.video 
                if media:
                    batch_tasks.append((media, m))
                else:
                    stats['skip'] += 1

            if batch_tasks:
                saved, dups = await Media.save_batch(batch_tasks)
                stats['saved'] += saved
                stats['dup'] += dups

            # 🔥 FloodWait Safe UI Update
            try: 
                msg_text = (
                    f"🚀 **Ultra-Fast Indexing...**\n\n"
                    f"📥 Scanned: `{min(end, last_id)}` / `{last_id}`\n"
                    f"✅ **Saved:** `{stats['saved']}`\n"
                    f"♻️ **Duplicates:** `{stats['dup']}`\n"
                    f"🗑️ Skipped: `{stats['skip']}`"
                )
                await query.message.edit(msg_text, reply_markup=cancel_btn)
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except Exception: 
                pass
            
            current += BATCH_SIZE
            await asyncio.sleep(0.5) # API safe delay
            
    except Exception as e:
        await query.message.reply(f"Error: {e}")

    if user_id in RUNNING_TASKS: del RUNNING_TASKS[user_id]
    
    await query.message.edit(f"✅ **Complete!**\n\nTotal Saved: `{stats['saved']}`\nDuplicates: `{stats['dup']}`\nSkipped: `{stats['skip']}`")

@Client.on_callback_query(filters.regex("^cancel_index"))
async def cancel(bot, query):
    user_id = query.from_user.id
    if user_id in INDEX_CACHE: del INDEX_CACHE[user_id]
    if user_id in RUNNING_TASKS: del RUNNING_TASKS[user_id]
    await query.message.edit("🛑 Indexing ya Deletion process Cancelled.")
