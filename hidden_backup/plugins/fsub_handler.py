from pyrogram import Client, filters, enums
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated
from database.users_chats_db import db
from info import ADMINS, LOG_CHANNEL
import logging

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. JOIN REQUEST LISTENER (Component 1)
# Trigger: Jab user "Request to Join" button dabata hai.
# Action: User ko Database ki 'Pending' list mein add karte hain.
# ==============================================================================
@Client.on_chat_join_request()
async def join_req_handler(client: Client, request: ChatJoinRequest):
    try:
        # User ID aur Channel ID ko DB me save karo (Status: Pending)
        await db.add_pending_request(request.from_user.id, request.chat.id)
        logger.info(f"➕ Pending Request Added: User {request.from_user.id} in Chat {request.chat.id}")
    except Exception as e:
        logger.error(f"Join Request Error: {e}")

# ==============================================================================
# 2. MEMBER UPDATE HANDLER (Component 2: Cleanup & Logging)
# Trigger: Jab Admin approve/decline karta hai, ya user leave karta hai.
# Action: User ko 'Pending' list se remove karte hain.
# ==============================================================================
@Client.on_chat_member_updated()
async def member_update_handler(client: Client, update: ChatMemberUpdated):
    try:
        if not update.new_chat_member: return

        user_id = update.new_chat_member.user.id
        chat_id = update.chat.id
        new_status = update.new_chat_member.status
        
        # ⚠️ CRITICAL CHECK:
        # Agar status 'RESTRICTED' hai, iska matlab user abhi bhi REQUESTED state me ho sakta hai.
        # Isliye hum use DB se REMOVE NAHI karenge.
        if new_status == enums.ChatMemberStatus.RESTRICTED:
            return

        # Agar status MEMBER, ADMIN, LEFT, ya BANNED ho gaya, 
        # iska matlab Request process khatam ho gayi. DB clean karo.
        if new_status in [
            enums.ChatMemberStatus.MEMBER,
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
            enums.ChatMemberStatus.LEFT,
            enums.ChatMemberStatus.BANNED
        ]:
            await db.remove_pending_request(user_id, chat_id)
            # logger.info(f"➖ Pending Removed: {user_id} (Status: {new_status})")

        # --- LOGGING TO CHANNEL ---
        # Sirf tab log karo agar user pehle 'Restricted' (Pending request) tha
        if LOG_CHANNEL and update.old_chat_member and update.old_chat_member.status == enums.ChatMemberStatus.RESTRICTED:
            
            admin = update.from_user 
            user = update.new_chat_member.user 
            chat_title = update.chat.title
            log_msg = ""

            # CASE A: REJECTED / LEFT
            if new_status == enums.ChatMemberStatus.LEFT:
                # Agar Admin user available hai aur User ID same hai -> User ne khud cancel kiya
                if admin and user and admin.id == user.id:
                    log_msg = f"❌ **Request Cancelled**\n👤 User: {user.mention}\n📍 Chat: {chat_title}"
                # Agar Admin alag hai -> Admin ne Decline kiya
                elif user:
                    log_msg = f"🚫 **Request Declined**\n👤 User: {user.mention}\n📍 Chat: {chat_title}"

            # CASE B: APPROVED
            elif new_status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR]:
                 if user:
                    log_msg = f"✅ **Request Approved**\n👤 User: {user.mention}\n📍 Chat: {chat_title}"
            
            # Send Log to Channel
            if log_msg:
                try: await client.send_message(LOG_CHANNEL, log_msg)
                except: pass

    except Exception as e:
        logger.error(f"Member Update Error: {e}")

# --- 3. CLEAR CACHE COMMAND (Optional Utility) ---
@Client.on_message(filters.command("delreq") & filters.private & filters.user(ADMINS))
async def del_requests(client, message):
    # Yeh bas ek dummy response hai, asli cleanup automatic hota hai upar wale handler se.
    await message.reply("<b>ℹ️ Note:</b> Join Requests automatically manage hoti hain via Database.\nManual delete ki zaroorat nahi hai.")
