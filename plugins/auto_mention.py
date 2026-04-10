import asyncio
import time
import random
import datetime
import pytz
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db

# ==============================================================================
# 🧹 HELPER: AUTO-DELETE MENTION MESSAGE
# ==============================================================================
async def delete_mention_msg(message, delay=600):
    """10 Minute (600 seconds) baad mention message ko chupchap delete kar dega"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

# ==============================================================================
# 🔄 DEFAULT ROTATING MESSAGES
# ==============================================================================
MSG_LIST = [
    "Hey {mentions} 👋\n\nLooking for the latest movies and series? Just type the name in the group to get instant download links!",
    "Welcome back {mentions} 🍿\n\nWeekend aa gaya hai! Grab your popcorn aur apni favorite movie search karke download karein.",
    "Hello {mentions} 🎬\n\nDid you know? Aap is group mein koi bhi movie high quality mein HD links ke sath direct download kar sakte hain. Try searching now!",
    "Hey {mentions} ⚡\n\nBore ho rahe ho? Click on the 'Trending' button below ya apni manpasand series ka naam likh kar turant link lijiye."
]

# ==============================================================================
# ⏳ BACKGROUND SCHEDULER (Auto Mention - PRO VERSION)
# ==============================================================================

async def auto_mention_scheduler(client):
    while True:
        try:
            await asyncio.sleep(60) # Check every 60 seconds
            
            # 🌙 SLEEP MODE CHECK (Raat 12 se subah 6 baje tak koi mention nahi hoga)
            tz = pytz.timezone('Asia/Kolkata')
            current_time_ist = datetime.datetime.now(tz).time()
            if datetime.time(0, 0) <= current_time_ist <= datetime.time(6, 0):
                continue # Skip loop during quiet hours
            
            # Iterate through all groups in DB where automention is enabled
            async for group in db.groups.find({"automention_enabled": True}):
                chat_id = group['id']
                interval = group.get('mention_interval', 300)
                last_time = group.get('last_mention_time', 0)
                pending = group.get('pending_mentions', [])
                
                # Check Time & Queue
                if pending and (time.time() - last_time) >= interval:
                    # Take top 5 users
                    users_to_mention = pending[:5]
                    
                    mentions = []
                    for uid in users_to_mention:
                        try:
                            # Try to get user info
                            user = await client.get_chat_member(chat_id, uid)
                            mentions.append(user.user.mention)
                        except:
                            pass # If user left or error, skip
                    
                    if mentions:
                        # 📝 CUSTOM YA RANDOM TEXT SELECT KAREIN
                        custom_text = group.get('custom_mention_text')
                        if custom_text:
                            text = custom_text.replace("{mentions}", ', '.join(mentions))
                        else:
                            text = random.choice(MSG_LIST).format(mentions=', '.join(mentions))
                        
                        # 🔘 BUTTONS LOGIC
                        btn = [[InlineKeyboardButton("🔥 Today Popular Movies", callback_data="trend_list#0")]]
                        
                        # ⁉️ HOW TO DOWNLOAD BUTTON (Agar DB me set hai)
                        howto_url = group.get('howto_url')
                        if howto_url:
                            btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
                        
                        try:
                            # Send Mention Message
                            sent_msg = await client.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(btn))
                            
                            # 🧹 TRIGGER AUTO-DELETE TIMER (600 Sec = 10 Min)
                            asyncio.create_task(delete_mention_msg(sent_msg, 600))
                            
                            # Cleanup DB: Remove mentioned users & update time
                            await db.remove_pending_mentions(chat_id, users_to_mention)
                        except Exception as e:
                            print(f"AutoMention Send Error ({chat_id}): {e}")
                            # If send fails (perm issue), clear the list to avoid stuck loop
                            await db.remove_pending_mentions(chat_id, users_to_mention)
                    else:
                        # Clean up invalid IDs from DB if no valid mentions found
                        await db.remove_pending_mentions(chat_id, users_to_mention)

        except Exception as e:
            print(f"Scheduler Error: {e}")
            await asyncio.sleep(10) # Wait a bit before retrying loop
