from pyrogram import Client, enums
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated
from database.users_chats_db import db

# --- 1. JOIN REQUEST LISTENER (जब रिक्वेस्ट आए) ---
# Trigger: जब यूजर "Request to Join" बटन दबाता है
@Client.on_chat_join_request()
async def join_req_handler(client: Client, request: ChatJoinRequest):
    try:
        # User और Chat ID को DB में 'pending' लिस्ट में Add करो
        await db.add_pending_request(request.from_user.id, request.chat.id)
        # Optional: Debugging ke liye print laga sakte hain
        # print(f"New Request: {request.from_user.id} in {request.chat.id}")
    except Exception as e:
        print(f"Join Request Error: {e}")

# --- 2. MEMBER STATUS UPDATE (जब स्टेटस बदले) ---
# Trigger: जब एडमिन Approve/Decline करे या यूजर Leave करे
@Client.on_chat_member_updated()
async def member_update_handler(client: Client, update: ChatMemberUpdated):
    try:
        # Valid update check
        if not update.new_chat_member:
            return

        user_id = update.new_chat_member.user.id
        chat_id = update.chat.id
        new_status = update.new_chat_member.status
        
        # --- LOGIC: DATABASE CLEANUP ---
        
        # CASE A: APPROVED (Member/Admin ban gaya)
        # CASE B: LEFT/BANNED (Group se nikal gaya ya nikal diya gaya)
        
        # In dono cases me user ab "Pending" nahi raha. 
        # Ya to wo andar hai (Member) ya bahar hai (Left).
        # Isliye use Pending List se DELETE kar do.
        
        if new_status in [
            enums.ChatMemberStatus.MEMBER,
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
            enums.ChatMemberStatus.BANNED,
            enums.ChatMemberStatus.LEFT
        ]:
            await db.remove_pending_request(user_id, chat_id)
            # print(f"Removed from Pending: {user_id} (Status: {new_status})")
            
    except Exception as e:
        print(f"Member Update Error: {e}")
