import logging
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# ==================================================================
# 1️⃣ The `/id` Command Handler
# ==================================================================
@Client.on_message(filters.command("id"))
async def get_id_command(client, message: Message):
    # Basic IDs
    chat_id = message.chat.id
    sender_id = message.from_user.id
    
    text = f"🆔 **ID EXTRACTION**\n\n"
    text += f"🔹 **Current Chat ID:** `{chat_id}`\n"
    text += f"🔹 **Your User ID:** `{sender_id}`\n"
    
    # Agar kisi message par reply kiya gaya hai
    if message.reply_to_message:
        text += "\n📌 **Replied Message Details:**\n"
        
        # Replied User ki ID
        if message.reply_to_message.from_user:
            replied_user_id = message.reply_to_message.from_user.id
            text += f"🔸 **Replied User ID:** `{replied_user_id}`\n"
            
        # Agar replied message kisi Channel/Group se forward hoke aaya tha
        if message.reply_to_message.forward_from_chat:
            fwd_chat_id = message.reply_to_message.forward_from_chat.id
            fwd_chat_title = message.reply_to_message.forward_from_chat.title
            text += f"📢 **Forwarded Chat ID:** `{fwd_chat_id}`\n"
            text += f"📝 **Chat Title:** {fwd_chat_title}\n"
            
        # Agar replied message kisi normal User ka forwarded tha
        elif message.reply_to_message.forward_from:
            fwd_user_id = message.reply_to_message.forward_from.id
            text += f"👤 **Forwarded User ID:** `{fwd_user_id}`\n"
            
        # Agar User ne privacy lagayi hui hai
        elif message.reply_to_message.forward_sender_name:
            text += f"⚠️ **Forwarded User ID:** Hidden (Privacy Enabled)\n"

    await message.reply(text, quote=True)


# ==================================================================
# 2️⃣ Auto-Forward ID Detector (No Command Needed)
# ==================================================================
@Client.on_message(filters.private & filters.forwarded)
async def auto_forward_detector(client, message: Message):
    
    # Condition A: Forwarded from a Channel or Supergroup
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        title = message.forward_from_chat.title
        # Chat type ko clean string me convert karna (e.g., CHANNEL, SUPERGROUP)
        chat_type = str(message.forward_from_chat.type).split(".")[-1] 
        
        text = (
            f"📢 **Forwarded Chat Details:**\n\n"
            f"🔹 **ID:** `{chat_id}`\n"
            f"🔹 **Title:** {title}\n"
            f"🔹 **Type:** {chat_type}"
        )
        await message.reply(text, quote=True)

    # Condition B: Forwarded from a User (Public ID)
    elif message.forward_from:
        user_id = message.forward_from.id
        first_name = message.forward_from.first_name
        
        text = (
            f"👤 **Forwarded User Details:**\n\n"
            f"🔹 **User ID:** `{user_id}`\n"
            f"🔹 **Name:** {first_name}"
        )
        await message.reply(text, quote=True)

    # Condition C: Forwarded from a User with "Forward Privacy" ENABLED
    elif message.forward_sender_name:
        sender_name = message.forward_sender_name
        
        text = (
            f"⚠️ **Privacy Enabled!**\n\n"
            f"Jiska ye message hai (**{sender_name}**), usne apni Telegram settings me 'Forward Privacy' ko ON rakha hai.\n\n"
            f"Is wajah se Telegram unki original User ID chupaa raha hai aur extract karna possible nahi hai."
        )
        await message.reply(text, quote=True)
