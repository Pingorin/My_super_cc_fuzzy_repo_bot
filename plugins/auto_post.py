import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db

# ==============================================================================
# 🧹 HELPER: AUTO-DELETE AD MESSAGE
# ==============================================================================
async def delete_autopost_msg(message, delay):
    """Bheje gaye ad ko delay (seconds) ke baad chupchap delete karega"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

# ==============================================================================
# ⏳ AUTO POST SCHEDULER (PRO VERSION - MULTI MEDIA & AUTO-DELETE)
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
                    
                    # Fetch Ad Delete Time (Default 1 mins = 60 sec)
                    ad_del_time = group.get('autopost_del_time', 60)
                    
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
                        sent_msg = None
                        sent_msg_text = None # Sticker ke sath alag text bhejna padta hai
                        
                        # Send Ad based on Media Type
                        if ad_media:
                            if media_type == 'video':
                                sent_msg = await client.send_video(chat_id, video=ad_media, caption=ad_text or "", reply_markup=reply_markup)
                            elif media_type == 'animation':
                                sent_msg = await client.send_animation(chat_id, animation=ad_media, caption=ad_text or "", reply_markup=reply_markup)
                            elif media_type == 'audio':
                                sent_msg = await client.send_audio(chat_id, audio=ad_media, caption=ad_text or "", reply_markup=reply_markup)
                            elif media_type == 'sticker':
                                # Stickers cannot have captions in Telegram
                                sent_msg = await client.send_sticker(chat_id, sticker=ad_media, reply_markup=reply_markup if not ad_text else None)
                                # If there is text along with the sticker, send it separately
                                if ad_text:
                                    sent_msg_text = await client.send_message(chat_id, text=ad_text, reply_markup=reply_markup)
                            else:
                                # Default is Photo
                                sent_msg = await client.send_photo(chat_id, photo=ad_media, caption=ad_text or "", reply_markup=reply_markup)
                        else:
                            # If only Text is available
                            sent_msg = await client.send_message(chat_id, text=ad_text, reply_markup=reply_markup)
                        
                        # 🔥 TIMER: 1, 2, 3, 5, 10, 15, 30 Min baad Ad delete
                        if sent_msg and ad_del_time > 0:
                            asyncio.create_task(delete_autopost_msg(sent_msg, ad_del_time))
                        
                        # Agar sticker ke sath alag se text bheja tha, toh use bhi delete karo
                        if sent_msg_text and ad_del_time > 0:
                            asyncio.create_task(delete_autopost_msg(sent_msg_text, ad_del_time))
                        
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
