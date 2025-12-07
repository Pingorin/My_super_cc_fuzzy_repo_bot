import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from info import ADMINS

INDEX_CACHE = {}
RUNNING_TASKS = {}

@Client.on_message(filters.command("index") & filters.user(ADMINS), group=-1)
async def step_one_index(bot, message):
    INDEX_CACHE[message.from_user.id] = {
        'state': 'waiting_forward',
        'chat_id': None, 'last_msg_id': 0, 'skip': 0
    }
    await message.reply_text("**🆔 Step 1: Forward Last Message**\nApne Channel se Last Message forward karein.")

@Client.on_message(filters.forwarded & filters.user(ADMINS), group=-1)
async def step_two_forward(bot, message):
    user_id = message.from_user.id
    if user_id in INDEX_CACHE and INDEX_CACHE[user_id]['state'] == 'waiting_forward':
        if message.forward_from_chat:
            INDEX_CACHE[user_id]['chat_id'] = message.forward_from_chat.id
            INDEX_CACHE[user_id]['last_msg_id'] = message.forward_from_message_id
            INDEX_CACHE[user_id]['state'] = 'waiting_skip'
            await message.reply_text(f"✅ **Channel Detected!** ID: `{message.forward_from_chat.id}`\n**Step 2:** Skip number bhejein (e.g. 0).")
        else:
            await message.reply("❌ Direct Channel se forward karein.")

@Client.on_message(filters.regex(r"^\d+$") & filters.user(ADMINS), group=-1)
async def step_three_skip(bot, message):
    user_id = message.from_user.id
    if user_id not in INDEX_CACHE: return
    if INDEX_CACHE[user_id]['state'] == 'waiting_skip':
        INDEX_CACHE[user_id]['skip'] = int(message.text)
        INDEX_CACHE[user_id]['state'] = 'ready'
        data = INDEX_CACHE[user_id]
        total = data['last_msg_id'] - int(message.text)
        await message.reply_text(f"📊 **Ready!** Total: {total}\nStart karu?", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 Start", callback_data="start_index"), InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")]]))

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
    
    cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")]])
    
    try:
        while current <= last_id:
            if user_id not in RUNNING_TASKS: break
            end = min(current + 200, last_id + 1)
            try:
                msgs = await bot.get_messages(chat_id, list(range(current, end)))
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except: break

            for m in msgs:
                if not m or m.empty: continue
                media = m.document or m.video or m.audio
                if media:
                    # ✅ Saving logic passes the message 'm'
                    res = await Media.save_file(media, m)
                    if res == 'saved': 
                        stats['saved'] += 1
                        stats['new'] += 1
                    elif res == 'duplicate': 
                        stats['saved'] += 1
                        stats['dup'] += 1
                    else: stats['err'] += 1
            
            try: await query.message.edit(f"⚙️ **Running...**\nSaved: {stats['saved']}", reply_markup=cancel_btn)
            except: pass
            current += 200
            
    except Exception as e: await query.message.reply(f"Error: {e}")
    if user_id in RUNNING_TASKS: del RUNNING_TASKS[user_id]
    await query.message.edit(f"✅ **Done!**\nTotal: {stats['saved']}\nNew: {stats['new']}")

@Client.on_callback_query(filters.regex("^cancel_index"))
async def cancel(bot, query):
    user_id = query.from_user.id
    if user_id in INDEX_CACHE: del INDEX_CACHE[user_id]
    if user_id in RUNNING_TASKS: del RUNNING_TASKS[user_id]
    await query.message.edit("❌ Cancelled.")
