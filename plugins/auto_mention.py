import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db

# ==============================================================================
# ⏳ BACKGROUND SCHEDULER (Auto Mention)
# ==============================================================================

async def auto_mention_scheduler(client):
    while True:
        try:
            # Check every 60 seconds
            await asyncio.sleep(60)
            
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
                            # Try to get user info (might be cached)
                            user = await client.get_chat_member(chat_id, uid)
                            mentions.append(user.user.mention)
                        except:
                            # If user left or error, skip
                            pass
                    
                    if mentions:
                        text = (
                            f"Hey {', '.join(mentions)}\n\n"
                            f"Looking for the latest movies and series? Just type the name in the group to get instant download links!"
                        )
                        
                        # ✅ Button triggers the NEW Trending Plugin (trending.py)
                        btn = [[InlineKeyboardButton("🔥 Today Popular Movies", callback_data="trend_list#0")]]
                        
                        try:
                            await client.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(btn))
                            
                            # Cleanup DB: Remove mentioned users
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
