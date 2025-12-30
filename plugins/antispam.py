import re
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import ChatPermissions
from database.users_chats_db import db

# 🔞 Keywords for Instant Ban (NSFW)
NSFW_KEYWORDS = ["porn", "sex", "xxx", "nude", "horny", "gore", "adult", "dick", "pussy"]

# --- HELPER: DELETE BOT MESSAGE AFTER 2 MIN ---
async def delete_after_delay(message, delay):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except:
        pass

@Client.on_message(filters.group & ~filters.me, group=10)
async def robust_antispam(client, message):
    if not message.from_user: return
    
    # 1. Check if Feature Enabled
    settings = await db.get_group_settings(message.chat.id)
    if not settings or not settings.get('antispam_enabled', False):
        return

    # 2. Skip Admins
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return
    except: return

    # ==================================================================
    # 🕵️ DETECTION LOGIC
    # ==================================================================
    is_spam = False
    is_nsfw = False
    
    text = message.text or message.caption or ""
    
    # A. 18+ Keyword Check
    if any(word in text.lower() for word in NSFW_KEYWORDS):
        is_spam = True
        is_nsfw = True

    # B. Entities Check (Links, Text Links, Mentions)
    if not is_spam and message.entities:
        for entity in message.entities:
            if entity.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK, enums.MessageEntityType.MENTION]:
                is_spam = True
                break
    
    # C. Raw Link Regex (Fallback)
    if not is_spam:
        url_pattern = r"(https?://[^\s]+)|(www\.[^\s]+)|([^\s]+\.com)"
        if re.search(url_pattern, text):
            is_spam = True

    # D. Forward Check
    if not is_spam and (message.forward_from or message.forward_from_chat):
        is_spam = True

    # E. Inline Button Check
    if not is_spam and message.reply_markup:
        is_spam = True

    # ==================================================================
    # 🔨 PUNISHMENT LOGIC (4 STRIKES SYSTEM)
    # ==================================================================
    
    if is_spam:
        # ⚡ FAST DELETE (First Action)
        try: await message.delete()
        except: pass 

        user_id = message.from_user.id
        chat_id = message.chat.id
        first_name = message.from_user.first_name
        
        # 🟥 INSTANT BAN FOR NSFW
        if is_nsfw:
            try:
                await client.ban_chat_member(chat_id, user_id)
                msg = await message.reply_text(f"🚫 **Banned:** {first_name}\nReason: NSFW Content 🔞")
                asyncio.create_task(delete_after_delay(msg, 120))
            except: pass
            return

        # 🟨 4-STRIKE WARNING SYSTEM
        # Warnings 1, 2, 3 = MUTE
        # Warning 4 = BAN
        
        warnings = await db.add_spam_warning(chat_id, user_id)
        mute_seconds = settings.get('mute_duration', 600) # Default 10 mins
        mute_minutes = int(mute_seconds / 60)

        # --- WARNING 1, 2, 3: MUTE ---
        if warnings < 4:
            try:
                # Mute User
                permissions = ChatPermissions(can_send_messages=False)
                await client.restrict_chat_member(chat_id, user_id, permissions, until_date=message.date + mute_seconds)
                
                # Send Custom Message
                alert_text = f"🔇 {first_name}, you have been muted for {mute_minutes} minutes. Reason: spam."
                msg = await message.reply_text(alert_text)
                
                # Auto-Delete Bot Message after 2 Minutes
                asyncio.create_task(delete_after_delay(msg, 120))
                
            except Exception as e:
                print(f"AntiSpam Error: {e}")

        # --- WARNING 4: BAN ---
        else:
            try:
                # Ban User
                await client.ban_chat_member(chat_id, user_id)
                
                # Reset Warnings (Optional)
                await db.reset_spam_warnings(chat_id, user_id)
                
                # Send Ban Message
                alert_text = f"🚫 {first_name}, you have been banned. Reason: Repeated Spam (4/4)."
                msg = await message.reply_text(alert_text)
                
                # Auto-Delete Bot Message
                asyncio.create_task(delete_after_delay(msg, 120))

            except Exception as e:
                print(f"AntiSpam Ban Error: {e}")
