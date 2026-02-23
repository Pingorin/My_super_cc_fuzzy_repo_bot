import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType  # ✅ Isko add kiya gaya hai chat type check karne ke liye

logger = logging.getLogger(__name__)

ID_STATES = {}

# ==================================================================
# 1️⃣ The `/id` Command Handler (Ab Group aur Private dono me chalega)
# ==================================================================
@Client.on_message(filters.command("id"))  # ✅ filters.private hata diya gaya hai
async def id_command_handler(client, message: Message):
    user_id = message.from_user.id
    
    # CASE 1: Agar kisi message par Reply karke /id bheja hai (Group ho ya PM)
    if message.reply_to_message:
        return await extract_and_send_id(message.reply_to_message, message)
        
    # CASE 2: Agar Group me sirf /id bheja hai (Bina reply ke)
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        text = f"🆔 **Chat Details**\n\n"
        text += f"🔹 **Group ID:** `{message.chat.id}`\n"
        text += f"🔹 **Your User ID:** `{user_id}`\n"
        return await message.reply(text, quote=True)
        
    # CASE 3: Agar Private Chat (PM) me sirf /id bheja hai (Wait Mode ON karna)
    if message.chat.type == ChatType.PRIVATE:
        ID_STATES[user_id] = True
        await message.reply(
            "🆔 **ID Extraction Mode ON**\n\n"
            "Ab aap kisi bhi channel, group ya user ka post yahan **forward** karein, main uski ID nikal kar dunga.\n\n"
            "*(Ek baar ID batane ke baad ye mode apne aap band ho jayega)*"
        )

# ==================================================================
# 2️⃣ The `/info` Command Handler 
# ==================================================================
@Client.on_message(filters.command("info"))
async def user_info_command(client, message: Message):
    
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        heading = "👤 **Replied User Info**"
    else:
        target_user = message.from_user
        heading = "👤 **Your Information**"

    user_id = target_user.id
    first_name = target_user.first_name or "N/A"
    last_name = target_user.last_name or ""
    username = f"@{target_user.username}" if target_user.username else "N/A"
    dc_id = target_user.dc_id or "Unknown"

    profile_link = f"<a href='tg://user?id={user_id}'>Click Here</a>"

    text = f"{heading}\n\n"
    text += f"🔹 **First Name:** {first_name}\n"
    if last_name:
        text += f"🔹 **Last Name:** {last_name}\n"
    text += f"🔹 **User ID:** `{user_id}`\n"
    text += f"🔹 **Username:** {username}\n"
    text += f"🔹 **Profile Link:** {profile_link}\n"
    text += f"🔹 **Data Center (DC):** `{dc_id}`\n"

    await message.reply(text, quote=True, disable_web_page_preview=True)

# ==================================================================
# 3️⃣ Message Receiver (Sirf Private Chat ke liye)
# ==================================================================
@Client.on_message(filters.private & ~filters.command(["id", "info"]), group=2)
async def process_message_for_id(client, message: Message):
    user_id = message.from_user.id
    
    if user_id in ID_STATES and ID_STATES[user_id]:
        await extract_and_send_id(message, message)
        del ID_STATES[user_id]

# ==================================================================
# 4️⃣ Main ID Extraction Logic
# ==================================================================
async def extract_and_send_id(target_msg: Message, reply_msg: Message):
    text = f"🆔 **ID EXTRACTION**\n\n"
    text += f"🔹 **Your User ID:** `{reply_msg.from_user.id}`\n"
    
    if target_msg.forward_from_chat:
        fwd_chat_id = target_msg.forward_from_chat.id
        fwd_chat_title = target_msg.forward_from_chat.title
        chat_type = str(target_msg.forward_from_chat.type).split(".")[-1]
        
        text += f"\n📢 **Forwarded Chat Details:**\n"
        text += f"🔹 **Chat ID:** `{fwd_chat_id}`\n"
        text += f"📝 **Chat Title:** {fwd_chat_title}\n"
        text += f"🏢 **Chat Type:** {chat_type}\n"
        
    elif target_msg.forward_from:
        fwd_user_id = target_msg.forward_from.id
        first_name = target_msg.forward_from.first_name
        
        text += f"\n👤 **Forwarded User Details:**\n"
        text += f"🔹 **User ID:** `{fwd_user_id}`\n"
        text += f"📝 **Name:** {first_name}\n"
        
    elif target_msg.forward_sender_name:
        text += f"\n⚠️ **Privacy Enabled!**\n"
        text += f"Original User (**{target_msg.forward_sender_name}**) ne apni Forward Privacy ON rakhi hai, isliye ID hide ho chuki hai.\n"
        
    else:
        text += f"\nℹ️ **Note:** Ye message forward nahi kiya gaya hai, isliye iske paas kisi aur chat ki ID nahi hai.\n"

    await reply_msg.reply(text, quote=True)
