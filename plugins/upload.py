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

# 🗑️ Background Task: File ko 2 minute baad delete karne ke liye
async def delete_after_delay(message: Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

# ⏱️ Auto-Close Timer: 30 second inactivity par session band karega
async def auto_close_upload(client, message: Message, user_id: int):
    await asyncio.sleep(30) # Ab 30 seconds wait karega
    
    # Agar 30 second baad bhi session active hai, toh use automatically close kar do
    if user_id in UPLOAD_STATES:
        sent_count = UPLOAD_STATES[user_id]["forwarded"]
        status_msg = UPLOAD_STATES[user_id]["status_msg"]
        
        # 🔄 Edit Message: Start -> Complete
        if status_msg:
            try:
                await status_msg.edit_text("✅ **complete forward**")
            except Exception:
                pass
        
        # Session khatam karo
        del UPLOAD_STATES[user_id]
        
        if sent_count > 0:
            await message.reply(
                f"✅ **Upload Auto-Completed!**\n\n"
                f"Total `{sent_count}` videos successfully channel me bhej di gayi hain.\n"
                f"(Ye videos 2 minute baad aapki chat se delete ho jayengi)."
            )

@Client.on_message(filters.command("admin_upload") & filters.private)
async def admin_upload_command(client, message: Message):
    user_id = message.from_user.id
    
    if not TARGET_CHANNEL_ID or TARGET_CHANNEL_ID == -100:
        return await message.reply("❌ **Error:** Kripya pehle `info.py` me `TARGET_CHANNEL_ID` set karein!")
    
    # Agar pehle se koi timer chal raha ho toh use band kar do
    if user_id in UPLOAD_STATES and "timer" in UPLOAD_STATES[user_id] and UPLOAD_STATES[user_id]["timer"]:
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
    
    await message.reply(
        "📤 **Upload Mode Activated!**\n\n"
        "🎥 **Sirf Videos** bhej sakte hain (Photo, Sticker, Text aate hi delete ho jayenge).\n"
        "Main unhe automatically Target Channel me bhej dunga.\n\n"
        "⚠️ **Limit:** Ek baar me maximum 20 Videos.\n"
        "*(Aapko koi command dene ki zaroorat nahi hai, 30 second wait karne par bot apne aap session close kar dega)*"
    )

@Client.on_message(filters.private & ~filters.command(["admin_upload"]))
async def receive_and_forward_files(client, message: Message):
    user_id = message.from_user.id
    
    # Agar session chal raha hai
    if user_id in UPLOAD_STATES:
        
        # ✅ STEP 1: Sirf Video Filter (Ab Album me bhi strong delete karega)
        if not (message.video or message.document):
            try:
                await message.delete()
            except Exception:
                pass
            return
            
        # ✅ STEP 2: Limit check (20 se zyada aate hi turant delete)
        if UPLOAD_STATES[user_id]["received"] >= 20:
            try:
                await message.delete()
            except Exception:
                pass
            return  
            
        UPLOAD_STATES[user_id]["received"] += 1
        
        # ✅ STEP 3: "Start forward" msg
        if not UPLOAD_STATES[user_id]["start_msg_sent"]:
            UPLOAD_STATES[user_id]["start_msg_sent"] = True 
            try:
                status_message = await message.reply("⏳ **Start forward...**")
                UPLOAD_STATES[user_id]["status_msg"] = status_message
            except Exception:
                pass
        
        if user_id not in USER_LOCKS:
            USER_LOCKS[user_id] = asyncio.Lock()
            
        # ✅ STEP 4: Forward Queue
        async with USER_LOCKS[user_id]:
            while True:
                try:
                    await message.copy(chat_id=TARGET_CHANNEL_ID)
                    UPLOAD_STATES[user_id]["forwarded"] += 1
                    
                    asyncio.create_task(delete_after_delay(message, 120))
                    
                    # Agar 20 files poori ho jayein toh turant close kar do
                    if UPLOAD_STATES[user_id]["forwarded"] == 20:
                        
                        # Timer band karo
                        if UPLOAD_STATES[user_id]["timer"]:
                            UPLOAD_STATES[user_id]["timer"].cancel()
                            
                        # 🔄 Edit Message: Start -> Complete
                        try:
                            if UPLOAD_STATES[user_id]["status_msg"]:
                                await UPLOAD_STATES[user_id]["status_msg"].edit_text("✅ **complete forward**")
                        except Exception:
                            pass
                            
                        await message.reply(
                            "⚠️ **20 Files Ki Limit Poori Hui!**\n\n"
                            "Sirf 20 files hi forward ki gayi hain. Baki extra files delete kar di gayi hain.\n"
                            "📅 **Kripya baki ki files Next Day (Agle Din) upload karein.**\n\n"
                            "✅ **Upload Complete!** (Ye videos 2 minute baad chat se hat jayengi)."
                        )
                        del UPLOAD_STATES[user_id]
                        return # Session turant yahan close ho gaya
                    
                    await asyncio.sleep(1.5)
                    break
                    
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                except Exception as e:
                    await message.reply(f"❌ Error: `{e}`")
                    break

        # ✅ STEP 5: Har file forward hone ke baad 30 second ka naya timer start karo
        if user_id in UPLOAD_STATES:
            if UPLOAD_STATES[user_id]["timer"]:
                UPLOAD_STATES[user_id]["timer"].cancel() # Purana timer cancel
            # Naya 30 second ka timer lagao
            UPLOAD_STATES[user_id]["timer"] = asyncio.create_task(auto_close_upload(client, message, user_id))
            
    # Agar user bina /admin_upload ke direct media bhej de
    else:
        if message.media:
            await message.reply("❌ **Upload session active nahi hai!**\nPehle `/admin_upload` bhejein, fir videos upload karein.")
