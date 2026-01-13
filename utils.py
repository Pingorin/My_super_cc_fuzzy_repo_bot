import logging
import math
import aiohttp
import re
import os
from pyrogram.types import InlineKeyboardButton
from pyrogram import enums
from pyrogram.errors import UserNotParticipant
from database.users_chats_db import db

# Optional Imports from Info.py
try: from info import AUTH_CHANNEL, AUTH_CHANNEL_2, AUTH_CHANNEL_3, AUTH_CHANNEL_4, API_ID, API_HASH, BOT_TOKEN
except: pass

logger = logging.getLogger(__name__)

class temp(object):
    U_NAME = None
    B_NAME = None
    B_LINK = None
    ME = None

# ✅ 1. GENERAL HELPERS
def get_size(size):
    if not size: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

# ✅ 2. TELEGRAPH SETUP
try:
    from telegraph import Telegraph
    telegraph_client = Telegraph()
    telegraph_client.create_account(short_name='AutoFilter')
except Exception as e:
    telegraph_client = None

# ✅ 3. RESULT MODE FORMATTERS

def format_text_results(files, query, chat_id):
    """Generates the List layout for Text Mode."""
    text = f"👻 **Results for:** `{query}`\n\n"
    for i, file in enumerate(files, 1):
        f_name = file['file_name']
        f_size = get_size(file['file_size'])
        link_id = file['link_id']
        f_chat_id = chat_id
        
        link = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{f_chat_id}"
        text += f"{i}. 📂 <a href='{link}'>{f_name}</a> [{f_size}]\n\n"
    return text

def format_detailed_results(files, query, chat_id, time_taken=0):
    """Generates the detailed layout with Metadata."""
    text = (
        f"⚡ **Hey {query} lovers!**\n"
        f"👻 **Here are your results....**\n"
        f"⌛ **Time taken:** {time_taken} seconds\n"
        f"code: {len(files)}\n\n"
    )
    for file in files:
        f_name = file['file_name']
        f_size = get_size(file['file_size'])
        link_id = file['link_id']
        f_chat_id = chat_id
        link = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{f_chat_id}"
        
        q_match = re.search(r"\b(1080p|720p|480p|360p|2160p|4k|HDRip|WEBRip|BluRay|DVDRip|CAM)\b", f_name, re.IGNORECASE)
        quality = q_match.group(0) if q_match else "N/A"
        
        text += f"📂 <a href='{link}'>𝘾𝙡𝙞𝙘𝙠 𝙩𝙤 𝙜𝙖𝙩 𝙩𝙝𝙞𝙨 𝙛𝙞𝙡𝙚 📥</a>\n"
        text += f"🖥 𝙉𝙖𝙢𝙚: {f_name}\n"
        text += f"📀 𝙦𝙪𝙖𝙡𝙞𝙩𝙮: {quality}\n"
        text += f"📦 [{f_size}]\n\n"
    return text

def format_card_result(file, current_index, total_count):
    """Generates the Single Card layout."""
    f_name = file['file_name']
    f_size = get_size(file['file_size'])
    
    f_type = "Document"
    if f_name.endswith(('.mkv', '.mp4', '.avi', '.webm', '.mov')): f_type = "Video"
    elif f_name.endswith(('.mp3', '.flac', '.wav', '.m4a')): f_type = "Audio"
    elif f_name.endswith(('.jpg', '.jpeg', '.png', '.webp')): f_type = "Photo"

    text = f"🎬 **{f_name}**\n\n"
    text += f"🗂️ **Type:** {f_type}\n"
    text += f"💾 **Size:** {f_size}\n\n"
    text += f"File {current_index + 1} of {total_count}"
    return text

# ✅ 4. FILTERING LOGIC
def filter_by_type(files, f_type):
    """
    Strictly filters files based on 'file_type' saved in DB.
    Ensures Videos are Streamable Videos and Docs are Documents.
    """
    if not f_type or f_type.lower() == "all":
        return files
        
    filtered = []
    target_type = f_type.lower()
    
    for f in files:
        # Get type from DB. Default to 'document' if missing.
        db_type = f.get('file_type', 'document').lower()
        
        if target_type == "video" and db_type == "video":
            filtered.append(f)
        elif target_type == "document" and db_type == "document":
            filtered.append(f)
            
    return filtered

# ✅ 5. DYNAMIC BUTTONS (Fixed for 3 Arguments)
def get_dynamic_filter_buttons(unique_id, active_filter="all", page=0):
    """
    Generates dynamic filter buttons.
    Accepts 'page' argument to prevent TypeError.
    """
    # Callback Format: filter_media#unique_id#type
    
    vid_btn = InlineKeyboardButton("🎬 Videos", callback_data=f"filter_media#{unique_id}#video")
    doc_btn = InlineKeyboardButton("📂 Docs", callback_data=f"filter_media#{unique_id}#document")
    reset_btn = InlineKeyboardButton("🔄 All Media Types", callback_data=f"unfilter_media#{unique_id}#")
    
    btn_row = []
    
    if active_filter == "video":
        btn_row.append(reset_btn)
        btn_row.append(doc_btn)
    elif active_filter == "document":
        btn_row.append(vid_btn)
        btn_row.append(reset_btn)
    else:
        btn_row.append(vid_btn)
        btn_row.append(doc_btn)
        
    return btn_row

