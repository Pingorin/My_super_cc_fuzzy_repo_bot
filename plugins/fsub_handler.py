from pyrogram import Client, filters, enums
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated
from database.users_chats_db import db
from info import ADMINS, LOG_CHANNEL
import logging

logger = logging.getLogger(__name__)

# --- 1. JOIN REQUEST LISTENER ---
@Client.on_chat_join_request()
async def join_req_handler(client: Client, request: ChatJoinRequest):
    try:
        # Request aate hi DB me 'Pending' mark karein
        await db.add_pending_request(request.from_user.id, request.chat.id)
    except Exception as e:
        logger.error(f"Join Request Error: {e}")

# --- 2. STATUS UPDATE LISTENER (LOGGING & CLEANUP) ---
@Client.on_chat_member_updated()
async def member_update_handler(client: Client, update: ChatMemberUpdated):
    try:
        if not update.new_chat_member: return

        user_id = update.new_chat_member.user.id
        chat_id = update.chat.id
        new_status = update.new_chat_member.status
        
        # Agar status abhi bhi Restricted (Pending) hai, toh kuch mat karo
        if new_status == enums.ChatMemberStatus.RESTRICTED:
            return

        # Agar Approved, Left, ya Banned hua hai, toh DB se hata do
        await db.remove_pending_request(user_id, chat_id)

        # --- LOGGING LOGIC (Repo 2 Style) ---
        # Sirf tab log karo agar user pehle 'Restricted' (Pending) tha
        if LOG_CHANNEL and update.old_chat_member and update.old_chat_member.status == enums.ChatMemberStatus.RESTRICTED:
            
            admin = update.from_user 
            user = update.new_chat_member.user 
            chat_title = update.chat.title
            log_msg = ""

            # CASE 1: REJECTED / LEFT
            if new_status == enums.ChatMemberStatus.LEFT:
                # Agar User ne khud cancel kiya
                if admin and user and admin.id == user.id:
                    log_msg = f"**User {user.mention} cancelled their join request for {chat_title}.**"
                # Agar Admin ne decline kiya
                elif user:
                    log_msg = f"**Join request for {user.mention} in {chat_title} was declined.**"

            # CASE 2: APPROVED
            elif new_status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR]:
                 if user:
                    log_msg = f"**User {user.mention} was approved in {chat_title}.**"
            
            # Send Log to Channel
            if log_msg:
                try: await client.send_message(LOG_CHANNEL, log_msg)
                except: pass

    except Exception as e:
        logger.error(f"Member Update Error: {e}")

# --- 3. CLEAR CACHE COMMAND ---
@Client.on_message(filters.command("delreq") & filters.private & filters.user(ADMINS))
async def del_requests(client, message):
    await message.reply("<b>ℹ️ Join Request Cache clear karne ke liye Database function check karein.</b>")
