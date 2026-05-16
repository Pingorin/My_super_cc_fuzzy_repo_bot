import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

# ✅ info.py se TARGET_CHANNEL_ID import kar rahe hain
from info import TARGET_CHANNEL_ID

logger = logging.getLogger(__name__)

UPLOAD_STATES = {}
USER_LOCKS = {}

# 🗑️ Background Task: File aur Message ko 120 seconds (2 mins) baad delete karne ke liye
async def delete_after_delay(message: Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

# ⏱️ Auto-Close Timer: 5 second inactivity par session band karega
async def auto_close_upload(client, message: Message, user_id: int):
    await asyncio.sleep(5) 
    
    # Agar 5 second baad bhi session active hai, toh close kar do
    if user_id in UPLOAD_STATES:
        sent_count = UPLOAD_STATES[user_id]["forwarded"]
        status_msg = UPLOAD_STATES[user_id]["status_msg"]
        
        # 🔄 Edit Message: Start -> Complete
        if status_msg:
            try:
                await status_msg.edit_text("✅ **complete forward**")
            except Exception:
                pass
        
        del UPLOAD_STATES[user_id]
        
        if sent_count > 0:
            summary_msg = await message.reply(
                f"✅ **Upload Auto-Completed!**\n\n"
                f"Total `{sent_count}` videos successfully channel me bhej di gayi hain.\n"
                f"(Ye videos aur messages 2 minute baad chat se delete ho jayenge)."
            )
            # ✅ Summary Message par bhi 2 min ka delete timer laga diya
            asyncio.create_task(delete_after_delay(summary_msg, 120))

@Client.on_message(filters.command("admin_upload") & filters.private)
async def admin_upload_command(client, message: Message):
    user_id = message.from_user.id
    
    if not TARGET_CHANNEL_ID or TARGET_CHANNEL_ID == -100:
        return await message.reply("❌ **Error:** Kripya pehle `info.py` me `TARGET_CHANNEL_ID` set karein!")
    
    # Purana timer band karo (agar koi chal raha ho)
    if user_id in UPLOAD_STATES and UPLOAD_STATES[user_id].get("timer"):
        UPLOAD_STATES[user_id]["timer"].cancel()
        
    UPLOAD_STATES[user_id] = {
        "received": 0, 
        "forwarded": 0, 
        "status_msg": None,
        "start_msg_sent": False,
        "timer": None
    }
    
    if user_id not in USER_LOCKS:
        USER_LOCKS[user_id] = asyncio.Lock()
    
    start_msg = await message.reply(
        "📤 **Upload Mode Activated!**\n\n"
        "🎥 **Sirf Videos** bhej sakte hain (Photo, Sticker, Text ignore honge).\n"
        "⚠️ **Limit:** Ek baar me maximum 20 Videos.\n"
        "*(5 second wait karne par bot apne aap session close kar dega)*"
    )
    # ✅ Upload Mode Activated wale Message par bhi 2 min ka delete timer laga diya
    asyncio.create_task(delete_after_delay(start_msg, 120))

@Client.on_message(filters.private & ~filters.command(["admin_upload"]), group=1)
async def receive_and_forward_files(client, message: Message):
    user_id = message.from_user.id
    
    # Agar session active hai
    if user_id in UPLOAD_STATES:
        
        # 🚫 Sirf Video/Document allow karega, baaki turant delete
        if not (message.video or message.document):
            asyncio.create_task(message.delete()) 
            return
            
        # 🚫 20 ki limit cross hote hi extra files turant delete
        if UPLOAD_STATES[user_id]["received"] >= 20:
            asyncio.create_task(message.delete()) 
            return  
            
        UPLOAD_STATES[user_id]["received"] += 1
        
        # ⏳ "Start forward" message (Sirf ek baar)
        if not UPLOAD_STATES[user_id]["start_msg_sent"]:
            UPLOAD_STATES[user_id]["start_msg_sent"] = True 
            try:
                status_message = await message.reply("⏳ **Start forward...**")
                UPLOAD_STATES[user_id]["status_msg"] = status_message
                # ✅ "Start forward" / "Complete forward" wale Message par bhi 2 min ka delete timer laga diya
                asyncio.create_task(delete_after_delay(status_message, 120))
            except Exception:
                pass
        
        if user_id not in USER_LOCKS:
            USER_LOCKS[user_id] = asyncio.Lock()
            
        # 🚀 Forward Queue (Smooth process ke liye)
        async with USER_LOCKS[user_id]:
            while True:
                try:
                    await message.copy(chat_id=TARGET_CHANNEL_ID)
                    UPLOAD_STATES[user_id]["forwarded"] += 1
                    
                    # 🗑️ Forward hone ke baad us video ko 2 min me delete hone ke list me daal do
                    asyncio.create_task(delete_after_delay(message, 120))
                    
                    # ✅ Jab limit (20 files) poori ho jaye
                    if UPLOAD_STATES[user_id]["forwarded"] == 20:
                        if UPLOAD_STATES[user_id]["timer"]:
                            UPLOAD_STATES[user_id]["timer"].cancel()
                            
                        if UPLOAD_STATES[user_id]["status_msg"]:
                            try:
                                await UPLOAD_STATES[user_id]["status_msg"].edit_text("✅ **complete forward**")
                            except Exception:
                                pass
                                
                        limit_msg = await message.reply(
                            "⚠️ **20 Files Ki Limit Poori Hui!**\n\n"
                            "Sirf 20 files hi forward ki gayi hain. Baki extra files delete kar di gayi hain.\n"
                            "📅 **Kripya baki ki files Next Day upload karein.**\n\n"
                            "✅ **Upload Complete!** (Ye sabhi messages 2 min baad hat jayenge)."
                        )
                        # ✅ Limit Poori hui wale Message par bhi 2 min ka delete timer laga diya
                        asyncio.create_task(delete_after_delay(limit_msg, 120))
                        del UPLOAD_STATES[user_id]
                        return 
                    
                    # Delay (FloodWait se bachne ke liye)
                    await asyncio.sleep(1.5)
                    break
                    
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                except Exception:
                    break

        # ⏱️ Har valid file ke baad naya 5 sec ka timer start
        if user_id in UPLOAD_STATES:
            if UPLOAD_STATES[user_id]["timer"]:
                UPLOAD_STATES[user_id]["timer"].cancel()
            UPLOAD_STATES[user_id]["timer"] = asyncio.create_task(auto_close_upload(client, message, user_id))
