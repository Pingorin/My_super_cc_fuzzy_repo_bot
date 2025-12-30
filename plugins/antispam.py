import re
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import ChatPermissions
from database.users_chats_db import db

# 🔞 Keywords for Instant Ban (NSFW remains strict for safety)
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
    reason = "Spam"
    
    text = message.text or message.caption or ""
    
    # A. 18+ Keyword Check
    if any(word in text.lower() for word in NSFW_KEYWORDS):
        is_spam = True
        is_nsfw = True
        reason = "NSFW Content 🔞"

    # B. Entities Check (Links, Text Links, Mentions)
    if not is_spam and message.entities:
        for entity in message.entities:
            if entity.type in [enums.MessageEntityType.URL, enums.MessageEntityType.TEXT_LINK]:
                is_spam = True
                reason = "🔗 Link without authorization"
                break
            if entity.type == enums.MessageEntityType.MENTION:
                is_spam = True
                reason = "🏷️ Mention without authorization"
                break
    
    # C. Raw Link Regex (Fallback)
    if not is_spam:
        url_pattern = r"(https?://[^\s]+)|(www\.[^\s]+)|([^\s]+\.com)"
        if re.search(url_pattern, text):
            is_spam = True
            reason = "🔗 Link without authorization"

    # D. Forward Check
    if not is_spam and (message.forward_from or message.forward_from_chat):
        is_spam = True
        reason = "⏩ Forwarded Message"

    # E. Inline Button Check
    if not is_spam and message.reply_markup:
        is_spam = True
        reason = "⌨️ Inline Button"

    # ==================================================================
    # 🔨 PUNISHMENT LOGIC (DIRECT ACTION - NO WARNINGS)
    # ==================================================================
    
    if is_spam:
        # 1. Instant Delete (Always)
        try: await message.delete()
        except: pass 

        user_id = message.from_user.id
        chat_id = message.chat.id
        first_name = message.from_user.first_name

        # 🟥 EXCEPTION: NSFW IS ALWAYS BAN (Safety First)
        if is_nsfw:
            try:
                await client.ban_chat_member(chat_id, user_id)
                msg = await message.reply_text(f"🚫 **Banned:** {first_name}\nReason: {reason}")
                asyncio.create_task(delete_after_delay(msg, 120))
            except: pass
            return

        # 🟨 GENERAL SPAM: CHECK SETTINGS
        action = settings.get('antispam_action', 'mute') # 'mute' or 'kick'
        mute_seconds = settings.get('mute_duration', 600) # Default 10 mins
        mute_minutes = int(mute_seconds / 60)

        # --- OPTION A: ACTION = KICK ---
        if action == 'kick':
            try:
                # Kick = Ban then Unban
                await client.ban_chat_member(chat_id, user_id)
                await client.unban_chat_member(chat_id, user_id)
                
                alert_text = f"👢 {first_name}, you have been Kicked. Reason: {reason}"
                msg = await message.reply_text(alert_text)
                
                asyncio.create_task(delete_after_delay(msg, 120))
            except Exception as e:
                print(f"Kick Error: {e}")

        # --- OPTION B: ACTION = MUTE (WARN) ---
        else:
            try:
                # Mute for Specific Time (e.g., 10 mins)
                permissions = ChatPermissions(can_send_messages=False)
                await client.restrict_chat_member(chat_id, user_id, permissions, until_date=message.date + mute_seconds)
                
                # Simple Alert Message (No strike count)
                alert_text = (
                    f"🔇 {first_name}, you have been muted for {mute_minutes} minutes.\n"
                    f"Reason: {reason}"
                )
                msg = await message.reply_text(alert_text)
                
                asyncio.create_task(delete_after_delay(msg, 120))
            except Exception as e:
                print(f"Mute Error: {e}")
