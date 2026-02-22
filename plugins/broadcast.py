import logging
import asyncio
import time
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import ADMINS

# ✅ Aapka Database Import
from database.users_chats_db import db

logger = logging.getLogger(__name__)

@Client.on_message(filters.command("broadcast") & filters.user(ADMINS))
async def broadcast_handler(client, message):
    # 1. Check if replying to a message
    if not message.reply_to_message:
        return await message.reply(
            "⚠️ **Error:** Jis message ko bhejna hai, uspar reply karke `/broadcast` likhein.\n\n"
            "🔘 **Button add karne ka asan tarika (Line change karke):**\n"
            "`/broadcast`\n"
            "`Button Ka Naam`\n"
            "`https://t.me/AapkaLink`"
        )

    msg_to_broadcast = message.reply_to_message
    raw_text = message.text
    
    btn_text = None
    btn_url = None
    
    # ==================================================================
    # 🔘 INLINE BUTTON PARSING LOGIC (ASAN TARIKA)
    # ==================================================================
    if "|" in raw_text:
        # Purana tarika agar koi use karna chahe
        parts = raw_text.split("|")
        cmd_part = parts[0].strip().split()
        if len(parts) >= 3:
            btn_text = parts[1].strip()
            btn_url = parts[2].strip()
    elif "\n" in raw_text:
        # Naya asan tarika (Enter wala)
        lines = raw_text.split("\n")
        cmd_part = lines[0].strip().split()
        if len(lines) >= 3:
            btn_text = lines[1].strip()
            btn_url = lines[2].strip()
    else:
        cmd_part = message.command

    # Create Inline Keyboard agar button details hain
    reply_markup = None
    if btn_text and btn_url:
        if not btn_url.startswith(("http://", "https://", "t.me/")):
            return await message.reply("❌ **Invalid Link!** Link `http://`, `https://` ya `t.me/` se shuru hona chahiye.")
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn_text, url=btn_url)]])
    else:
        # Agar original message me koi button pehle se hai, toh wahi copy hoga
        reply_markup = msg_to_broadcast.reply_markup

    # ==================================================================
    # 🎯 TARGET SELECTION LOGIC
    # ==================================================================
    all_users = []
    
    if len(cmd_part) > 1:
        # Specific Users ke liye
        for u_id in cmd_part[1:]:
            try:
                all_users.append(int(u_id))
            except ValueError:
                continue
                
        if not all_users:
            return await message.reply("❌ Koi valid User ID nahi mili.")
            
        status_msg = await message.reply(f"🔄 **{len(all_users)} Specific Users ko message bhej raha hoon...**")
        
    else:
        # Sabhi Users ke liye
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

    # 🚀 Broadcast Loop
    for target_user_id in all_users:
        while True:
            try:
                await msg_to_broadcast.copy(
                    chat_id=int(target_user_id),
                    reply_markup=reply_markup
                )
                sent += 1
                break
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                failed += 1
                last_error = str(e)
                break
                
        # 🔄 UI Update
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
    
    # 📊 Final Status Update
    if total_users == 1 and failed == 1:
        try:
            await status_msg.edit_text(
                f"❌ **Message Nahi Gaya!**\n\n"
                f"**Reason:** `{last_error}`\n\n"
                f"*(Note: Ya toh ye ID galat hai, ya iss user ne bot ko block kar diya hai)*"
            )
        except Exception:
            pass
    else:
        try:
            await status_msg.edit_text(
                f"✅ **Broadcast Completed Successfully!**\n\n"
                f"⏱ Time Taken: `{time_taken} seconds`\n"
                f"👥 Target Users: `{total_users}`\n"
                f"✅ Successfully Sent: `{sent}`\n"
                f"❌ Failed/Blocked: `{failed}`"
            )
        except Exception:
            await message.reply(f"✅ **Broadcast Completed!**\nSent: {sent} | Failed: {failed}")
