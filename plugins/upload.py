import logging
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)

# ==================================================================
# ⚙️ SETTINGS: Yahan apne Channel ka ID daalein
# (Channel ID hamesha -100 se shuru hota hai)
# Example: TARGET_CHANNEL_ID = -1001234567890
# ==================================================================
TARGET_CHANNEL_ID = -1003719921511


# Ye dictionary users ke session aur unki file count yaad rakhegi
UPLOAD_STATES = {}

@Client.on_message(filters.command("admin_upload") & filters.private)
async def admin_upload_command(client, message: Message):
    user_id = message.from_user.id
    
    # User ka naya session start karo (Count = 0)
    UPLOAD_STATES[user_id] = 0
    
    await message.reply(
        "📤 **Upload Mode Activated!**\n\n"
        "Ab aap mujhe yahan files (Photo, Video, Document, etc.) bhej sakte hain.\n"
        "Main unhe automatically Target Channel me forward kar dunga.\n\n"
        "⚠️ **Limit:** Ek baar me maximum 20 files.\n"
        "🛑 Jab saari files bhej dein, toh `/done` type karein."
    )

@Client.on_message(filters.media & filters.private)
async def receive_and_forward_files(client, message: Message):
    user_id = message.from_user.id
    
    # Check karna ki kya user upload mode me hai
    if user_id in UPLOAD_STATES:
        current_count = UPLOAD_STATES[user_id]
        
        # 20 File ki limit check karna
        if current_count < 20:
            try:
                # File channel me copy karna (Bina forwarded tag ke)
                await message.copy(chat_id=TARGET_CHANNEL_ID)
                
                # Count badhana
                UPLOAD_STATES[user_id] += 1
                
                # Agar user ne ek sath media group (album) bheja hai toh bar-bar reply na jaye, 
                # Isliye hum har file par reply nahi kar rahe, bas background me channel me bhej rahe hain.
                
            except Exception as e:
                await message.reply(f"❌ File bhejne me error aaya: {e}")
        else:
            # 20 ki limit cross hone par session close kar dena
            await message.reply("⚠️ **Limit Reached!**\nAapne 20 files bhej di hain. Session close kiya jaa raha hai.")
            del UPLOAD_STATES[user_id]

@Client.on_message(filters.command("done") & filters.private)
async def done_upload(client, message: Message):
    user_id = message.from_user.id
    
    # Agar user upload mode me tha aur usne /done bheja
    if user_id in UPLOAD_STATES:
        sent_count = UPLOAD_STATES[user_id]
        
        # Session khatam karna
        del UPLOAD_STATES[user_id]
        
        await message.reply(f"✅ **Upload Complete!**\n\nTotal `{sent_count}` files successfully channel me bhej di gayi hain.")
    else:
        await message.reply("❌ Aapka koi upload session active nahi hai. Start karne ke liye `/admin_upload` bhejein.")
