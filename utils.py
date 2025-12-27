import logging
import math
import aiohttp
import os
from pyrogram.types import InlineKeyboardButton
from pyrogram import enums
from pyrogram.errors import UserNotParticipant
from database.users_chats_db import db
from info import ADMINS, AUTH_CHANNEL

# Optional Imports from Info.py
try: from info import AUTH_CHANNEL_2
except: AUTH_CHANNEL_2 = None
try: from info import AUTH_CHANNEL_3
except: AUTH_CHANNEL_3 = None
try: from info import AUTH_CHANNEL_4
except: AUTH_CHANNEL_4 = None

logger = logging.getLogger(__name__)

class temp(object):
    U_NAME = None
    B_NAME = None
    B_LINK = None
    ME = None

# --- 1. FILE SIZE FORMATTER ---
def get_size(size):
    if not size: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

# --- 2. SHORTLINK GENERATOR (UPDATED: 20s TIMEOUT) ---
async def get_shortlink(site, api, link):
    url = f'https://{site}/api'
    params = {'api': api, 'url': link}
    
    try:
        async with aiohttp.ClientSession() as session:
            # ✅ Timeout set to 20 Seconds
            async with session.get(url, params=params, timeout=20) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Standard API Response Check
                    if "shortenedUrl" in data:
                        return data["shortenedUrl"]
                    elif "status" in data and data["status"] == "success" and "shortenedUrl" in data:
                        return data["shortenedUrl"]
                
                # Log error if status is not 200
                logger.error(f"Shortener Failed ({site}): Status {response.status}")
                return None 

    except Exception as e:
        logger.error(f"Shortlink Exception ({site}): {e}")
        return None 

# --- 3. BUTTON PARSER (UPDATED: INCLUDES CHAT_ID) ---
def btn_parser(files, chat_id, query=None):
    buttons = []
    for file in files:
        f_name = file.get('file_name', 'Unknown File')
        f_size = get_size(file.get('file_size', 0))
        link_id = file.get('link_id')
        caption = file.get('caption')

        display_name = f_name
        # 
        if query and caption:
            q = query.lower()
            n = f_name.lower()
            c = caption.lower()
            # If query is in caption but not in filename, use caption as display name
            if q not in n and q in c:
                clean_cap = caption.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
                if len(clean_cap) > 60: clean_cap = clean_cap[:57] + "..."
                display_name = clean_cap

        btn_text = f"📂 {display_name} [{f_size}]"
        
        if link_id is not None:
            # Format: get_LINKID_CHATID
            # Passing Chat ID is crucial for group-specific verification settings
            url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}"
            buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    return buttons

# ==============================================================================
# 🔥 FSUB SYSTEM LOGIC
# ==============================================================================

async def _get_fsub_status(bot, user_id, channel_id):
    """
    Advanced Check: Checks for Member, Admin, Owner, or Pending Request.
    """
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return "MEMBER"
        
        # If user Left or Banned, check if they have a Pending Request in DB
        if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
            if await db.is_user_pending(user_id, channel_id): return "PENDING"
            return "NOT_JOINED"
        
        # If Telegram API says Restricted, usually means Pending/Requested
        if member.status == enums.ChatMemberStatus.RESTRICTED:
            return "PENDING"
            
    except UserNotParticipant:
        # Not a participant, check DB for pending request
        if await db.is_user_pending(user_id, channel_id): return "PENDING"
        return "NOT_JOINED"
    except Exception as e:
        # Fallback for other errors (e.g. Chat Invalid)
        return "NOT_JOINED"
    
    return "NOT_JOINED"

async def _get_normal_fsub_status(bot, user_id, channel_id):
    """
    Normal Channel Check (Slot 3) - Only checks if joined.
    """
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return "MEMBER"
    except: pass
    return "NOT_JOINED"

async def check_fsub_status(bot, user_id, grp_id=None):
    """
    Returns statuses for Slot 1, 2, and 3 along with their IDs.
    Returns: (status1, status2, status3, id1, id2, id3)
    """
    id_1, id_2, id_3 = AUTH_CHANNEL, AUTH_CHANNEL_2, AUTH_CHANNEL_3
    
    # Override defaults if Group Settings exist
    if grp_id:
        settings = await db.get_group_settings(grp_id)
        if settings:
            fsub_channels = settings.get('fsub_channels', {})
            if isinstance(fsub_channels, dict):
                if fsub_channels.get('1'): id_1 = int(fsub_channels['1'])
                if fsub_channels.get('2'): id_2 = int(fsub_channels['2'])
                if fsub_channels.get('3'): id_3 = int(fsub_channels['3'])
            
            # Legacy support
            if settings.get('fsub_id_1'): id_1 = int(settings['fsub_id_1'])
            if settings.get('fsub_id_2'): id_2 = int(settings['fsub_id_2'])
            if settings.get('fsub_id_3'): id_3 = int(settings['fsub_id_3'])

    status_1 = "MEMBER"
    if id_1: status_1 = await _get_fsub_status(bot, user_id, id_1)
    
    status_2 = "MEMBER"
    if id_2: status_2 = await _get_fsub_status(bot, user_id, id_2)
    
    status_3 = "MEMBER"
    if id_3: status_3 = await _get_normal_fsub_status(bot, user_id, id_3)
    
    return status_1, status_2, status_3, id_1, id_2, id_3

async def check_fsub_4_status(bot, user_id, grp_id=None):
    """
    Checks status for Slot 4 (Post-Verify).
    """
    id_4 = AUTH_CHANNEL_4
    if grp_id:
        settings = await db.get_group_settings(grp_id)
        if settings:
            fsub_channels = settings.get('fsub_channels', {})
            if isinstance(fsub_channels, dict) and fsub_channels.get('4'):
                 id_4 = int(fsub_channels['4'])
            elif settings.get('fsub_id_4'): id_4 = int(settings['fsub_id_4'])
        
    if not id_4: return "MEMBER", None 
    
    # Slot 4 uses Advanced Check (Pending allowed)
    status = await _get_fsub_status(bot, user_id, id_4)
    return status, id_4
