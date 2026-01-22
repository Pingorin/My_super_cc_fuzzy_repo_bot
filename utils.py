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

# ✅ CONSTANTS
LANGUAGES = ["English", "Hindi", "Tamil", "Telugu", "Malayalam", "Kannada", "Bengali", "Punjabi", "Marathi", "Gujarati", "Urdu"]
QUALITIES = ["4k", "2160p", "1080p", "720p", "480p", "360p", "HD", "SD", "CAM", "DVD"]
# Year Regex: Matches 19xx or 20xx (e.g., 1999, 2023)
YEAR_REGEX = r"(?P<year>(19|20)\d{2})"

class temp(object):
    U_NAME = None
    B_NAME = None
    B_LINK = None
    ME = None

# ==============================================================================
# 1. FILTER FUNCTIONS
# ==============================================================================

def filter_by_type(files, f_type):
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
    if not lang or lang.lower() == "none" or lang.lower() == "all":
        return files
    
    filtered = []
    for f in files:
        fname = f.get('file_name', '').lower()
        if lang.lower() in fname:
            filtered.append(f)
    return filtered

def filter_by_quality(files, quality):
    if not quality or quality.lower() == "none" or quality.lower() == "all":
        return files
    
    filtered = []
    q_clean = re.escape(quality.lower())
    for f in files:
        fname = f.get('file_name', '').lower()
        if re.search(rf"\b{q_clean}\b", fname) or quality.lower() in fname:
            filtered.append(f)
    return filtered

def filter_by_year(files, year):
    if not year or year.lower() == "none" or year.lower() == "all":
        return files
    
    filtered = []
    for f in files:
        fname = f.get('file_name', '')
        # Check if specific year exists in filename
        if str(year) in fname:
            filtered.append(f)
    return filtered

# ==============================================================================
# 2. BUTTON GENERATORS
# ==============================================================================

def get_filter_buttons(search_id, active_filter=None, active_lang=None, active_qual=None, active_year=None):
    """
    Generates Main Filter Menu.
    Row 1: Type (Video/Docs)
    Row 2: Language | Quality
    Row 3: Year
    Row 4: Reset
    """
    buttons = []
    
    # Safe Defaults
    c_type = active_filter if active_filter else "none"
    c_lang = active_lang if active_lang else "none"
    c_qual = active_qual if active_qual else "none"
    c_year = active_year if active_year else "none"

    # ROW 1: Type
    row1 = []
    if active_filter == "video":
        row1.append(InlineKeyboardButton("Videos ✅", callback_data="ignore"))
        row1.append(InlineKeyboardButton("All Files", callback_data=f"filter_{search_id}_none_{c_lang}_{c_qual}_{c_year}_0"))
    elif active_filter == "document":
        row1.append(InlineKeyboardButton("Docs ✅", callback_data="ignore"))
        row1.append(InlineKeyboardButton("All Files", callback_data=f"filter_{search_id}_none_{c_lang}_{c_qual}_{c_year}_0"))
    else:
        row1.append(InlineKeyboardButton("Videos", callback_data=f"filter_{search_id}_video_{c_lang}_{c_qual}_{c_year}_0"))
        row1.append(InlineKeyboardButton("Docs", callback_data=f"filter_{search_id}_document_{c_lang}_{c_qual}_{c_year}_0"))
    buttons.append(row1)

    # ROW 2: Language | Quality
    row2 = []
    
    # Language
    if active_lang and active_lang != "none":
        row2.append(InlineKeyboardButton(f"{active_lang} ✅", callback_data=f"lang_menu_{search_id}_{c_type}_{c_qual}_{c_year}"))
    else:
        row2.append(InlineKeyboardButton("Select Language 🌐", callback_data=f"lang_menu_{search_id}_{c_type}_{c_qual}_{c_year}"))
        
    # Quality
    if active_qual and active_qual != "none":
        row2.append(InlineKeyboardButton(f"{active_qual} ✅", callback_data=f"qual_menu_{search_id}_{c_type}_{c_lang}_{c_year}"))
    else:
        row2.append(InlineKeyboardButton("Select Quality 📀", callback_data=f"qual_menu_{search_id}_{c_type}_{c_lang}_{c_year}"))
    buttons.append(row2)

    # ROW 3: Year (New)
    row3 = []
    if active_year and active_year != "none":
        row3.append(InlineKeyboardButton(f"{active_year} ✅", callback_data=f"year_menu_{search_id}_{c_type}_{c_lang}_{c_qual}"))
    else:
        row3.append(InlineKeyboardButton("Select Year 🗓", callback_data=f"year_menu_{search_id}_{c_type}_{c_lang}_{c_qual}"))
    buttons.append(row3)

    # ROW 4: Resets
    row4 = []
    if active_lang != "none" or active_qual != "none" or active_year != "none":
        # Global Reset
        row4.append(InlineKeyboardButton("Reset All Filters 🔄", callback_data=f"filter_{search_id}_{c_type}_none_none_none_0"))
    
    if row4: buttons.append(row4)
        
    return buttons

# --- SUB MENUS ---

