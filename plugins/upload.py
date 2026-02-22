import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)

# ==================================================================
# ⚙️ SETTINGS: Yahan apne Channel ka ID daalein
# ==================================================================
TARGET_CHANNEL_ID = -1001234567890 

UPLOAD_STATES = {}

@Client.on_message(filters.command("admin_upload") & filters.private)
async def admin_upload_command(client, message: Message):
    user_id = message.from_user.id
    
    # User ka naya session start karo (Count = 0)
    UPLOAD_STATES[user_id] = 0
    
    await message.reply(
        "📤 **Upload Mode Activated!**\n\n"
        "Ab aap mujhe yahan files bhej sakte hain.\n"
        "Main unhe automatically Target Channel me bhej dunga.\n\n"
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
            
            # ✅ ERROR HANDLING & RETRY LOOP
            while True:
                try:
                    # File channel me copy karna
                    await message.copy(chat_id=TARGET_CHANNEL_ID)
                    UPLOAD_STATES[user_id] += 1
                    break  # Success ho gaya, loop se bahar niklo
                    
                except FloodWait as e:
                    # Telegram ne roka hai, wait karega
                    wait_time = e.value
                    warning_msg = await message.reply(f"⏳ **Telegram Limit!** Bot {wait_time} seconds ke liye ruk raha hai. Kripya wait karein...")
                    await asyncio.sleep(wait_time + 1)
                    try:
                        await warning_msg.delete() # Wait khatam hone ke baad warning message hata dega
                    except:
                        pass
                    # Loop wapas shuru hoga aur file ko phir try karega
                    
                except Exception as e:
                    await message.reply(f"❌ File bhejne me error aaya: `{e}`")
                    break
        else:
            # 20 ki limit cross hone par session close karna
            await message.reply("⚠️ **Limit Reached!**\nAapne 20 files bhej di hain. Session close kiya jaa raha hai.")
            if user_id in UPLOAD_STATES:
                del UPLOAD_STATES[user_id]

@Client.on_message(filters.command("done") & filters.private)
async def done_upload(client, message: Message):
    user_id = message.from_user.id
    
    if user_id in UPLOAD_STATES:
        sent_count = UPLOAD_STATES[user_id]
        
        # Session khatam karna
        del UPLOAD_STATES[user_id]
        
        await message.reply(f"✅ **Upload Complete!**\n\nTotal `{sent_count}` files successfully channel me bhej di gayi hain.")
    else:
        await message.reply("❌ Aapka koi upload session active nahi hai. Start karne ke liye `/admin_upload` bhejein.")
