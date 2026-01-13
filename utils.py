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

def get_size(size):
    if not size: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

try:
    from telegraph import Telegraph
    telegraph_client = Telegraph()
    telegraph_client.create_account(short_name='AutoFilter')
except:
    telegraph_client = None

# ✅ NEW: Filter Button Generator
def get_filter_buttons(unique_id, active_mode=None):
    """
    Generates the Media Type toggle buttons.
    unique_id: The current search session ID.
    active_mode: 'video' | 'document' | None
    """
    # Visual state
    vid_text = "Videos ✅" if active_mode == 'video' else "Videos 📹"
    doc_text = "Docs ✅" if active_mode == 'document' else "Docs 📂"
    
    # Toggle Buttons
    row1 = [
        InlineKeyboardButton(vid_text, callback_data=f"filter_video_{unique_id}"),
        InlineKeyboardButton(doc_text, callback_data=f"filter_doc_{unique_id}")
    ]
    
    buttons = [row1]
    
    # "All Media" Button (Only if filter is active)
    if active_mode:
        buttons.append([
            InlineKeyboardButton(f"⬅️ All Media Types (Show {active_mode.capitalize()}s Only)", callback_data=f"unfilter_{unique_id}")
        ])
        
    return buttons

def format_text_results(files, query, chat_id):
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
        lang = ", ".join(sorted(set([l.capitalize() for l in l_matches]))) if l_matches else "N/A"

        text += f"📂 <a href='{link}'>𝘾𝙡𝙞𝙘𝙠 𝙩𝙤 𝙜𝙖𝙩 𝙩𝙝𝙞𝙨 𝙛𝙞𝙡𝙚 📥</a>\n"
        text += f"🖥 𝙉𝙖𝙢𝙚: {f_name}\n"
        text += f"📀 𝙦𝙪𝙖𝙡𝙞𝙩𝙮: {quality}\n"
        text += f"🌍 𝙡𝙖𝙣𝙜𝙪𝙖𝙜𝙚: {lang}\n"
        text += f"📦 [{f_size}]\n\n"
    return text

def format_card_result(file, current_index, total_count):
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

def get_pagination_row(current_offset, limit, total_count, unique_id):
    buttons = []
    current_page = int(current_offset / limit) + 1
    total_pages = math.ceil(total_count / limit)

    if total_pages == 1:
        return []

    if current_offset >= limit:
        buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"next_{unique_id}_{current_offset - limit}"))

    buttons.append(InlineKeyboardButton(f"📑 {current_page}/{total_pages}", callback_data="pages"))

    if current_offset + limit < total_count:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"next_{unique_id}_{current_offset + limit}"))

    return buttons

# ✅ FIX: Added safety check and correct argument handling
def btn_parser(files, chat_id, unique_id, query=None, offset=0, limit=10):
    # Safety: If query is passed as int (misplaced offset), reset it
    if isinstance(query, int): query = None

    current_files = files[offset : offset + limit]
    buttons = []
    
    for file in current_files:
        f_name = file.get('file_name', 'Unknown File')
        f_size = get_size(file.get('file_size', 0))
        link_id = file.get('link_id')
        f_chat_id = chat_id
        
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
            url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{f_chat_id}"
            buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    # Pagination
    pagination = get_pagination_row(offset, limit, len(files), unique_id)
    if pagination:
        buttons.append(pagination)
            
    return buttons

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
    except:
        return None 