def get_language_buttons(search_id, files, c_type="none", c_qual="none", c_year="none"):
    buttons = []
    row = []
    
    stats = {lang: 0 for lang in LANGUAGES}
    for f in files:
        fname = f.get('file_name', '').lower()
        for lang in LANGUAGES:
            if lang.lower() in fname: stats[lang] += 1
                
    for lang, count in stats.items():
        if count > 0:
            # Callback: filter_lang_{id}_{lang}_{type}_{qual}_{year}_{offset}
            row.append(InlineKeyboardButton(f"{lang} ({count})", callback_data=f"filter_lang_{search_id}_{lang}_{c_type}_{c_qual}_{c_year}_0"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    
    buttons.append([InlineKeyboardButton("Back", callback_data=f"filter_{search_id}_{c_type}_none_{c_qual}_{c_year}_0")])
    return buttons

def get_quality_buttons(search_id, files, c_type="none", c_lang="none", c_year="none"):
    buttons = []
    row = []
    
    stats = {qual: 0 for qual in QUALITIES}
    for f in files:
        fname = f.get('file_name', '').lower()
        for qual in QUALITIES:
            if re.search(rf"\b{re.escape(qual.lower())}\b", fname) or qual.lower() in fname:
                stats[qual] += 1
                
    for qual, count in stats.items():
        if count > 0:
            row.append(InlineKeyboardButton(f"{qual} ({count})", callback_data=f"filter_qual_{search_id}_{qual}_{c_type}_{c_lang}_{c_year}_0"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    
    buttons.append([InlineKeyboardButton("Back", callback_data=f"filter_{search_id}_{c_type}_{c_lang}_none_{c_year}_0")])
    return buttons

def get_year_buttons(search_id, files, c_type="none", c_lang="none", c_qual="none"):
    buttons = []
    row = []
    
    # Extract years dynamically from current files
    years_found = {}
    
    for f in files:
        fname = f.get('file_name', '')
        # Regex search for 4 digit years starting with 19 or 20
        match = re.search(YEAR_REGEX, fname)
        if match:
            y = match.group('year')
            years_found[y] = years_found.get(y, 0) + 1

    # Sort years descending (2025, 2024, ...)
    sorted_years = sorted(years_found.items(), key=lambda x: x[0], reverse=True)

    for year, count in sorted_years:
        row.append(InlineKeyboardButton(f"{year} ({count})", callback_data=f"filter_year_{search_id}_{year}_{c_type}_{c_lang}_{c_qual}_0"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    
    buttons.append([InlineKeyboardButton("Back", callback_data=f"filter_{search_id}_{c_type}_{c_lang}_{c_qual}_none_0")])
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
        f"⚡ **Results for {query}**\nFound {len(files)} files.\n\n"
    )
    for file in files:
        f_name = file['file_name']
        f_size = get_size(file['file_size'])
        link_id = file['link_id']
        f_chat_id = chat_id
        
        link = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{f_chat_id}"
        
        # Extract Quality
        q_match = re.search(r"\b(1080p|720p|480p|360p|2160p|4k|HDRip|WEBRip|BluRay|DVDRip|CAM)\b", f_name, re.IGNORECASE)
        quality = q_match.group(0) if q_match else "N/A"
        
        # Extract Language
        l_matches = re.findall(r"\b(Hindi|Eng|English|Tam|Tamil|Tel|Telugu|Mal|Malayalam|Kan|Kannada|Ben|Bengali|Pun|Punjabi|Mar|Marathi)\b", f_name, re.IGNORECASE)
        if l_matches:
            lang = ", ".join(sorted(set([l.capitalize() for l in l_matches])))
        else:
            lang = "N/A"
            
        # Extract Year
        y_match = re.search(YEAR_REGEX, f_name)
        year = y_match.group('year') if y_match else "N/A"

        text += f"📂 <a href='{link}'>Click to get this file 📥</a>\n"
        text += f"🖥 Name: {f_name}\n"
        text += f"📀 Quality: {quality} | 🗓 Year: {year}\n"
        text += f"🌍 Language: {lang}\n"
        text += f"📦 Size: [{f_size}]\n\n"
    return text

def format_card_result(file, current_index, total_count):
    f_name = file['file_name']
    f_size = get_size(file['file_size'])
    return f"🎬 **{f_name}**\n💾 Size: {f_size}\n\nFile {current_index + 1} of {total_count}"

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

def get_pagination_row(search_id, current_offset, limit, total_count, active_filter=None, active_lang=None, active_qual=None, active_year=None):
    buttons = []
    current_page = int(current_offset / limit) + 1
    total_pages = math.ceil(total_count / limit)

    if total_pages <= 1:
        return []

    c_type = active_filter if active_filter else "none"
    c_lang = active_lang if active_lang else "none"
    c_qual = active_qual if active_qual else "none"
    c_year = active_year if active_year else "none"

    # Master Callback: filter_{id}_{type}_{lang}_{qual}_{year}_{offset}
    cb_prefix = f"filter_{search_id}_{c_type}_{c_lang}_{c_qual}_{c_year}"

    if current_offset >= limit:
        buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"{cb_prefix}_{current_offset - limit}"))

    buttons.append(InlineKeyboardButton(f"📑 {current_page}/{total_pages}", callback_data="pages"))

    if current_offset + limit < total_count:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"{cb_prefix}_{current_offset + limit}"))

    return buttons

def btn_parser(files, chat_id, search_id, offset=0, limit=10, query=None, active_filter=None, active_lang=None, active_qual=None, active_year=None):
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
    pagination = get_pagination_row(search_id, offset, limit, len(files), active_filter, active_lang, active_qual, active_year)
    if pagination:
        buttons.append(pagination)
            
    return buttons

# ==============================================================================
# 5. OTHER HELPERS
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
