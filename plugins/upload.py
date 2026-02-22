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

@Client.on_message(filters.command("admin_upload") & filters.private)
async def admin_upload_command(client, message: Message):
    user_id = message.from_user.id
    
    # User ka naya session start karo
    UPLOAD_STATES[user_id] = {"count": 0, "warned": False}
    
    # User ke liye ek lock banao taaki files line me lagein
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
        # Lock check karo
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
                        
                        # ✅ Limit (20) exactly abhi poori hui hai
                        if UPLOAD_STATES[user_id]["count"] == 20:
                            UPLOAD_STATES[user_id]["warned"] = True
                            await message.reply(
                                "⚠️ **20 Files Ki Limit Poori Hui!**\n\n"
                                "Sirf 20 files hi forward ki gayi hain. Baki ki extra files ko ignore kar diya gaya hai.\n\n"
                                "📅 **Kripya baki ki files Next Day (Agle Din) upload karein.**"
                            )
                        
                        # Har file bhejne ke baad 1.5 second ka aaram (Delay)
                        await asyncio.sleep(1.5)
                        break
                        
                    except FloodWait as e:
                        # Agar fir bhi limit aati hai, toh bot CHUPCHAP wait karega
                        await asyncio.sleep(e.value + 1)
                        
                    except Exception as e:
                        await message.reply(f"❌ File bhejne me error aaya: `{e}`")
                        break
            else:
                # 🛑 Limit cross ho chuki hai, extra files ko silent ignore karo
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
