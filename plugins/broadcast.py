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
        return await message.reply("⚠️ **Error:** Jis message ko bhejna hai, uspar reply karke `/broadcast` ya `/broadcast <user_id>` likhein.")

    msg_to_broadcast = message.reply_to_message
    
    all_users = []
    
    # ==================================================================
    # 🎯 TARGET SELECTION LOGIC
    # ==================================================================
    if len(message.command) > 1:
        for user_id in message.command[1:]:
            try:
                all_users.append(int(user_id))
            except ValueError:
                continue
                
        if not all_users:
            return await message.reply("❌ Koi valid User ID nahi mili.")
            
        status_msg = await message.reply(f"🔄 **{len(all_users)} Specific Users ko message bhej raha hoon...**")
        
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
    last_error = "" # Error save karne ke liye variable

    # Broadcast Loop
    for user_id in all_users:
        while True:
            try:
                # Photo, Video, ya Text copy karke bhejna
                await msg_to_broadcast.copy(chat_id=int(user_id))
                sent += 1
                break
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                failed += 1
                last_error = str(e) # Exact error capture karna
                logger.error(f"Broadcast Failed for {user_id}: {last_error}")
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
    
    # Agar sirf 1 user ko bheja tha aur wo Fail ho gaya, toh specific Error dikhayega
    if total_users == 1 and failed == 1:
        try:
            await status_msg.edit_text(
                f"❌ **Message Nahi Gaya!**\n\n"
                f"**Reason:** `{last_error}`\n\n"
                f"*(Note: Ya toh ye ID galat hai, ya iss user ne aapke bot ko Start/Unblock nahi kiya hai)*"
            )
        except Exception:
            pass
    else:
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
