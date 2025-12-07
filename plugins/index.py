import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from info import ADMINS

# Global Variables
INDEX_CACHE = {}
RUNNING_TASKS = {}

# --- COMMANDS ---

# 1. DELETE ALL DATA (Reset Command)
@Client.on_message(filters.command("delete_all") & filters.user(ADMINS), group=-1)
async def delete_database_handler(bot, message):
    btn = [[
        InlineKeyboardButton("✅ YES, Delete All", callback_data="confirm_delete"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")
    ]]
    await message.reply_text(
        "⚠️ **WARNING: DATABASE RESET** ⚠️\n\n"
        "Kya aap sach me **Saara Data Delete** karna chahte hain?\n"
        "(Ye files_data, files_search aur counters sab uda dega).\n\n"
        "Search error theek karne ke liye ye zaruri hai.",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query(filters.regex("^confirm_delete"))
async def confirm_delete_handler(bot, query):
    await query.message.edit_text("⏳ **Deleting Database...** Please wait.")
    
    try:
        # Drop Collections
        await Media.db.drop_collection("files_data")
        await Media.db.drop_collection("files_search")
        await Media.db.drop_collection("counters")
        
        # Re-create Indexes
        await Media.ensure_indexes()
        
        await query.message.edit_text(
            "✅ **Database Reset Successful!** 🗑️\n\n"
            "Ab Database 100% Clean hai.\n"
            "Kripya ab **/index** command dekar shuru se indexing karein.\n"
            "Ab 'Button Invalid' wala error nahi aayega."
        )
    except Exception as e:
        await query.message.edit_text(f"❌ Error: {e}")


# 2. INDEX COMMAND (Standard)
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

@Client.on_message(filters.forwarded & filters.user(ADMINS), group=-1)
async def step_two_forward(bot, message):
    user_id = message.from_user.id
    if user_id in INDEX_CACHE and INDEX_CACHE[user_id]['state'] == 'waiting_forward':
        if message.forward_from_chat:
            INDEX_CACHE[user_id]['chat_id'] = message.forward_from_chat.id
            INDEX_CACHE[user_id]['last_msg_id'] = message.forward_from_message_id
            INDEX_CACHE[user_id]['state'] = 'waiting_skip'
            await message.reply_text(f"✅ **Detected!**\nLast ID: `{message.forward_from_message_id}`\n\n**🆔 Step 2:** Ab **Skip Number** (e.g., 0) bhejein.")
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
        
        buttons = [[InlineKeyboardButton("🚀 Start Indexing", callback_data="start_index")]]
        await message.reply_text(f"📊 **Ready!**\nTotal: {total}\nSkip: {skip}", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex("^start_index"))
async def start_index(bot, query):
    user_id = query.from_user.id
    if user_id not in INDEX_CACHE: return await query.answer("Expired.", show_alert=True)
    
    data = INDEX_CACHE[user_id]
    del INDEX_CACHE[user_id]
    RUNNING_TASKS[user_id] = True
    
    await query.message.edit_text("⏳ **Initializing...**")
    
    chat_id = data['chat_id']
    last_id = data['last_msg_id']
    current = data['skip'] + 1
    
    stats = {'saved': data['skip'], 'new': 0, 'dup': 0, 'err': 0}
    
    try:
        while current <= last_id:
            if user_id not in RUNNING_TASKS: break
            end = min(current + 200, last_id + 1)
            try:
                msgs = await bot.get_messages(chat_id, list(range(current, end)))
            except Exception:
                break

            for m in msgs:
                if not m or m.empty: continue
                media = m.document or m.video or m.audio
                if media:
                    # Save logic
                    res = await Media.save_file(media, m) 
                    if res == 'saved': 
                        stats['saved'] += 1
                        stats['new'] += 1
                    elif res == 'duplicate': 
                        stats['saved'] += 1
                        stats['dup'] += 1
                    else: stats['err'] += 1

            try: await query.message.edit(f"⚙️ **Indexing...**\nTotal: {stats['saved']}\nNew: {stats['new']}")
            except: pass
            current += 200
            
    except Exception as e:
        await query.message.reply(f"Error: {e}")
        
    if user_id in RUNNING_TASKS: del RUNNING_TASKS[user_id]
    await query.message.edit(f"✅ **Complete!**\nTotal DB Size: {stats['saved']}\nNew Files: {stats['new']}")
