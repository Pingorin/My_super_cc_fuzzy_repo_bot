import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db

# ==============================================================================
# ⏳ AUTO POST SCHEDULER (PRO VERSION - MULTI MEDIA SUPPORT)
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
                    
                    # Fetch Media and its Type (Backward compatible with old 'autopost_image')
                    ad_media = group.get('autopost_media_id') or group.get('autopost_image')
                    media_type = group.get('autopost_media_type', 'photo' if group.get('autopost_image') else None)
                    
                    ad_buttons_data = group.get('autopost_buttons', {})
                    
                    # Validation: Must have at least Text or Media
                    if not ad_text and not ad_media:
                        continue 

                    # Build Buttons
                    markup = []
                    for slot in sorted(ad_buttons_data.keys()):
                        btn_data = ad_buttons_data[slot]
                        markup.append([InlineKeyboardButton(btn_data['text'], url=btn_data['url'])])
                    
                    reply_markup = InlineKeyboardMarkup(markup) if markup else None
                    
                    try:
                        # Send Ad based on Media Type
                        if ad_media:
                            if media_type == 'video':
                                await client.send_video(chat_id, video=ad_media, caption=ad_text or "", reply_markup=reply_markup)
                            elif media_type == 'animation':
                                await client.send_animation(chat_id, animation=ad_media, caption=ad_text or "", reply_markup=reply_markup)
                            elif media_type == 'audio':
                                await client.send_audio(chat_id, audio=ad_media, caption=ad_text or "", reply_markup=reply_markup)
                            elif media_type == 'sticker':
                                # Stickers cannot have captions in Telegram
                                await client.send_sticker(chat_id, sticker=ad_media, reply_markup=reply_markup if not ad_text else None)
                                # If there is text along with the sticker, send it separately
                                if ad_text:
                                    await client.send_message(chat_id, text=ad_text, reply_markup=reply_markup)
                            else:
                                # Default is Photo
                                await client.send_photo(chat_id, photo=ad_media, caption=ad_text or "", reply_markup=reply_markup)
                        else:
                            # If only Text is available
                            await client.send_message(chat_id, text=ad_text, reply_markup=reply_markup)
                        
                        # Update Last Run Time
                        await db.groups.update_one(
                            {'id': chat_id},
                            {'$set': {'last_autopost_time': time.time()}}
                        )
                        
                    except Exception as e:
                        print(f"AutoPost Send Error ({chat_id}): {e}")
                        # If bot kicked/no permission, disable to save resources
                        if "403" in str(e) or "chat not found" in str(e).lower():
                            await db.groups.update_one({'id': chat_id}, {'$set': {'autopost_enabled': False}})

        except Exception as e:
            print(f"AutoPost Scheduler Error: {e}")
