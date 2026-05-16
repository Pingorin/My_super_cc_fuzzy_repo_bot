import asyncio
from pyrogram import Client, filters, enums
from database.users_chats_db import db

# Default Image (Aap is link ko change kar sakte hain)
DEFAULT_WELCOME_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg"

# --- HELPER: DELETE MESSAGE AFTER DELAY ---
async def delete_after_delay(message, delay):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        pass # Agar message pehle hi delete ho gaya ya permission nahi hai to ignore kare

@Client.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    try:
        chat_id = message.chat.id
        
        # 1. Group Settings Fetch Karein
        group_settings = await db.get_group_settings(chat_id)
        
        # Agar group DB me nahi hai, to add karein (Safety Check)
        if not group_settings:
            await db.add_group(chat_id, message.chat.title)
            group_settings = await db.get_group_settings(chat_id)

        # 2. Check Karein ki Welcome Enabled hai ya nahi
        if not group_settings.get('welcome_enabled', True):
            return

        mode = group_settings.get('welcome_mode', 'default')
        
        # 3. Har naye member ke liye message bhejein
        for user in message.new_chat_members:
            # Bot khud ko welcome na kare
            if user.id == (await client.get_me()).id: continue

            sent_msg = None # To store the sent message object

            # --- DEFAULT MODE ---
            if mode == 'default':
                text = (
                    f"Hello {user.mention}, thanks for joining!\n"
                    f"A WARM WELCOME TO YOU!"
                )
                try:
                    sent_msg = await message.reply_photo(photo=DEFAULT_WELCOME_IMG, caption=text)
                except:
                    # Agar photo bhejne me error aaye (permission etc), to text bheje
                    sent_msg = await message.reply_text(text)

            # --- CUSTOM MODE ---
            elif mode == 'custom':
                custom_text = group_settings.get('custom_welcome_text')
                custom_photo = group_settings.get('custom_welcome_photo')
                
                # Fallback text
                if not custom_text:
                    custom_text = f"Hey {user.mention}, Welcome to {message.chat.title}!"

                # Variables Format Karein
                formatted_text = custom_text.format(
                    mention=user.mention,
                    username=user.username or "User",
                    chat_name=message.chat.title,
                    id=user.id
                )

                try:
                    if custom_photo:
                        sent_msg = await message.reply_photo(photo=custom_photo, caption=formatted_text)
                    else:
                        sent_msg = await message.reply_text(formatted_text)
                except:
                    sent_msg = await message.reply_text(formatted_text)

            # ✅ 4. AUTO DELETE TASK (2 Minutes = 120 Seconds)
            if sent_msg:
                asyncio.create_task(delete_after_delay(sent_msg, 120))

    except Exception as e:
        print(f"Welcome Error: {e}")
