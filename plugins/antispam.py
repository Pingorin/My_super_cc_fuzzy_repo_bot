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
    reason = "Spam Content"

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
    # 🔨 PUNISHMENT LOGIC (3 STRIKES)
    # ==================================================================
    
    if is_spam:
        # ⚡ 1. FAST DELETE MSG
        try: await message.delete()
        except: pass 

        user_id = message.from_user.id
        chat_id = message.chat.id
        mention = message.from_user.mention
        
        # 🟥 INSTANT BAN FOR NSFW
        if is_nsfw:
            try:
                await client.ban_chat_member(chat_id, user_id)
                msg = await message.reply_text(f"🚫 **Banned:** {mention}\nReason: {reason}")
                asyncio.create_task(delete_after_delay(msg, 120))
            except: pass
            return

        # 🟨 3-STRIKE WARNING SYSTEM
        warnings = await db.add_spam_warning(chat_id, user_id)
        mute_time = settings.get('mute_duration', 600) # Default 10 mins (fetch from settings)

        # --- WARNING 1 & 2: MUTE ---
        if warnings < 3:
            try:
                # Mute User for 'mute_time' seconds
                permissions = ChatPermissions(can_send_messages=False)
                await client.restrict_chat_member(chat_id, user_id, permissions, until_date=message.date + mute_time)
                
                # Send Warning Message
                alert_text = (
                    f"{mention} has sent a {reason}.\n"
                    f"• Warns now: ({warnings}/3) ❕\n"
                    f"• Action: Muted 🔇"
                )
                msg = await message.reply_text(alert_text)
                
                # Auto-Delete Bot Message after 2 Minutes
                asyncio.create_task(delete_after_delay(msg, 120))
                
            except Exception as e:
                print(f"AntiSpam Mute Error: {e}")

        # --- WARNING 3: BAN/KICK ---
        else:
            try:
                # Determine Action (Ban or Kick based on strictness)
                # Defaulting to BAN for 3rd strike as it's the final punishment
                await client.ban_chat_member(chat_id, user_id)
                
                # Reset Warnings
                await db.reset_spam_warnings(chat_id, user_id)
                
                # Send Final Alert
                alert_text = (
                    f"{mention} has sent a {reason}.\n"
                    f"• Warns now: (3/3) ❕\n"
                    f"• Action: Banned 🚫"
                )
                msg = await message.reply_text(alert_text)
                
                # Auto-Delete Bot Message after 2 Minutes
                asyncio.create_task(delete_after_delay(msg, 120))

            except Exception as e:
                print(f"AntiSpam Ban Error: {e}")