# ✅ 6. PAGINATION HELPER
def get_pagination_row(current_offset, limit, total_count, unique_id, active_filter="all"):
    """
    Generates navigation row using '#' separator.
    Persists the 'active_filter' state across pages.
    """
    buttons = []
    current_page = int(current_offset / limit) + 1
    total_pages = math.ceil(total_count / limit)

    if total_pages == 1: return []

    # Back Button
    if current_offset >= limit:
        buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"next#{unique_id}#{current_offset - limit}#{active_filter}"))

    # Page Counter
    buttons.append(InlineKeyboardButton(f"📑 {current_page}/{total_pages}", callback_data="pages"))

    # Next Button
    if current_offset + limit < total_count:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"next#{unique_id}#{current_offset + limit}#{active_filter}"))

    return buttons

# ✅ 7. BUTTON PARSER (Cleaned)
def btn_parser(files, chat_id, unique_id, query=None, offset=0, limit=10):
    """
    Generates ONLY the file buttons. 
    Pagination is appended later in autofilter.py to ensure correct order:
    [Files] -> [Filter Buttons] -> [Pagination]
    """
    current_files = files[offset : offset + limit]
    buttons = []
    
    for file in current_files:
        f_name = file.get('file_name', 'Unknown File')
        f_size = get_size(file.get('file_size', 0))
        link_id = file.get('link_id')
        f_chat_id = chat_id
        caption = file.get('caption')

        display_name = f_name
        if query and isinstance(query, str) and caption:
            q = query.lower()
            n = f_name.lower()
            c = caption.lower()
            if q not in n and q in c:
                clean_cap = caption.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
                if len(clean_cap) > 60: clean_cap = clean_cap[:57] + "..."
                display_name = clean_cap

        btn_text = f"📂 {display_name} [{f_size}]"
        
        if link_id is not None:
            url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{f_chat_id}"
            buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    return buttons

# ✅ 8. SHORTLINK GENERATOR
async def get_shortlink(site, api, link):
    url = f'https://{site}/api'
    params = {'api': api, 'url': link}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=20) as response:
                if response.status == 200:
                    data = await response.json()
                    if "shortenedUrl" in data: return data["shortenedUrl"]
                    elif "status" in data and data["status"] == "success" and "shortenedUrl" in data: return data["shortenedUrl"]
                return None 
    except Exception as e:
        logger.error(f"Shortlink Exception ({site}): {e}")
        return None 

# ✅ 9. FSUB STATUS HELPERS
async def _get_fsub_status(bot, user_id, channel_id):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return "MEMBER"
        if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]:
            if await db.is_user_pending(user_id, channel_id): return "PENDING"
            return "NOT_JOINED"
        if member.status == enums.ChatMemberStatus.RESTRICTED:
            return "PENDING"
    except UserNotParticipant:
        if await db.is_user_pending(user_id, channel_id): return "PENDING"
        return "NOT_JOINED"
    except: return "NOT_JOINED"
    return "NOT_JOINED"

async def _get_normal_fsub_status(bot, user_id, channel_id):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
            return "MEMBER"
    except: pass
    return "NOT_JOINED"

async def check_fsub_status(bot, user_id, grp_id=None):
    id_1, id_2, id_3 = AUTH_CHANNEL, AUTH_CHANNEL_2, AUTH_CHANNEL_3
    
    if grp_id:
        settings = await db.get_group_settings(grp_id)
        if settings:
            fsub_channels = settings.get('fsub_channels', {})
            if isinstance(fsub_channels, dict):
                if fsub_channels.get('1'): id_1 = int(fsub_channels['1'])
                if fsub_channels.get('2'): id_2 = int(fsub_channels['2'])
                if fsub_channels.get('3'): id_3 = int(fsub_channels['3'])
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
    id_4 = AUTH_CHANNEL_4
    if grp_id:
        settings = await db.get_group_settings(grp_id)
        if settings:
            fsub_channels = settings.get('fsub_channels', {})
            if isinstance(fsub_channels, dict) and fsub_channels.get('4'):
                 id_4 = int(fsub_channels['4'])
            elif settings.get('fsub_id_4'): id_4 = int(settings['fsub_id_4'])
        
    if not id_4: return "MEMBER", None 
    status = await _get_fsub_status(bot, user_id, id_4)
    return status, id_4
