import asyncio
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from info import ADMINS

INDEX_CACHE = {}

# Priority -1: Taaki ye sabse pehle chale
@Client.on_message(filters.command("index") & filters.user(ADMINS), group=-1)
async def step_one_index(bot, message):
    INDEX_CACHE[message.from_user.id] = {
        'state': 'waiting_forward',
        'chat_id': None,
        'last_msg_id': 0,
        'skip': 0
    }
    await message.reply_text("**🆔 Step 1:** Apne Movie Channel se **Last Message** forward kijiye.")

@Client.on_message(filters.forwarded & filters.user(ADMINS), group=-1)
async def step_two_forward(bot, message):
    user_id = message.from_user.id
    if user_id in INDEX_CACHE and INDEX_CACHE[user_id]['state'] == 'waiting_forward':
        try:
            if message.forward_from_chat:
                INDEX_CACHE[user_id]['chat_id'] = message.forward_from_chat.id
                INDEX_CACHE[user_id]['last_msg_id'] = message.forward_from_message_id
                INDEX_CACHE[user_id]['state'] = 'waiting_skip'
                await message.reply_text(f"✅ **Detected!**\nLast ID: `{message.forward_from_message_id}`\n\n**🆔 Step 2:** Ab **Skip Number** (e.g., 0) bhejein.")
            else:
                await message.reply("❌ Direct Channel se forward karein.")
        except:
            await message.reply("❌ Error in forward.")

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
        await message.reply_text(f"📊 **Ready!**\nTotal Files: {total}\nStart karu?", reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex("^start_index"))
async def start_index(bot, query):
    user_id = query.from_user.id
    if user_id not in INDEX_CACHE: return await query.answer("Expired.", show_alert=True)
    
    data = INDEX_CACHE[user_id]
    del INDEX_CACHE[user_id]
    
    await query.message.edit_text("⏳ **Indexing Started...**")
    
    chat_id = data['chat_id']
    last_id = data['last_msg_id']
    current = data['skip'] + 1
    stats = {'saved': 0, 'dup': 0, 'err': 0}
    
    try:
        while current <= last_id:
            end = min(current + 200, last_id + 1)
            try:
                msgs = await bot.get_messages(chat_id, list(range(current, end)))
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except:
                break # Stop if error

            for m in msgs:
                if not m or m.empty: continue
                media = m.document or m.video or m.audio
                if media:
                    # FIX: 'm' (message) bhi pass kiya hai caption ke liye
                    res = await Media.save_file(media, m) 
                    if res == 'saved': stats['saved'] += 1
                    elif res == 'duplicate': stats['dup'] += 1
                    else: stats['err'] += 1

            try: await query.message.edit(f"⚙️ **Running...**\nSaved: {stats['saved']}\nDups: {stats['dup']}")
            except: pass
            current += 200
            
    except Exception as e:
        await query.message.reply(f"Error: {e}")

    await query.message.edit(f"✅ **Complete!**\nSaved: {stats['saved']}\nDups: {stats['dup']}\nErrors: {stats['err']}")
