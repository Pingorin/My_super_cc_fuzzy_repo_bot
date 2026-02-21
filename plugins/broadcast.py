import logging
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified
from info import ADMINS
# ✅ Import your database here
# from database.users_chats_db import db

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_handler(client, message):
    # 1. Check if the admin is replying to a message
    if not message.reply_to_message:
        return await message.reply("⚠️ **Error:** You must reply to a message to broadcast it.")

    msg_to_broadcast = message.reply_to_message

    # ==================================================================
    # 🔗 DATABASE INTEGRATION PLACEHOLDER
    # ==================================================================
    # Replace this dummy list with your MongoDB fetch logic.
    # Example using your motor setup: 
    # all_users = []
    # async for user in db.users.find({}):
    #     all_users.append(user['id'])
    
    all_users = [123456789, 987654321]  # <--- REPLACE THIS WITH YOUR DB FETCH
    total_users = len(all_users)
    # ==================================================================

    if total_users == 0:
        return await message.reply("❌ No users found in the database.")

    # 2. Send Initial Progress Message
    status_msg = await message.reply(
        f"⏳ **Broadcast Started!**\n\n"
        f"👥 Total Users: `{total_users}`\n"
        f"✅ Sent: `0`\n"
        f"❌ Failed: `0`"
    )

    sent = 0
    failed = 0
    start_time = time.time()

    # 3. Broadcast Loop
    for user_id in all_users:
        while True:
            try:
                # ✅ .copy() sends media/text cleanly without "Forwarded" tag
                await msg_to_broadcast.copy(chat_id=int(user_id))
                sent += 1
                break  # Break the while loop, move to next user
                
            except FloodWait as e:
                # 🛑 API Limit Reached: Sleep for the required time, then loop retries
                logger.warning(f"FloodWait of {e.value}s encountered. Sleeping...")
                await asyncio.sleep(e.value + 1)
                
            except Exception as e:
                # ❌ User blocked bot, account deleted, or invalid ID
                failed += 1
                break  # Break the while loop, move to next user
                
        # 4. Update Progress Message every 20 users to prevent FloodWait on edit
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

        # Small delay to respect general Telegram API limits (~30 msgs per sec max)
        await asyncio.sleep(0.05)

    # 5. Final Status Update
    time_taken = round(time.time() - start_time, 2)
    
    try:
        await status_msg.edit_text(
            f"✅ **Broadcast Completed Successfully!**\n\n"
            f"⏱ Time Taken: `{time_taken} seconds`\n"
            f"👥 Total Users: `{total_users}`\n"
            f"✅ Successfully Sent: `{sent}`\n"
            f"❌ Failed/Blocked: `{failed}`"
        )
    except Exception as e:
        await message.reply(f"✅ **Broadcast Completed!**\nSent: {sent} | Failed: {failed}")
