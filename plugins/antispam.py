import re
from pyrogram import Client, filters, enums
from pyrogram.types import ChatPermissions, MessageEntity
from database.users_chats_db import db
from info import ADMINS
import asyncio

# 🔞 Keywords for Instant Ban (Customize as needed)
NSFW_KEYWORDS = ["porn", "sex", "xxx", "nude", "horny", "gore", "adult", "dick", "pussy"]

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
    reason = ""

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
                reason = "Link Detected 🔗"
                break
            if entity.type == enums.MessageEntityType.MENTION:
                is_spam = True
                reason = "Username Mention 🏷️"
                break
    
    # C. Raw Link Regex (Fallback)
    if not is_spam:
        url_pattern = r"(https?://[^\s]+)|(www\.[^\s]+)|([^\s]+\.com)"
        if re.search(url_pattern, text):
            is_spam = True
            reason = "Link Detected 🔗"

    # D. Forward Check
    if not is_spam and (message.forward_from or message.forward_from_chat):
        is_spam = True
        reason = "Forwarded Message ⏩"

    # E. Inline Button Check
    if not is_spam and message.reply_markup:
        is_spam = True
        reason = "Inline Button/Keyboard ⌨️"

    # ==================================================================
    # 🔨 PUNISHMENT LOGIC
    # ==================================================================
    
    if is_spam:
        # Step 1: Immediate Delete
        try: await message.delete()
        except: pass # Bot might lack permission

        user_id = message.from_user.id
        chat_id = message.chat.id
        name = message.from_user.mention
        
        # 🟥 INSTANT BAN FOR NSFW
        if is_nsfw:
            try:
                await client.ban_chat_member(chat_id, user_id)
                await message.reply_text(f"🚫 **Banned:** {name}\nReason: {reason}")
            except: pass
            return

        # 🟨 GENERAL SPAM HIERARCHY
        action_mode = settings.get('antispam_action', 'mute') # 'mute' or 'kick'
        
        # If Mode is "Kick", skip warnings -> Kick immediately
        if action_mode == 'kick':
            try:
                await client.ban_chat_member(chat_id, user_id) # Kick (Ban then Unban usually, or just Ban)
                await client.unban_chat_member(chat_id, user_id) # Soft Ban = Kick
                await message.reply_text(f"👢 **Kicked:** {name}\nReason: {reason} (Strict Mode)")
            except: pass
            return

        # If Mode is "Warn/Mute" -> Use 3 Strike System
        warnings = await db.add_spam_warning(chat_id, user_id)
        mute_time = settings.get('mute_duration', 600)

        # STRIKE 1: Warn + Mute
        if warnings == 1:
            try:
                # Mute User
                permissions = ChatPermissions(can_send_messages=False)
                await client.restrict_chat_member(chat_id, user_id, permissions, until_date=message.date + mute_time)
                
                await message.reply_text(
                    f"⚠️ **Warning (1/3):** {name}\n"
                    f"Reason: {reason}\n"
                    f"Action: Muted for {int(mute_time/60)} mins."
                )
            except: pass
        
        # STRIKE 2: Kick (Soft Ban)
        elif warnings == 2:
            try:
                await client.ban_chat_member(chat_id, user_id)
                await client.unban_chat_member(chat_id, user_id)
                await message.reply_text(
                    f"👢 **Kicked (2/3):** {name}\n"
                    f"Reason: {reason}\n"
                    f"Next violation = Perm Ban."
                )
            except: pass

        # STRIKE 3: Permanent Ban
        elif warnings >= 3:
            try:
                await client.ban_chat_member(chat_id, user_id)
                await db.reset_spam_warnings(chat_id, user_id) # Reset counter after ban
                await message.reply_text(
                    f"🚫 **Banned (3/3):** {name}\n"
                    f"Reason: Repeated Spamming."
                )
            except: pass
