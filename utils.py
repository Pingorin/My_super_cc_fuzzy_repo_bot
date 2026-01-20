import logging
import math
import aiohttp
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

# ✅ Defined Languages
LANGUAGES = ["English", "Hindi", "Tamil", "Telugu", "Malayalam", "Kannada", "Bengali", "Punjabi", "Marathi", "Gujarati", "Urdu"]

class temp(object):
    U_NAME = None
    B_NAME = None
    B_LINK = None
    ME = None

# ==============================================================================
# 1. FILTER FUNCTIONS
# ==============================================================================

def filter_by_type(files, f_type):
    """Filters files by Video or Document. Returns all if f_type is None/All."""
    if not f_type or f_type.lower() == "none" or f_type.lower() == "all":
        return files
    
    filtered = []
    for f in files:
        db_type = f.get('file_type', 'document').lower()
        if f_type.lower() == "video" and db_type == "video":
            filtered.append(f)
        elif f_type.lower() == "document" and db_type == "document":
            filtered.append(f)
    return filtered

def filter_by_lang(files, lang):
    """Filters files by Language string in filename. Returns all if lang is None/All."""
    if not lang or lang.lower() == "none" or lang.lower() == "all":
        return files
    
    filtered = []
    for f in files:
        fname = f.get('file_name', '').lower()
        if lang.lower() in fname:
            filtered.append(f)
    return filtered

# ==============================================================================
# 2. BUTTON GENERATORS (CUMULATIVE LOGIC)
# ==============================================================================

def get_filter_buttons(search_id, active_filter=None, active_lang=None):
    """
    Generates buttons. Crucially, passes 'active_lang' to Type buttons
    and 'active_filter' to Language buttons to preserve state.
    """
    buttons = []
    
    # Safe Defaults for callback string (avoid 'None')
    curr_type = active_filter if active_filter else "none"
    curr_lang = active_lang if active_lang else "none"

    # Row 1: Type Filters
    row1 = []
    if active_filter == "video":
        row1.append(InlineKeyboardButton("Videos ✅", callback_data="ignore"))
        # Unfilter Type (set to none), but KEEP curr_lang
        row1.append(InlineKeyboardButton("All Files", callback_data=f"filter_{search_id}_none_{curr_lang}_0"))
    elif active_filter == "document":
        row1.append(InlineKeyboardButton("Docs ✅", callback_data="ignore"))
        # Unfilter Type (set to none), but KEEP curr_lang
        row1.append(InlineKeyboardButton("All Files", callback_data=f"filter_{search_id}_none_{curr_lang}_0"))
    else:
        # Select Type, KEEP curr_lang
        row1.append(InlineKeyboardButton("Videos", callback_data=f"filter_{search_id}_video_{curr_lang}_0"))
        row1.append(InlineKeyboardButton("Docs", callback_data=f"filter_{search_id}_document_{curr_lang}_0"))
    buttons.append(row1)

    # Row 2: Language Filter
    row2 = []
    if active_lang and active_lang != "none":
        # Opens menu but remembers type so back button works
        row2.append(InlineKeyboardButton(f"{active_lang} ✅", callback_data=f"lang_menu_{search_id}_{curr_type}"))
        # Unfilter Lang (set to none), but KEEP curr_type
        row2.append(InlineKeyboardButton("All Languages", callback_data=f"filter_{search_id}_{curr_type}_none_0"))
    else:
        # Opens menu but remembers type
        row2.append(InlineKeyboardButton("Select Language 🌐", callback_data=f"lang_menu_{search_id}_{curr_type}"))
    buttons.append(row2)
        
    return buttons

def get_language_buttons(search_id, files, active_filter=None):
    """
    Generates the grid of languages. 
    'active_filter' is passed so when a language is picked, we don't lose the Type.
    """
    buttons = []
    row = []
    
    curr_type = active_filter if active_filter else "none"

    # Calculate Counts based on the files passed (which should already be type-filtered)
    stats = {lang: 0 for lang in LANGUAGES}
    for file in files:
        fname = file.get('file_name', '').lower()
        for lang in LANGUAGES:
            if lang.lower() in fname:
                stats[lang] += 1
                
    for lang, count in stats.items():
        if count > 0:
            # CALLBACK FORMAT: filter_lang_{id}_{lang}_{type}_{offset}
            # This ensures Type is preserved when Language is selected
            row.append(InlineKeyboardButton(f"{lang} ({count})", callback_data=f"filter_lang_{search_id}_{lang}_{curr_type}_0"))
        
        if len(row) == 2:
            buttons.append(row)
            row = []
            
    if row:
        buttons.append(row)
        
    # Navigation
    buttons.append([
        InlineKeyboardButton("All Languages", callback_data=f"filter_{search_id}_{curr_type}_none_0"),
        InlineKeyboardButton("Back", callback_data=f"filter_{search_id}_{curr_type}_none_0")
    ])
    
    return buttons

# ==============================================================================
# 3. FORMATTING & PAGINATION
# ==============================================================================

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
except Exception as e:
    logger.warning(f"Telegraph library not found: {e}")
    telegraph_client = None

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
        if l_matches:
            lang = ", ".join(sorted(set([l.capitalize() for l in l_matches])))
        else:
            lang = "N/A"

        text += f"📂 <a href='{link}'>Click to get this file 📥</a>\n"
        text += f"🖥 Name: {f_name}\n"
        text += f"📀 Quality: {quality}\n"
        text += f"🌍 Language: {lang}\n"
        text += f"📦 Size: [{f_size}]\n\n"
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

def get_pagination_row(search_id, current_offset, limit, total_count, active_filter=None, active_lang=None):
    """
    Generates pagination that remembers Active Filter and Active Lang.
    """
    buttons = []
    current_page = int(current_offset / limit) + 1
    total_pages = math.ceil(total_count / limit)

    if total_pages <= 1:
        return []

    # Safe Strings
    a_type = active_filter if active_filter else "none"
    a_lang = active_lang if active_lang else "none"

    # Use the Combined Filter Callback
    # filter_{id}_{type}_{lang}_{offset}
    cb_prefix = f"filter_{search_id}_{a_type}_{a_lang}"

    if current_offset >= limit:
        buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"{cb_prefix}_{current_offset - limit}"))

    buttons.append(InlineKeyboardButton(f"📑 {current_page}/{total_pages}", callback_data="pages"))

    if current_offset + limit < total_count:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"{cb_prefix}_{current_offset + limit}"))

    return buttons

# ✅ 5. BUTTON PARSER (Combined Logic)
def btn_parser(files, chat_id, search_id, offset=0, limit=10, query=None, active_filter=None, active_lang=None):
    current_files = files[offset : offset + limit]
    buttons = []
    
    for file in current_files:
        f_name = file.get('file_name', 'Unknown File')
        f_size = get_size(file.get('file_size', 0))
        link_id = file.get('link_id')
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
            if temp.U_NAME:
                url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}"
                buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    # Pagination must receive the active states
    pagination = get_pagination_row(search_id, offset, limit, len(files), active_filter, active_lang)
    if pagination:
        buttons.append(pagination)
            
    return buttons

# ==============================================================================
# 4. OTHER HELPERS
# ==============================================================================

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
    except: return None 

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
