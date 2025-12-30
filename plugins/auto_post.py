import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db

# ==============================================================================
# ⏳ AUTO POST SCHEDULER
# ==============================================================================

async def auto_post_scheduler(client):
    while True:
        try:
            # Check every 60 seconds
            await asyncio.sleep(60)
            
            # Iterate through all groups with Auto Post Enabled
            async for group in db.groups.find({"autopost_enabled": True}):
                chat_id = group['id']
                interval = group.get('autopost_interval', 1800)
                last_time = group.get('last_autopost_time', 0)
                
                # Check if it's time to post
                if (time.time() - last_time) >= interval:
                    
                    # Fetch Ad Content
                    ad_text = group.get('autopost_text')
                    ad_image = group.get('autopost_image')
                    ad_buttons_data = group.get('autopost_buttons', {})
                    
                    # Validation: Must have at least Text or Image
                    if not ad_text and not ad_image:
                        continue 

                    # Build Buttons
                    markup = []
                    # Sort buttons by slot '1', '2', '3'
                    for slot in sorted(ad_buttons_data.keys()):
                        btn_data = ad_buttons_data[slot]
                        markup.append([InlineKeyboardButton(btn_data['text'], url=btn_data['url'])])
                    
                    reply_markup = InlineKeyboardMarkup(markup) if markup else None
                    
                    try:
                        # Send Ad
                        if ad_image:
                            await client.send_photo(
                                chat_id, 
                                photo=ad_image, 
                                caption=ad_text if ad_text else "", 
                                reply_markup=reply_markup
                            )
                        else:
                            await client.send_message(
                                chat_id, 
                                text=ad_text, 
                                reply_markup=reply_markup
                            )
                        
                        # Update Last Run Time
                        await db.groups.update_one(
                            {'id': chat_id},
                            {'$set': {'last_autopost_time': time.time()}}
                        )
                        
                    except Exception as e:
                        print(f"AutoPost Send Error ({chat_id}): {e}")
                        # If bot kicked/no permission, disable to save resources
                        if "403" in str(e) or "chat not found" in str(e).lower():
                            await db.update_group_settings(chat_id, {'autopost_enabled': False})

        except Exception as e:
            print(f"AutoPost Scheduler Error: {e}")
