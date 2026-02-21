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
    # 1. Check if replying to a message
    if not message.reply_to_message:
        return await message.reply("⚠️ **Error:** Jis message ko broadcast karna hai, uspar reply karke `/broadcast` likhein.")

    msg_to_broadcast = message.reply_to_message

    # 2. Progress Message
    status_msg = await message.reply("🔄 **Database se users fetch kar raha hoon...**")

    # ==================================================================
    # ✅ REAL DATABASE FETCH LOGIC
    # ==================================================================
    all_users = []
    try:
        # MongoDB ki 'users' collection se saari IDs nikalna
        async for user in db.users.find({"id": {"$exists": True}}):
            all_users.append(user['id'])
    except Exception as e:
        return await status_msg.edit_text(f"❌ Database Error: {e}")
        
    total_users = len(all_users)
    # ==================================================================

    if total_users == 0:
        return await status_msg.edit_text("❌ Database mein koi user nahi mila.")

    # 3. Update Status
    await status_msg.edit_text(
        f"⏳ **Broadcast Started!**\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"✅ Sent: `0`\n"
        f"❌ Failed: `0`"
    )

    sent = 0
    failed = 0
    start_time = time.time()

    # 4. Broadcast Loop
    for user_id in all_users:
        while True:
            try:
                # ✅ .copy() ka use (Bina 'Forwarded' tag ke message jayega)
                await msg_to_broadcast.copy(chat_id=int(user_id))
                sent += 1
                break  # Success! Next user par jao
                
            except FloodWait as e:
                # 🛑 Agar Telegram limit lagaye, to bot automatically wait karega
                await asyncio.sleep(e.value + 1)
                
            except Exception as e:
                # ❌ User ne bot block kar diya, delete ho gaya, etc.
                failed += 1
                break  # Failed! Next user par jao
                
        # 5. Har 20 messages ke baad progress update (Taki limit na lage)
        if (sent + failed) % 20 == 0:
            try:
                await status_msg.edit_text(
                    f"🔄 **Broadcasting...**\n\n"
                    f"👥 Total Users: `{total_users}`\n"
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

        # Message bhejne ke beech thoda delay (Telegram limits se bachne ke liye)
        await asyncio.sleep(0.05)

    # 6. Final Status Update
    time_taken = round(time.time() - start_time, 2)
    
    try:
        await status_msg.edit_text(
            f"✅ **Broadcast Completed Successfully!**\n\n"
            f"⏱ Time Taken: `{time_taken} seconds`\n"
            f"👥 Total Users: `{total_users}`\n"
            f"✅ Successfully Sent: `{sent}`\n"
            f"❌ Failed/Blocked: `{failed}`"
        )
    except Exception:
        await message.reply(f"✅ **Broadcast Completed!**\nSent: {sent} | Failed: {failed}")
