from pyrogram import Client, filters, enums
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from utils import temp
from info import ADMINS, LOG_CHANNEL
import logging

logger = logging.getLogger(__name__)

# --- 1. JOIN REQUEST LISTENER ---
@Client.on_chat_join_request()
async def join_req_handler(client: Client, request: ChatJoinRequest):
    try:
        # User ko Pending List me daalo
        await db.add_pending_request(request.from_user.id, request.chat.id)
    except Exception as e:
        logger.error(f"Join Request Error: {e}")

# --- 2. STATUS UPDATE LISTENER (AUTO NOTIFY & LOGGING) ---
@Client.on_chat_member_updated()
async def member_update_handler(client: Client, update: ChatMemberUpdated):
    try:
        if not update.new_chat_member: return

        user_id = update.new_chat_member.user.id
        chat_id = update.chat.id
        new_status = update.new_chat_member.status
        
        # Check karo ki kya ye user Database me 'Pending' tha?
        was_pending = await db.is_user_pending(user_id, chat_id)

        # --- CASE 1: APPROVED (MEMBER) ---
        if new_status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR]:
            if was_pending:
                await db.remove_pending_request(user_id, chat_id)
                
                # 1. Notify User
                try: 
                    await client.send_message(user_id, "✅ **Your request has been approved!**\nYou can now access the files.")
                except: pass

                # 2. Log to Log Channel
                if LOG_CHANNEL:
                    try:
                        user = update.new_chat_member.user
                        chat = update.chat
                        await client.send_message(
                            LOG_CHANNEL,
                            f"✅ **FSub Request Approved**\n\n"
                            f"👤 User: {user.mention} (`{user.id}`)\n"
                            f"📍 Channel: {chat.title}\n"
                            f"🤖 By: Auto-Approve / Admin"
                        )
                    except: pass

        # --- CASE 2: DISMISSED / LEFT (REJECTED) ---
        elif new_status == enums.ChatMemberStatus.LEFT:
            if was_pending:
                # 1. DB se hatao (Taaki wo dubara check ho sake)
                await db.remove_pending_request(user_id, chat_id)
                
                # 2. 🔥 USER KO TURANT MESSAGE BHEJO (With Button) 🔥
                try:
                    chat_info = await client.get_chat(chat_id)
                    # Try to create a request link
                    try:
                        link_obj = await client.create_chat_invite_link(chat_id, creates_join_request=True)
                        link = link_obj.invite_link
                    except:
                        link = f"https://t.me/{temp.U_NAME}" # Fallback

                    btn = [
                        [InlineKeyboardButton("📢 Request to Join Again", url=link)],
                        [InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{temp.U_NAME}?start=start")]
                    ]
                    
                    await client.send_message(
                        chat_id=user_id,
                        text=f"❌ **Your Join Request was Declined.**\n\n"
                             f"Admin has dismissed your request for **{chat_info.title}**.\n"
                             f"You need to request again to access the files.",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                except Exception as e:
                    logger.error(f"Could not send dismiss alert: {e}")

                # 3. Log to Log Channel
                if LOG_CHANNEL:
                    try:
                        user = update.new_chat_member.user
                        chat = update.chat
                        await client.send_message(
                            LOG_CHANNEL,
                            f"❌ **FSub Request Declined**\n\n"
                            f"👤 User: {user.mention} (`{user.id}`)\n"
                            f"📍 Channel: {chat.title}"
                        )
                    except: pass

    except Exception as e:
        logger.error(f"Member Update Error: {e}")

# --- 3. CLEANUP COMMAND (MAINTENANCE) ---
@Client.on_message(filters.command("delreq") & filters.private & filters.user(ADMINS))
async def del_requests(client, message):
    """
    Clears the Join Request database cache.
    Use this if DB gets too big or buggy.
    """
    try:
        # Direct DB access to delete all pending requests
        await db.fsub_pending.delete_many({})
        await message.reply("<b>⚙️ Successfully cleared Join Request Cache.</b>")
    except Exception as e:
        await message.reply(f"Error: {e}")
