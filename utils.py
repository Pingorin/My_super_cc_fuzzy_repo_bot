import logging
import math
import aiohttp
from pyrogram import enums
from pyrogram.errors import UserNotParticipant, PeerIdInvalid, ChannelInvalid
from pyrogram.types import InlineKeyboardButton
from database.users_chats_db import db

logger = logging.getLogger(__name__)

class temp(object):
    U_NAME = None

def get_size(size):
    if not size: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

# --- SHORTLINK GENERATOR (WITH 20s TIMEOUT) ---
async def get_shortlink(site, api, link):
    url = f'https://{site}/api'
    params = {'api': api, 'url': link}
    
    try:
        async with aiohttp.ClientSession() as session:
            # ✅ UPDATED: Timeout set to 20 Seconds
            async with session.get(url, params=params, timeout=20) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Standard API Response Check
                    if "shortenedUrl" in data:
                        return data["shortenedUrl"]
                    elif "status" in data and data["status"] == "success" and "shortenedUrl" in data:
                        return data["shortenedUrl"]
                
                # Agar valid response nahi mila
                logger.error(f"Shortener Failed ({site}): Status {response.status}")
                return None 

    except Exception as e:
        logger.error(f"Shortlink Exception ({site}): {e}")
        return None # Return None taaki Commands.py isko Skip karke next try kare

# --- ADVANCED FSUB CHECK (Database + Live) ---
async def get_fsub_status(client, user_id, channel_id):
    """
    Checks if user is Member OR has a Pending Join Request.
    Handles PeerIdInvalid by falling back to Database.
    Returns: True (Allowed) / False (Not Allowed)
    """
    # 1. LIVE CHECK: Telegram API se pucho
    try:
        member = await client.get_chat_member(channel_id, user_id)
        
        # Agar user Member, Admin ya Owner hai to OK
        if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return True
            
    except UserNotParticipant:
        # User channel mein nahi hai, ab DB check karenge
        pass
    except (PeerIdInvalid, ChannelInvalid):
        # Bot restart hua hai ya channel access nahi hai
        # Aise case mein hum DB check par rely karenge
        logger.warning(f"⚠️ Peer Error for {channel_id} during FSub Check. Falling back to DB.")
    except Exception as e:
        logger.error(f"❌ FSub Check Error: {e}")

    # 2. DATABASE CHECK: Kya user ne Request bheji hai?
    # (Agar "Request to Join" button dabaya tha aur bot ne restart ke baad cache kho diya)
    try:
        if await db.is_join_request_pending(user_id, channel_id):
            return True
    except Exception as e:
        logger.error(f"DB FSub Check Error: {e}")

    # 3. Agar dono jagah nahi mila, to False
    return False

def btn_parser(files, chat_id, query=None):
    buttons = []
    for file in files:
        f_name = file['file_name']
        f_size = get_size(file['file_size'])
        link_id = file.get('link_id')
        caption = file.get('caption')

        display_name = f_name
        if query and caption:
            q = query.lower()
            n = f_name.lower()
            c = caption.lower()
            if q not in n and q in c:
                clean_cap = caption.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
                if len(clean_cap) > 60: clean_cap = clean_cap[:57] + "..."
                display_name = clean_cap

        btn_text = f"📂 {display_name} [{f_size}]"
        
        if link_id is not None:
            # Format: get_LINKID_CHATID
            # Link ID ke sath Chat ID bhejna zaroori hai group settings fetch karne ke liye
            url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}"
            buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    return buttons
