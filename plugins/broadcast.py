import logging
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified
from info import ADMINS

# ✅ Aapka Database Import
from database.users_chats_db import db

logger = logging.getLogger(__name__)

# 🛑 Yahan se `& filters.user(ADMINS)` hata diya taaki bot kam se kam reply zaroor kare
@Client.on_message(filters.command("broadcast"))
async def broadcast_handler(client, message):
    
    # ==================================================================
    # 🔒 ADMIN CHECK LOGIC (FIXED)
    # ==================================================================
    user_id = message.from_user.id
    
    # ADMINS list ko force karke Integer (Number) mein convert kar rahe hain
    # (Taki string vs int ka issue hamesha ke liye khatam ho jaye)
    try:
        admin_list = [int(admin) for admin in ADMINS if str(admin).isdigit()]
    except Exception:
        admin_list = []
        
    if user_id not in admin_list:
        return await message.reply(
            f"🚫 **Access Denied!**\n\n"
            f"Aapki User ID: `{user_id}`\n"
            f"Bot ke paas save ADMINS: `{ADMINS}`\n\n"
            f"*(Aapki ID aur Bot ki list match nahi kar rahi hai)*"
        )
    # ==================================================================

    if not message.reply_to_message:
        return await message.reply("⚠️ **Error:** Jis message ko bhejna hai, uspar reply karke `/broadcast` ya `/broadcast <user_id>` likhein.")

    msg_to_broadcast = message.reply_to_message
    
    all_users = []
    
    # ==================================================================
    # 🎯 TARGET SELECTION LOGIC
    # ==================================================================
    if len(message.command) > 1:
        for u_id in message.command[1:]:
            try:
                all_users.append(int(u_id))
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
    last_error = ""

    # Broadcast Loop
    for target_user_id in all_users:
        while True:
            try:
                await msg_to_broadcast.copy(chat_id=int(target_user_id))
                sent += 1
                break
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                failed += 1
                last_error = str(e)
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
