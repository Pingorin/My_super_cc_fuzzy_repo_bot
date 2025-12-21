from pyrogram import Client, enums
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated
from database.users_chats_db import db
import info

# --- 1. JOIN REQUEST LISTENER ---
# Jab user "Request to Join" dabayega, ye turant DB me add karega
@Client.on_chat_join_request()
async def join_req_handler(client: Client, request: ChatJoinRequest):
    try:
        if request.chat.id == info.FSUB_CHANNEL_ID:
            await db.add_pending_request(request.from_user.id, request.chat.id)
    except Exception as e:
        print(f"Join Request Error: {e}")

# --- 2. STATUS UPDATE LISTENER ---
# Jab Admin Request Accept/Decline kare ya User Leave kare
@Client.on_chat_member_updated()
async def member_update_handler(client: Client, update: ChatMemberUpdated):
    try:
        if update.chat.id == info.FSUB_CHANNEL_ID:
            user_id = update.new_chat_member.user.id
            new_status = update.new_chat_member.status
            
            # Agar Member ban gaya ya Left ho gaya -> Remove from Pending
            if new_status in [
                enums.ChatMemberStatus.MEMBER,
                enums.ChatMemberStatus.ADMINISTRATOR,
                enums.ChatMemberStatus.BANNED,
                enums.ChatMemberStatus.LEFT,
                enums.ChatMemberStatus.OWNER
            ]:
                await db.remove_pending_request(user_id, update.chat.id)
            
    except Exception as e:
        print(f"Member Update Error: {e}")
