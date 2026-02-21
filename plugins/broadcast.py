import logging
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified
from info import ADMINS

# ✅ Aapka Database Import
from database.users_chats_db import db

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_handler(client, message):
    if not message.reply_to_message:
        return await message.reply("⚠️ **Error:** Jis message ko bhejna hai, uspar reply karke `/broadcast` likhein.")

    msg_to_broadcast = message.reply_to_message
    
    all_users = []
    
    # ==================================================================
    # 🎯 TARGET SELECTION LOGIC
    # ==================================================================
    
    # 1. Agar specific IDs di gayi hain (e.g., /broadcast 1234567 8901234)
    if len(message.command) > 1:
        for user_id in message.command[1:]:
            try:
                all_users.append(int(user_id))
            except ValueError:
                continue # Agar galti se text type ho gaya ho toh ignore karega
                
        if not all_users:
            return await message.reply("❌ Koi valid User ID nahi mili. Kripya sahi ID space dekar daalein.")
            
        status_msg = await message.reply(f"🔄 **{len(all_users)} Specific Users ko message bhej raha hoon...**")
        
    # 2. Agar koi ID nahi di, toh Database se ALL USERS nikalega
    else:
        status_msg = await message.reply("🔄 **Database se sabhi users fetch kar raha hoon...**")
        try:
            async for user in db.users.find({"id": {"$exists": True}}):
                all_users.append(user['id'])
        except Exception as e:
            return await status_msg.edit_text(f"❌ Database Error: {e}")

    # ==================================================================
    
    total_users = len(all_users)
    if total_users == 0:
        return await status_msg.edit_text("❌ Koi user nahi mila.")

    await status_msg.edit_text(
        f"⏳ **Broadcast Started!**\n\n"
        f"👥 Target Users: `{total_users}`\n"
        f"✅ Sent: `0`\n"
        f"❌ Failed: `0`"
    )

    sent = 0
    failed = 0
    start_time = time.time()

    # Broadcast Loop
    for user_id in all_users:
        while True:
            try:
                # .copy() se clean message jayega
                await msg_to_broadcast.copy(chat_id=int(user_id))
                sent += 1
                break
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except Exception:
                failed += 1
                break
                
        # Har 20 messages par UI update
        if (sent + failed) % 20 == 0:
            try:
                await status_msg.edit_text(
                    f"🔄 **Broadcasting...**\n\n"
                    f"👥 Target Users: `{total_users}`\n"
                    f"✅ Sent: `{sent}`\n"
                    f"❌ Failed: `{failed}`\n"
                    f"📈 Progress: `{round((sent + failed) / total_users * 100, 2)}%`"
                )
            except MessageNotModified:
                pass
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception:
                pass

        await asyncio.sleep(0.05)

    time_taken = round(time.time() - start_time, 2)
    
    try:
        await status_msg.edit_text(
            f"✅ **Broadcast Completed!**\n\n"
            f"⏱ Time Taken: `{time_taken} seconds`\n"
            f"👥 Target Users: `{total_users}`\n"
            f"✅ Successfully Sent: `{sent}`\n"
            f"❌ Failed/Blocked: `{failed}`"
        )
    except Exception:
        await message.reply(f"✅ **Broadcast Completed!**\nSent: {sent} | Failed: {failed}")
