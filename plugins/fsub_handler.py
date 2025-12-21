from pyrogram import Client, enums
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated
from database.users_chats_db import db

# --- 1. JOIN REQUEST LISTENER (UNIVERSAL) ---
# Jab user kisi bhi channel me "Request to Join" dabayega jaha bot admin hai
@Client.on_chat_join_request()
async def join_req_handler(client: Client, request: ChatJoinRequest):
    try:
        # User aur Channel ID ko DB me 'pending' list me save karo.
        # Hum yahan filter nahi lagayenge kyunki alag-alag groups ke liye alag channels ho sakte hain.
        await db.add_pending_request(request.from_user.id, request.chat.id)
    except Exception as e:
        print(f"Join Request Error: {e}")

# --- 2. STATUS UPDATE LISTENER (UNIVERSAL) ---
# Jab Admin Request Accept/Decline kare ya User Leave kare
@Client.on_chat_member_updated()
async def member_update_handler(client: Client, update: ChatMemberUpdated):
    try:
        if not update.new_chat_member: return

        user_id = update.new_chat_member.user.id
        chat_id = update.chat.id
        new_status = update.new_chat_member.status
        
        # Agar status change hua (Member bana, Left hua, Ban hua, etc.)
        # To use Pending List se hata do.
        if new_status in [
            enums.ChatMemberStatus.MEMBER,
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.BANNED,
            enums.ChatMemberStatus.LEFT,
            enums.ChatMemberStatus.OWNER
        ]:
            await db.remove_pending_request(user_id, chat_id)
            
    except Exception as e:
        print(f"Member Update Error: {e}")

