from pyrogram import Client, enums
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from utils import temp

# --- 1. JOIN REQUEST LISTENER ---
@Client.on_chat_join_request()
async def join_req_handler(client: Client, request: ChatJoinRequest):
    try:
        # User ko Pending List me daalo
        await db.add_pending_request(request.from_user.id, request.chat.id)
    except Exception as e:
        print(f"Join Request Error: {e}")

# --- 2. STATUS UPDATE LISTENER (AUTO NOTIFY LOGIC) ---
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
                # Optional: Approve hone par badhai message
                try: await client.send_message(user_id, "✅ **Your request has been approved!**\nYou can now access the files.")
                except: pass

        # --- CASE 2: DISMISSED / LEFT (REJECTED) ---
        elif new_status == enums.ChatMemberStatus.LEFT:
            if was_pending:
                # 1. DB se hatao (Taaki wo dubara check ho sake)
                await db.remove_pending_request(user_id, chat_id)
                
                # 2. 🔥 USER KO TURANT MESSAGE BHEJO (With Button) 🔥
                try:
                    # Link generate karo
                    chat_info = await client.get_chat(chat_id)
                    link_obj = await client.create_chat_invite_link(chat_id, creates_join_request=True)
                    link = link_obj.invite_link
                    
                    btn = [
                        [InlineKeyboardButton("📢 Request to Join Again", url=link)],
                        [InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{temp.U_NAME}?start=start")]
                    ]
                    
                    await client.send_message(
                        chat_id=user_id,
                        text="❌ **Your Join Request was Declined.**\n\nAdmin has dismissed your request.\nYou need to request again to access the files.",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                except Exception as e:
                    print(f"Could not send dismiss alert: {e}")

    except Exception as e:
        print(f"Member Update Error: {e}")
