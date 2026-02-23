import logging
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# User ka state save karne ke liye dictionary
ID_STATES = {}

# ==================================================================
# 1️⃣ The `/id` Command Handler (ID Mode Activate Karne Ke Liye)
# ==================================================================
@Client.on_message(filters.command("id") & filters.private)
async def id_command_handler(client, message: Message):
    user_id = message.from_user.id
    
    # CASE 1: Agar user ne kisi message par Reply karke /id bheja hai
    if message.reply_to_message:
        return await extract_and_send_id(message.reply_to_message, message)
        
    # CASE 2: Agar user ne sirf /id bheja hai (Wait Mode ON karna)
    ID_STATES[user_id] = True
    await message.reply(
        "🆔 **ID Extraction Mode ON**\n\n"
        "Ab aap kisi bhi channel, group ya user ka post yahan **forward** karein, main uski ID nikal kar dunga.\n\n"
        "*(Ek baar ID batane ke baad ye mode apne aap band ho jayega)*"
    )

# ==================================================================
# 2️⃣ The `/info` Command Handler (User Details Nikalne Ke Liye)
# ==================================================================
@Client.on_message(filters.command("info"))
async def user_info_command(client, message: Message):
    
    # Check karna ki reply kiya hai ya direct command di hai
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        heading = "👤 **Replied User Info**"
    else:
        target_user = message.from_user
        heading = "👤 **Your Information**"

    # Details Extract karna
    user_id = target_user.id
    first_name = target_user.first_name or "N/A"
    last_name = target_user.last_name or ""
    username = f"@{target_user.username}" if target_user.username else "N/A"
    dc_id = target_user.dc_id or "Unknown"

    # Profile link banana
    profile_link = f"<a href='tg://user?id={user_id}'>Click Here</a>"

    # Message format karna
    text = f"{heading}\n\n"
    text += f"🔹 **First Name:** {first_name}\n"
    if last_name:
        text += f"🔹 **Last Name:** {last_name}\n"
    text += f"🔹 **User ID:** `{user_id}`\n"
    text += f"🔹 **Username:** {username}\n"
    text += f"🔹 **Profile Link:** {profile_link}\n"
    text += f"🔹 **Data Center (DC):** `{dc_id}`\n"

    # Bot ki taraf se reply
    await message.reply(text, quote=True, disable_web_page_preview=True)

# ==================================================================
# 3️⃣ Message Receiver (Jab /id mode ON ho tab message catch karega)
# ==================================================================
# Yahan dhyan dein: Humne ["id", "info"] dono commands ko yahan aane se block kar diya hai
@Client.on_message(filters.private & ~filters.command(["id", "info"]))
async def process_message_for_id(client, message: Message):
    user_id = message.from_user.id
    
    # Check karna ki kya user ka ID Mode ON hai?
    if user_id in ID_STATES and ID_STATES[user_id]:
        
        # ID Extract function ko call karna
        await extract_and_send_id(message, message)
        
        # Ek baar ID mil gayi, toh mode ko wapas OFF kar dena
        del ID_STATES[user_id]

# ==================================================================
# 4️⃣ Main ID Extraction Logic (Backend Function)
# ==================================================================
async def extract_and_send_id(target_msg: Message, reply_msg: Message):
    text = f"🆔 **ID EXTRACTION**\n\n"
    text += f"🔹 **Your User ID:** `{reply_msg.from_user.id}`\n"
    
    # Agar message kisi Channel/Group se forward hoke aaya tha
    if target_msg.forward_from_chat:
        fwd_chat_id = target_msg.forward_from_chat.id
        fwd_chat_title = target_msg.forward_from_chat.title
        chat_type = str(target_msg.forward_from_chat.type).split(".")[-1]
        
        text += f"\n📢 **Forwarded Chat Details:**\n"
        text += f"🔹 **Chat ID:** `{fwd_chat_id}`\n"
        text += f"📝 **Chat Title:** {fwd_chat_title}\n"
        text += f"🏢 **Chat Type:** {chat_type}\n"
        
    # Agar message kisi normal User ka forwarded tha
    elif target_msg.forward_from:
        fwd_user_id = target_msg.forward_from.id
        first_name = target_msg.forward_from.first_name
        
        text += f"\n👤 **Forwarded User Details:**\n"
        text += f"🔹 **User ID:** `{fwd_user_id}`\n"
        text += f"📝 **Name:** {first_name}\n"
        
    # Agar User ne privacy lagayi hui hai
    elif target_msg.forward_sender_name:
        text += f"\n⚠️ **Privacy Enabled!**\n"
        text += f"Original User (**{target_msg.forward_sender_name}**) ne apni Forward Privacy ON rakhi hai, isliye ID hide ho chuki hai.\n"
        
    # Agar message forward kiya hi nahi gaya hai (Normal message)
    else:
        text += f"\nℹ️ **Note:** Ye message forward nahi kiya gaya hai, isliye iske paas kisi aur chat ki ID nahi hai.\n"

    await reply_msg.reply(text, quote=True)
