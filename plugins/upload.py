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

@Client.on_message(filters.command("admin_upload") & filters.private)
async def admin_upload_command(client, message: Message):
    user_id = message.from_user.id
    
    if not TARGET_CHANNEL_ID or TARGET_CHANNEL_ID == -100:
        return await message.reply("❌ **Error:** Kripya pehle `info.py` me `TARGET_CHANNEL_ID` set karein!")
    
    # 'status_msg' ko save karne ke liye variable add kiya
    UPLOAD_STATES[user_id] = {"received": 0, "forwarded": 0, "warned": False, "status_msg": None}
    
    if user_id not in USER_LOCKS:
        USER_LOCKS[user_id] = asyncio.Lock()
    
    await message.reply(
        "📤 **Upload Mode Activated!**\n\n"
        "🎥 **Sirf Videos** bhej sakte hain (Photo, Sticker, Text ignore/delete ho jayenge).\n"
        "Main unhe automatically Target Channel me bhej dunga.\n\n"
        "⚠️ **Limit:** Ek baar me maximum 20 Videos.\n"
        "🛑 Jab complete ho jaye, toh `/done` type karein."
    )

# Yahan hum sab kuch catch kar rahe hain (command chhod kar) taaki non-videos ko delete kar sakein
@Client.on_message(filters.private & ~filters.command(["admin_upload", "done"]))
async def receive_and_forward_files(client, message: Message):
    user_id = message.from_user.id
    
    if user_id in UPLOAD_STATES:
        
        # ✅ STEP 1: Sirf Video Filter (Text, Photo, Sticker turant delete honge)
        if not (message.video or message.document):
            try:
                await message.delete()
            except Exception:
                pass
            return  # Yahan se aage nahi badhega
            
        # ✅ STEP 2: Turant Delete Logic (Extra videos aate hi gayab)
        if UPLOAD_STATES[user_id]["received"] >= 20:
            try:
                await message.delete()
            except Exception:
                pass
            return  
            
        # ✅ STEP 3: "Start forward" message bhejna (Pehli file aate hi)
        if UPLOAD_STATES[user_id]["received"] == 0:
            status_message = await message.reply("⏳ **Start forward...**")
            UPLOAD_STATES[user_id]["status_msg"] = status_message
            
        UPLOAD_STATES[user_id]["received"] += 1
        
        if user_id not in USER_LOCKS:
            USER_LOCKS[user_id] = asyncio.Lock()
            
        # ✅ STEP 4: Forward karne wali Queue
        async with USER_LOCKS[user_id]:
            while True:
                try:
                    # File channel me copy karna
                    await message.copy(chat_id=TARGET_CHANNEL_ID)
                    UPLOAD_STATES[user_id]["forwarded"] += 1
                    
                    # 🗑️ 2 minute (120 seconds) baad delete timer
                    asyncio.create_task(delete_after_delay(message, 120))
                    
                    # Jab 20 files poori ho jayein
                    if UPLOAD_STATES[user_id]["forwarded"] == 20:
                        UPLOAD_STATES[user_id]["warned"] = True
                        
                        # 🔄 Edit Message: Start forward -> Complete forward
                        try:
                            if UPLOAD_STATES[user_id]["status_msg"]:
                                await UPLOAD_STATES[user_id]["status_msg"].edit_text("✅ **complete forward**")
                        except Exception:
                            pass
                            
                        await message.reply(
                            "⚠️ **20 Files Ki Limit Poori Hui!**\n\n"
                            "Sirf 20 files hi forward ki gayi hain. Baki aane wali saari extra files delete kar di gayi hain.\n"
                            "(Forward ki gayi 20 files bhi 2 minute baad chat se hat jayengi)\n\n"
                            "📅 **Kripya baki ki files Next Day (Agle Din) upload karein.**"
                        )
                    
                    # 1.5 seconds wait karna taaki API Flood limit na aaye
                    await asyncio.sleep(1.5)
                    break
                    
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                    
                except Exception as e:
                    await message.reply(f"❌ File bhejne me error aaya: `{e}`")
                    break

@Client.on_message(filters.command("done") & filters.private)
async def done_upload(client, message: Message):
    user_id = message.from_user.id
    
    if user_id in UPLOAD_STATES:
        sent_count = UPLOAD_STATES[user_id]["forwarded"]
        status_msg = UPLOAD_STATES[user_id]["status_msg"]
        
        # 🔄 Agar limit (20) se pehle hi /done kar diya, toh bhi message 'complete' kar do
        if status_msg and sent_count < 20 and sent_count > 0:
            try:
                await status_msg.edit_text("✅ **complete forward**")
            except Exception:
                pass
                
        del UPLOAD_STATES[user_id]
        
        await message.reply(f"✅ **Upload Complete!**\n\nTotal `{sent_count}` videos successfully channel me bhej di gayi hain.\n(Ye videos 2 minute baad aapki chat se delete ho jayengi).")
    else:
        await message.reply("❌ Aapka koi upload session active nahi hai. Start karne ke liye `/admin_upload` bhejein.")
