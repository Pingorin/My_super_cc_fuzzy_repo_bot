import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from info import ADMINS

INDEX_CACHE = {}
RUNNING_TASKS = {}

# --- COMMANDS ---
@Client.on_message(filters.command("delete_all") & filters.user(ADMINS), group=-1)
async def delete_database_handler(bot, message):
    btn = [[
        InlineKeyboardButton("✅ YES, Delete All", callback_data="confirm_delete"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")
    ]]
    await message.reply_text(
        "⚠️ **WARNING: DATABASE RESET** ⚠️\n\n"
        "Kya aap sach me **Saara Data Delete** karna chahte hain?\n",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query(filters.regex("^confirm_delete"))
async def confirm_delete_handler(bot, query):
    if query.from_user.id not in ADMINS: return
    await query.message.edit_text("⏳ **Deleting Database...** Please wait.")
    try:
        await Media.db.drop_collection("files_data")
        await Media.db.drop_collection("files_search")
        await Media.db.drop_collection("counters")
        await Media.ensure_indexes()
        await query.message.edit_text("✅ **Database Reset Successful!** 🗑️")
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {e}")

@Client.on_message(filters.command("index") & filters.user(ADMINS), group=-1)
async def step_one_index(bot, message):
    INDEX_CACHE[message.from_user.id] = {
        'state': 'waiting_forward',
        'chat_id': None, 'last_msg_id': 0, 'skip': 0
    }
    await message.reply_text("**🆔 Step 1:** Apne Movie Channel se **Last Message** forward kijiye.")

@Client.on_message(filters.forwarded & filters.user(ADMINS), group=-1)
async def step_two_forward(bot, message):
    user_id = message.from_user.id
    if user_id in INDEX_CACHE and INDEX_CACHE[user_id]['state'] == 'waiting_forward':
        if message.forward_from_chat:
            INDEX_CACHE[user_id]['chat_id'] = message.forward_from_chat.id
            INDEX_CACHE[user_id]['last_msg_id'] = message.forward_from_message_id
            INDEX_CACHE[user_id]['state'] = 'waiting_skip'
            await message.reply_text(f"✅ **Channel Detected!**\nLast ID: `{message.forward_from_message_id}`\n\n**Step 2:** Skip Number bhejein (e.g. 0).")
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
            InlineKeyboardButton("🚀 Start Indexing", callback_data="start_index"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")
        ]]
        await message.reply_text(f"📊 **Ready**\nTotal: {total}\nSkip: {skip}", reply_markup=InlineKeyboardMarkup(buttons))

# --- MAIN INDEXING LOGIC (Strict Filter) ---
@Client.on_callback_query(filters.regex("^start_index"))
async def start_index(bot, query):
    user_id = query.from_user.id
    if user_id not in INDEX_CACHE: return await query.answer("Expired.", show_alert=True)
    
    data = INDEX_CACHE[user_id]
    del INDEX_CACHE[user_id]
    RUNNING_TASKS[user_id] = True
    
    await query.message.edit_text("🚀 **Initializing Indexing...**")
    
    chat_id = data['chat_id']
    last_id = data['last_msg_id']
    current = data['skip'] + 1
    
    stats = {
        'total_received': 0,
        'saved': data['skip'], # Total count me skip add rahega
        'duplicates': 0,
        'deleted': 0,
        'non_media': 0,   
        'unsupported': 0, # Audio, Photos ab yahan count honge
        'errors': 0
    }
    
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel Indexing", callback_data="cancel_index")]])
    BATCH_SIZE = 200

    try:
        while current <= last_id:
            if user_id not in RUNNING_TASKS: break 

            end = min(current + BATCH_SIZE, last_id + 1)
            ids_to_fetch = list(range(current, end))
            
            try:
                msgs = await bot.get_messages(chat_id, ids_to_fetch)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except Exception as e:
                await query.message.edit(f"❌ Error fetching: {e}")
                break

            valid_tasks = [] 
            
            for m in msgs:
                stats['total_received'] += 1
                
                if not m or m.empty:
                    stats['deleted'] += 1
                    continue
                
                # ✅ STRICT FILTER: Sirf Video aur Document allow hain
                # Audio (m.audio) ko hata diya gaya hai
                media = m.document or m.video 
                
                if media:
                    valid_tasks.append(Media.save_file(media, m))
                
                # ❌ Baki sab Unsupported me jayega (Audio, Photo, Sticker etc)
                elif m.audio or m.photo or m.sticker or m.animation:
                    stats['unsupported'] += 1
                    
                else:
                    stats['non_media'] += 1

            if valid_tasks:
                results = await asyncio.gather(*valid_tasks)
                for res in results:
                    if res == 'saved': 
                        stats['saved'] += 1
                    elif res == 'duplicate': 
                        stats['saved'] += 1 # Count as saved but listed as dup
                        stats['duplicates'] += 1
                    else: 
                        stats['errors'] += 1

            try: 
                msg_text = (
                    f"**Database: Primary**\n"
                    f"Total messages received: {stats['total_received']}\n"
                    f"✅ **Total Saved (Videos/Docs): {stats['saved']}**\n"
                    f"♻️ Duplicates Skipped: {stats['duplicates']}\n"
                    f"🗑️ Deleted Messages: {stats['deleted']}\n"
                    f"🚫 **Unsupported Skipped:** {stats['unsupported']}\n"
                    f"📝 Text Messages: {stats['non_media']}\n"
                    f"⚠️ Errors: {stats['errors']}\n\n"
                    f"⚡ **Processing...**"
                )
                await query.message.edit(msg_text, reply_markup=cancel_btn)
            except: pass
            
            current += BATCH_SIZE
            
    except Exception as e:
        await query.message.reply(f"Error: {e}")

    if user_id in RUNNING_TASKS: del RUNNING_TASKS[user_id]
    
    final_text = (
        f"✅ **Indexing Completed!**\n\n"
        f"📂 **Total Files Saved:** {stats['saved']}\n"
        f"♻️ Duplicates: {stats['duplicates']}\n"
        f"🚫 Unsupported Media Skipped: {stats['unsupported']}\n"
        f"⚠️ Errors: {stats['errors']}"
    )
    await query.message.edit(final_text)

@Client.on_callback_query(filters.regex("^cancel_index"))
async def cancel(bot, query):
    user_id = query.from_user.id
    if user_id in INDEX_CACHE: del INDEX_CACHE[user_id]
    if user_id in RUNNING_TASKS: del RUNNING_TASKS[user_id]
    await query.message.edit("🛑 Stopped.")
