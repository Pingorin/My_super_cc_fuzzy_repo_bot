from pyrogram import Client, filters, enums
from database.users_chats_db import db
from info import LOG_CHANNEL

# Default Image (You can change this)
DEFAULT_WELCOME_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg"

@Client.on_message(filters.new_chat_members)
async def welcome_handler(client, message):
    try:
        chat_id = message.chat.id
        group_settings = await db.get_group_settings(chat_id)
        
        # If group not in DB (rare case), add it
        if not group_settings:
            await db.add_group(chat_id, message.chat.title)
            return

        # ==================================================================
        # ✅ AUTO MENTION HOOK (Add Users to Pending List)
        # ==================================================================
        # We do this BEFORE checking if welcome message is enabled, 
        # because Auto Mention is a separate feature.
        for user in message.new_chat_members:
            if not user.is_bot:
                await db.add_pending_mention(chat_id, user.id)
        # ==================================================================

        # Check if Welcome Message is Enabled
        if not group_settings.get('welcome_enabled', True):
            return

        mode = group_settings.get('welcome_mode', 'default')
        
        for user in message.new_chat_members:
            # Skip Bot itself
            if user.id == (await client.get_me()).id: continue

            # --- DEFAULT MODE ---
            if mode == 'default':
                # ✅ Updated Text as per your request
                text = (
                    f"Hello {user.mention}, thanks for joining!\n"
                    f"A WARM WELCOME TO YOU!"
                )
                await message.reply_photo(photo=DEFAULT_WELCOME_IMG, caption=text)

            # --- CUSTOM MODE ---
            elif mode == 'custom':
                custom_text = group_settings.get('custom_welcome_text')
                custom_photo = group_settings.get('custom_welcome_photo')
                
                # Fallback if custom text is empty
                if not custom_text:
                    custom_text = f"Hey {user.mention}, Welcome to {message.chat.title}!"

                # Format Variables
                # Supported: {mention}, {username}, {chat_name}, {id}
                formatted_text = custom_text.format(
                    mention=user.mention,
                    username=user.username or "User",
                    chat_name=message.chat.title,
                    id=user.id
                )

                if custom_photo:
                    await message.reply_photo(photo=custom_photo, caption=formatted_text)
                else:
                    await message.reply_text(formatted_text)

    except Exception as e:
        print(f"Welcome Error: {e}")
