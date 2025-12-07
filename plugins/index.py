import asyncio
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from info import ADMINS

# Temporary Memory
INDEX_CACHE = {}

# --- STEP 1: Command Aaya ---
@Client.on_message(filters.command("index") & filters.user(ADMINS))
async def step_one_index(bot, message):
    INDEX_CACHE[message.from_user.id] = {
        'state': 'waiting_forward',
        'chat_id': None,
        'last_msg_id': 0,
        'skip': 0
    }
    await message.reply_text(
        "**🆔 Step 1: Forward Last Message**\n\n"
        "Apne Movie Channel me jayiye, **Sabse Niche wala (Last)** message select kijiye aur yahan **Forward** kijiye.\n\n"
        "_(Isse mujhe pata chalega ki total kitni files hain)_"
    )

# --- STEP 2: Forward Message Receive Hua ---
# Note: 'filters.forwarded' use kiya hai jo sahi hai
@Client.on_message(filters.forwarded & filters.user(ADMINS))
async def step_two_forward(bot, message):
    user_id = message.from_user.id
    
    # Check agar user session mein hai
    if user_id in INDEX_CACHE and INDEX_CACHE[user_id]['state'] == 'waiting_forward':
        
        try:
            if message.forward_from_chat:
                target_chat_id = message.forward_from_chat.id
                last_msg_id = message.forward_from_message_id
            else:
                return await message.reply("❌ Ye Channel ka message nahi lag raha. Channel se direct forward karein.")
        except:
            return await message.reply("❌ Error! Sahi se forward nahi hua.")

        INDEX_CACHE[user_id]['chat_id'] = target_chat_id
        INDEX_CACHE[user_id]['last_msg_id'] = last_msg_id
        INDEX_CACHE[user_id]['state'] = 'waiting_skip'

        await message.reply_text(
            f"✅ **Channel Detected:** `{target_chat_id}`\n"
            f"📄 **Last Message ID:** `{last_msg_id}`\n\n"
            f"**🆔 Step 2: Set Skip Number**\n"
            f"Agar shuru ke kuch messages chhodne hain to number bhejo.\n"
            f"Agar shuru se scan karna hai to **0** bhejo."
        )

# --- STEP 3: Skip Number Aaya (DEBUG MODE) ---
# Sirf Numbers ko pakdega
@Client.on_message(filters.regex(r"^\d+$") & filters.user(ADMINS))
async def step_three_skip(bot, message):
    user_id = message.from_user.id
    
    # SCENARIO 1: Sab Sahi Hai
    if user_id in INDEX_CACHE and INDEX_CACHE[user_id]['state'] == 'waiting_skip':
        try:
            skip = int(message.text)
        except:
            return await message.reply("❌ Kripya sirf number bhejein (Example: 0).")

        INDEX_CACHE[user_id]['skip'] = skip
        INDEX_CACHE[user_id]['state'] = 'ready'
        
        data = INDEX_CACHE[user_id]
        total_approx = data['last_msg_id'] - skip

        buttons = [[
            InlineKeyboardButton(f"🚀 Start Indexing ({total_approx} Msgs)", callback_data="start_index"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_index")
        ]]
        
        await message.reply_text(
            f"📊 **Indexing Summary**\n\n"
            f"📢 Channel ID: `{data['chat_id']}`\n"
            f"🔢 Total Range: `{skip}` se `{data['last_msg_id']}` tak\n"
            f"📂 Total Messages to Check: `{total_approx}`\n\n"
            f"Kya main start karu?",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    
    # SCENARIO 2: Bot Restart Ho Gaya Tha (Session Lost)
    elif user_id not in INDEX_CACHE:
        # Agar user number bhej raha hai par cache mein nahi hai, to batayein
        # (Ye optional reply hai taaki pata chale ki bot zinda hai par bhool gaya hai)
        # Aap chahein to ise hata sakte hain agar spam lage
        await message.reply("⚠️ **Session Expired / Bot Restarted**\n\nBot shayad crash hokar restart hua hai. Kripya shuru se `/index` command dein.")

# --- STEP 4: Start Button Click ---
@Client.on_callback_query(filters.regex("^start_index"))
async def start_indexing_callback(bot, query):
    user_id = query.from_user.id
    
    if user_id not in INDEX_CACHE or INDEX_CACHE[user_id]['state'] != 'ready':
        return await query.answer("Session expired. Dobara /index command dein.", show_alert=True)

    data = INDEX_CACHE[user_id]
    chat_id = data['chat_id']
    last_id = data['last_msg_id']
    skip = data['skip']
    
    del INDEX_CACHE[user_id]
    
    await query.message.edit_text("⏳ **Initializing...** Database connect kar raha hu...")
    
    total_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    
    status_msg = query.message
    current_id = skip + 1
    
    try:
        while current_id <= last_id:
            end_id = min(current_id + 200, last_id + 1)
            ids_to_fetch = list(range(current_id, end_id))
            
            try:
                messages = await bot.get_messages(chat_id, ids_to_fetch)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue
            except Exception as e:
                await status_msg.edit(f"❌ Error fetching messages: `{e}`")
                return

            for message in messages:
                if message is None or message.empty:
                    deleted += 1
                    continue
                
                media = message.document or message.video or message.audio
                if media:
                    res = await Media.save_file(media)
                    if res == 'saved':
                        total_files += 1
                    elif res == 'duplicate':
                        duplicate += 1
                    elif res == 'error':
                        errors += 1
                else:
                    deleted += 1

            try:
                if current_id % 200 == 0:
                    await status_msg.edit(
                        f"⚙️ **Indexing in Progress...**\n\n"
                        f"📥 Scanned: {min(end_id, last_id)} / {last_id}\n"
                        f"✅ Saved: {total_files}\n"
                        f"♻️ Duplicates: {duplicate}\n"
                        f"🗑️ Skipped: {deleted}\n"
                    )
            except:
                pass
            
            current_id += 200

    except Exception as e:
        await status_msg.reply(f"❌ Indexing Stopped: {e}")

    await status_msg.edit(
        f"✅ **Indexing Completed Successfully!**\n\n"
        f"📂 Total Files Saved: **{total_files}**\n"
        f"♻️ Duplicates Ignored: **{duplicate}**\n"
        f"🗑️ Skipped Messages: **{deleted}**\n"
        f"⚠️ Errors: **{errors}**"
    )

# --- Cancel Button ---
@Client.on_callback_query(filters.regex("^cancel_index"))
async def cancel_indexing(bot, query):
    if query.from_user.id in INDEX_CACHE:
        del INDEX_CACHE[query.from_user.id]
    await query.message.edit("❌ Indexing Cancelled.")
