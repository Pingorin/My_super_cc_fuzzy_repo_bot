import logging
import math
import aiohttp
import os
import re
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

# ✅ 2. TELEGRAPH SETUP (For Site Mode)
try:
    from telegraph import Telegraph
    telegraph_client = Telegraph()
    telegraph_client.create_account(short_name='AutoFilter')
except Exception as e:
    logger.warning(f"Telegraph library not found or error: {e}")
    telegraph_client = None

# ✅ 3. QUALITY EXTRACTION HELPER
def extract_qualities(files):
    """
    Scans files and returns a dictionary of qualities found with their counts.
    e.g., {'1080p': 5, '720p': 3}
    """
    qualities = {}
    # Regex to find common qualities
    pattern = re.compile(r"\b(4k|2160p|1080p|720p|480p|360p|hd|cam|hdcam|dvdrip|bluray)\b", re.IGNORECASE)
    
    for file in files:
        name = file.get('file_name', '').lower()
        match = pattern.search(name)
        if match:
            qual = match.group(1).lower()
            # Normalize names (e.g., 2160p -> 4k)
            if qual == '2160p': qual = '4k'
            
            qualities[qual] = qualities.get(qual, 0) + 1
        else:
            # Files with no specific quality in name
            pass
            
    return qualities

# ✅ 4. RESULT MODE FORMATTERS

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
        
        l_matches = re.findall(r"\b(Hindi|Eng|English|Tam|Tamil|Tel|Telugu|Mal|Malayalam|Kan|Kannada|Ben|Bengali|Pun|Punjabi|Mar|Marathi)\b", f_name, re.IGNORECASE)
        if l_matches:
            lang = ", ".join(sorted(set([l.capitalize() for l in l_matches])))
        else:
            lang = "N/A"

        text += f"📂 <a href='{link}'>𝘾𝙡𝙞𝙘𝙠 𝙩𝙤 𝙜𝙖𝙩 𝙩𝙝𝙞𝙨 𝙛𝙞𝙡𝙚 📥</a>\n"
        text += f"🖥 𝙉𝙖𝙢𝙚: {f_name}\n"
        text += f"📀 𝙦𝙪𝙖𝙡𝙞𝙩𝙮: {quality}\n"
        text += f"🌍 𝙡𝙖𝙣𝙜𝙪𝙖𝙜𝙚: {lang}\n"
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

async def post_to_telegraph(files, query, chat_id):
    if not telegraph_client: return None
    
    html_content = f"<h3>Search Results for: {query}</h3><br>"
    for file in files:
        f_name = file['file_name']
        f_size = get_size(file['file_size'])
        link_id = file['link_id']
        f_chat_id = chat_id
        
        link = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{f_chat_id}"
        html_content += f"<p>📂 <a href='{link}'>{f_name}</a> [{f_size}]</p><hr>"
    
    try:
        response = telegraph_client.create_page(title=f"Results: {query}", html_content=html_content)
        return response['url']
    except Exception as e:
        logger.error(f"Telegraph Error: {e}")
        return None

# ✅ 5. PAGINATION HELPER (Updated to use search_id)
def get_pagination_row(current_offset, limit, total_count, search_id, active_quality=None):
    """
    Generates the navigation row: [ ⬅️ Back ] [ 1/5 ] [ Next ➡️ ]
    Uses 'search_id' in callback data to prevent 'Expire' issues with long queries.
    """
    buttons = []
    
    current_page = int(current_offset / limit) + 1
    total_pages = math.ceil(total_count / limit)

    if total_pages == 1:
        return []

    # Prepare Quality Parameter for Callback
    q_param = active_quality if active_quality else "all"

    # 1. Back Button
    if current_offset >= limit:
        buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"next_{current_offset - limit}_{search_id}_{q_param}"))

    # 2. Page Counter (Static)
    buttons.append(InlineKeyboardButton(f"📑 {current_page}/{total_pages}", callback_data="pages"))

    # 3. Next Button
    if current_offset + limit < total_count:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"next_{current_offset + limit}_{search_id}_{q_param}"))

    return buttons

# ✅ 6. BUTTON PARSER (Updated to use search_id for callbacks)
def btn_parser(files, chat_id, search_id, query=None, offset=0, limit=10, active_quality=None):
    """
    Generates buttons for Inline Result Mode with Pagination AND Quality Filters.
    
    Args:
        files: List of file dictionaries
        chat_id: Group ID
        search_id: Unique ID for the search (used in callbacks)
        query: Original text query (used ONLY for text highlighting, optional)
        offset: Pagination offset
        limit: Files per page
        active_quality: '720p', '1080p', etc.
    """
    
    # --- 1. FILTERING LOGIC ---
    filtered_files = []
    
    if active_quality and active_quality != "all":
        # Create Pattern based on selection
        if active_quality == '4k':
            pattern = re.compile(r"\b(4k|2160p)\b", re.IGNORECASE)
        else:
            pattern = re.compile(rf"\b{re.escape(active_quality)}\b", re.IGNORECASE)
            
        for file in files:
            fname = file.get('file_name', '').lower()
            if pattern.search(fname):
                filtered_files.append(file)
    else:
        # No filter active, show all
        filtered_files = files

    # --- 2. PAGINATION SLICING ---
    # Slice the FILTERED list
    current_files = filtered_files[offset : offset + limit]
    
    buttons = []
    for file in current_files:
        f_name = file.get('file_name', 'Unknown File')
        f_size = get_size(file.get('file_size', 0))
        link_id = file.get('link_id')
        f_chat_id = chat_id
        caption = file.get('caption')

        display_name = f_name
        # Visual Highlight Logic (Only if query is provided)
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
            url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{f_chat_id}"
            buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    # --- 3. PAGINATION ROW ---
    # Pass search_id to pagination to keep callbacks short
    pagination = get_pagination_row(offset, limit, len(filtered_files), search_id, active_quality)
    if pagination:
        buttons.append(pagination)
    
    # --- 4. QUALITY FILTER BUTTONS ---
    
    if active_quality and active_quality != "all":
        # State: Quality Selected -> Show Checkmark & Reset
        buttons.append([
            InlineKeyboardButton(f"{active_quality.upper()} ✅", callback_data="pages"), # Static button
            InlineKeyboardButton("All Qualities", callback_data=f"qual_reset_{search_id}")
        ])
    else:
        # State: No Selection -> Show "Select Qualities" IF valid qualities exist
        qual_counts = extract_qualities(files) # Check full file list for qualities
        if len(qual_counts) > 0:
            buttons.append([
                InlineKeyboardButton("✨ Select Qualities", callback_data=f"qual_menu_{search_id}")
            ])

    return buttons

# ✅ 7. SHORTLINK GENERATOR
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
                logger.error(f"Shortener Failed ({site}): Status {response.status}")
                return None 
    except Exception as e:
        logger.error(f"Shortlink Exception ({site}): {e}")
        return None 

# ✅ 8. FSUB STATUS HELPERS
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
