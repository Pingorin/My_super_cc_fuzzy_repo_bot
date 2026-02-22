import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)

# ==================================================================
# ⚙️ SETTINGS: Yahan apne asli Channel ka ID daalein!
# (Channel ID hamesha -100 se shuru hota hai)
# ==================================================================
TARGET_CHANNEL_ID = -1003719921511  # <--- ISKO CHANGE KARNA MAT BHOOLNA

UPLOAD_STATES = {}

@Client.on_message(filters.command("admin_upload") & filters.private)
async def admin_upload_command(client, message: Message):
    user_id = message.from_user.id
    
    # User ka naya session start karo: count = 0, aur warned = False
    UPLOAD_STATES[user_id] = {"count": 0, "warned": False}
    
    await message.reply(
        "📤 **Upload Mode Activated!**\n\n"
        "Ab aap mujhe yahan files bhej sakte hain.\n"
        "Main unhe automatically Target Channel me bhej dunga.\n\n"
        "⚠️ **Limit:** Ek baar me maximum 20 files.\n"
        "🛑 Jab complete ho jaye, toh `/done` type karein."
    )

@Client.on_message(filters.media & filters.private)
async def receive_and_forward_files(client, message: Message):
    user_id = message.from_user.id
    
    if user_id in UPLOAD_STATES:
        current_count = UPLOAD_STATES[user_id]["count"]
        has_warned = UPLOAD_STATES[user_id]["warned"]
        
        # Agar 20 se kam files hain, toh forward karo
        if current_count < 20:
            while True:
                try:
                    # File channel me copy karna
                    await message.copy(chat_id=TARGET_CHANNEL_ID)
                    UPLOAD_STATES[user_id]["count"] += 1
                    
                    # Agar limit (20) exactly abhi poori hui hai
                    if UPLOAD_STATES[user_id]["count"] == 20:
                        UPLOAD_STATES[user_id]["warned"] = True
                        await message.reply(
                            "⚠️ **Limit Poori Hui!**\n\n"
                            "Sirf 20 file hi forward ki jayegi baki file ko forward nahi kiya gaya hai.\n"
                            "Naya session start karne ke liye pehle `/done` bhejein aur wapas `/admin_upload` karein."
                        )
                    break
                    
                except FloodWait as e:
                    wait_time = e.value
                    warning_msg = await message.reply(f"⏳ **Telegram Limit!** Bot {wait_time} seconds ke liye ruk raha hai...")
                    await asyncio.sleep(wait_time + 1)
                    try:
                        await warning_msg.delete()
                    except:
                        pass
                except Exception as e:
                    await message.reply(f"❌ File bhejne me error aaya: `{e}`\n(Check karo ki TARGET_CHANNEL_ID sahi hai ya nahi!)")
                    break
                    
        else:
            # Agar limit pehle hi cross ho chuki hai (jaise bachi hui 30 files aayengi), 
            # toh bot spam nahi karega. Chupchap ignore kar dega.
            pass

@Client.on_message(filters.command("done") & filters.private)
async def done_upload(client, message: Message):
    user_id = message.from_user.id
    
    if user_id in UPLOAD_STATES:
        sent_count = UPLOAD_STATES[user_id]["count"]
        
        # Session khatam karna
        del UPLOAD_STATES[user_id]
        
        await message.reply(f"✅ **Upload Complete!**\n\nTotal `{sent_count}` files successfully channel me bhej di gayi hain.")
    else:
        await message.reply("❌ Aapka koi upload session active nahi hai. Start karne ke liye `/admin_upload` bhejein.")
