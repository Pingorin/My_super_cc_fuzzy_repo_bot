from pyrogram import Client, enums
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from utils import temp

# --- 1. JOIN REQUEST LISTENER ---
# Jab user "Request to Join" button dabata hai, ye trigger hoga
@Client.on_chat_join_request()
async def join_req_handler(client: Client, request: ChatJoinRequest):
    try:
        # User ko Pending List me daalo (Timestamp ke saath)
        # Note: Ensure database/users_chats_db.py has 'add_join_request'
        await db.add_join_request(request.from_user.id, request.chat.id)
    except Exception as e:
        print(f"Join Request Error: {e}")

# --- 2. STATUS UPDATE LISTENER (AUTO NOTIFY LOGIC) ---
# Jab Admin request Accept/Decline karta hai, ye trigger hoga
@Client.on_chat_member_updated()
async def member_update_handler(client: Client, update: ChatMemberUpdated):
    try:
        # Hamein sirf nayi status updates chahiye
        if not update.new_chat_member: return

        user_id = update.new_chat_member.user.id
        chat_id = update.chat.id
        new_status = update.new_chat_member.status
        
        # 🔍 Database check: Kya is user ne Request bheji thi?
        # Note: Ensure database/users_chats_db.py has 'is_join_request_pending'
        was_pending = await db.is_join_request_pending(user_id, chat_id)

        # --- ✅ CASE 1: APPROVED (User Member ban gaya) ---
        if new_status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR]:
            if was_pending:
                # 1. DB se Pending tag hatao
                await db.remove_pending_request(user_id, chat_id)
                
                # 2. User ko Congrats message bhejo
                try: 
                    await client.send_message(
                        user_id, 
                        "✅ **Request Approved!**\n\nYour request to join the channel has been accepted.\nYou can now access the files."
                    )
                except: 
                    pass # User ne bot block kiya ho to ignore karo

        # --- ❌ CASE 2: DECLINED / LEFT (Request Reject ho gayi) ---
        elif new_status == enums.ChatMemberStatus.LEFT:
            if was_pending:
                # 1. DB se hatao (Taaki wo dubara request kar sake)
                await db.remove_pending_request(user_id, chat_id)
                
                # 2. 🔥 REJECTION ALERT (With New Request Link) 🔥
                try:
                    # Naya "Request to Join" link generate karo
                    # creates_join_request=True is VERY IMPORTANT
                    link_obj = await client.create_chat_invite_link(chat_id, creates_join_request=True)
                    link = link_obj.invite_link
                    
                    btn = [
                        [InlineKeyboardButton("📢 Request Join Again", url=link)],
                        [InlineKeyboardButton("🔄 Try File Again", url=f"https://t.me/{temp.U_NAME}?start=start")]
                    ]
                    
                    await client.send_message(
                        chat_id=user_id,
                        text=(
                            "❌ **Join Request Declined.**\n\n"
                            "Admin has dismissed your request.\n"
                            "You need to request again to access the files."
                        ),
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                except Exception as e:
                    print(f"Could not send dismiss alert: {e}")

    except Exception as e:
        print(f"Member Update Error: {e}")
