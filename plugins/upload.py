import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)

# ==================================================================
# ⚙️ SETTINGS: Yahan apne asli Channel ka ID daalein!
# ==================================================================
TARGET_CHANNEL_ID = -1003719921511  # <--- ISKO CHANGE KARNA MAT BHOOLNA

UPLOAD_STATES = {}
USER_LOCKS = {}

# 🗑️ Background Task: Ye function file ko x seconds baad delete karega
async def delete_after_delay(message: Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

@Client.on_message(filters.command("admin_upload") & filters.private)
async def admin_upload_command(client, message: Message):
    user_id = message.from_user.id
    
    # User ka naya session start karo
    UPLOAD_STATES[user_id] = {"count": 0, "warned": False}
    
    if user_id not in USER_LOCKS:
        USER_LOCKS[user_id] = asyncio.Lock()
    
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
        if user_id not in USER_LOCKS:
            USER_LOCKS[user_id] = asyncio.Lock()
            
        async with USER_LOCKS[user_id]:
            current_count = UPLOAD_STATES[user_id]["count"]
            
            # Agar 20 se kam files hain, toh forward karo
            if current_count < 20:
                while True:
                    try:
                        # File channel me copy karna
                        await message.copy(chat_id=TARGET_CHANNEL_ID)
                        UPLOAD_STATES[user_id]["count"] += 1
                        
                        # 🗑️ Forward hone ke baad file ko 2 Minute (120 sec) baad delete hone ke liye schedule karna
                        asyncio.create_task(delete_after_delay(message, 120))
                        
                        # ✅ Limit (20) poori hui
                        if UPLOAD_STATES[user_id]["count"] == 20:
                            UPLOAD_STATES[user_id]["warned"] = True
                            await message.reply(
                                "⚠️ **20 Files Ki Limit Poori Hui!**\n\n"
                                "Sirf 20 files hi forward ki gayi hain. Baki aane wali saari extra files delete kar di jayengi.\n"
                                "(Forward ki gayi 20 files bhi 2 minute baad chat se hat jayengi)\n\n"
                                "📅 **Kripya baki ki files Next Day (Agle Din) upload karein.**"
                            )
                        
                        # Delay taaki flood na aaye
                        await asyncio.sleep(1.5)
                        break
                        
                    except FloodWait as e:
                        await asyncio.sleep(e.value + 1)
                        
                    except Exception as e:
                        await message.reply(f"❌ File bhejne me error aaya: `{e}`")
                        break
            else:
                # 🛑 Limit cross ho chuki hai, extra files ko TURANT DELETE kar do
                try:
                    await message.delete()
                except Exception:
                    pass

@Client.on_message(filters.command("done") & filters.private)
async def done_upload(client, message: Message):
    user_id = message.from_user.id
    
    if user_id in UPLOAD_STATES:
        sent_count = UPLOAD_STATES[user_id]["count"]
        
        # Session khatam karna
        del UPLOAD_STATES[user_id]
        
        await message.reply(f"✅ **Upload Complete!**\n\nTotal `{sent_count}` files successfully channel me bhej di gayi hain.\n(Ye files 2 minute baad aapki chat se delete ho jayengi).")
    else:
        await message.reply("❌ Aapka koi upload session active nahi hai. Start karne ke liye `/admin_upload` bhejein.")
