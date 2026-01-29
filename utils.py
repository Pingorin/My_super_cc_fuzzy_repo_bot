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
QUALITIES = ["Bluray", "4k", "2160p", "1080p", "720p", "480p", "360p", "HD", "SD", "CAM", "DVD"]

# ✅ REGEX
LANG_REGEX = {
    "English": re.compile(r"\b(english|eng)\b", re.IGNORECASE),
    "Hindi": re.compile(r"\b(hindi|hin)\b", re.IGNORECASE),
    "Tamil": re.compile(r"\b(tamil|tam)\b", re.IGNORECASE),
    "Telugu": re.compile(r"\b(telugu|tel)\b", re.IGNORECASE),
    "Malayalam": re.compile(r"\b(malayalam|mal)\b", re.IGNORECASE),
    "Kannada": re.compile(r"\b(kannada|kan)\b", re.IGNORECASE),
    "Bengali": re.compile(r"\b(bengali|ben)\b", re.IGNORECASE),
    "Punjabi": re.compile(r"\b(punjabi|pun)\b", re.IGNORECASE),
    "Marathi": re.compile(r"\b(marathi|mar)\b", re.IGNORECASE),
    "Gujarati": re.compile(r"\b(gujarati|guj)\b", re.IGNORECASE),
    "Urdu": re.compile(r"\b(urdu)\b", re.IGNORECASE)
}

QUALITY_REGEX = {
    "Bluray": re.compile(r"\b(bluray|blu-ray|bdrip)\b", re.IGNORECASE),
    "4k": re.compile(r"\b(4k|ultra\s?hd|uhd)\b", re.IGNORECASE),
    "2160p": re.compile(r"\b2160p\b", re.IGNORECASE),
    "1080p": re.compile(r"\b1080p\b", re.IGNORECASE),
    "720p": re.compile(r"\b720p\b", re.IGNORECASE),
    "480p": re.compile(r"\b480p\b", re.IGNORECASE),
    "360p": re.compile(r"\b360p\b", re.IGNORECASE),
    "HD": re.compile(r"\b(hd|hdtv|hdrip|hq)\b", re.IGNORECASE),
    "SD": re.compile(r"\b(sd|sdqv)\b", re.IGNORECASE),
    "CAM": re.compile(r"\b(cam|camrip|hdcam)\b", re.IGNORECASE),
    "DVD": re.compile(r"\b(dvd|dvdrip)\b", re.IGNORECASE)
}

YEAR_REGEX = re.compile(r"\b(?:19|20)\d{2}\b")

class temp(object):
    U_NAME = None
    B_NAME = None
    B_LINK = None
    ME = None

# ==============================================================================
# 1. FILTER FUNCTIONS
# ==============================================================================

def filter_by_type(files, f_type):
    if not f_type or f_type.lower() == "none" or f_type.lower() == "all": return files
    filtered = []
    target_type = f_type.lower()
    for f in files:
        db_type = f.get('file_type', 'document').lower()
        if target_type == "video" and db_type == "video": filtered.append(f)
        elif target_type == "document" and db_type == "document": filtered.append(f)
    return filtered

def filter_by_lang(files, lang):
    if not lang or lang.lower() == "none" or lang.lower() == "all": return files
    filtered = []
    regex = LANG_REGEX.get(lang)
    for f in files:
        text = (f.get('file_name', '') + " " + (f.get('caption') or "")).lower()
        if regex:
            if regex.search(text): filtered.append(f)
        elif lang.lower() in text: filtered.append(f)
    return filtered

def filter_by_quality(files, quality):
    if not quality or quality.lower() == "none" or quality.lower() == "all": return files
    filtered = []
    regex = QUALITY_REGEX.get(quality)
    for f in files:
        fname = f.get('file_name', '')
        if regex:
            if regex.search(fname): filtered.append(f)
        elif quality.lower() in fname.lower(): filtered.append(f)
    return filtered

def filter_by_year(files, year):
    if not year or year.lower() == "none" or year.lower() == "all": return files
    filtered = []
    target_year = str(year)
    for f in files:
        fname = f.get('file_name', '')
        if target_year in fname: filtered.append(f)
    return filtered

def filter_by_size(files, size_range):
    if not size_range or size_range.lower() == "none" or size_range.lower() == "all": return files
    filtered = []
    MB_500 = 500 * 1024 * 1024
    GB_1 = 1024 * 1024 * 1024
    GB_2 = 2 * 1024 * 1024 * 1024
    for f in files:
        size = f.get('file_size', 0)
        if size_range == "min500": 
            if size < MB_500: filtered.append(f)
        elif size_range == "500-1gb": 
            if MB_500 <= size < GB_1: filtered.append(f)
        elif size_range == "1gb-2gb": 
            if GB_1 <= size < GB_2: filtered.append(f)
        elif size_range == "max2gb": 
            if size >= GB_2: filtered.append(f)
    return filtered

# ==============================================================================
# 2. BUTTON GENERATORS
# ==============================================================================

def get_filter_buttons(search_id, files, active_filter=None, active_lang=None, active_qual=None, active_year=None, active_size=None, active_sort=None):
    # Scan logic for available filters
    has_video = False
    has_docs = False
    has_lang_data = False
    has_qual_data = False
    has_year_data = False
    
    for f in files:
        fname = f.get('file_name', '')
        caption = f.get('caption') or ""
        full_text = f"{fname} {caption}"
        ftype = f.get('file_type', 'document')
        
        if ftype == 'video': has_video = True
        elif ftype == 'document': has_docs = True
        
        if not has_lang_data:
            for lang, regex in LANG_REGEX.items():
                if regex.search(full_text):
                    has_lang_data = True
                    break
        if not has_qual_data:
            for qual, regex in QUALITY_REGEX.items():
                if regex.search(fname):
                    has_qual_data = True
                    break
        if not has_year_data:
            if YEAR_REGEX.search(fname):
                has_year_data = True

    # -----------------------------------------------------------
    
    buttons = []
    
    curr_type = active_filter if active_filter else "none"
    curr_lang = active_lang if active_lang else "none"
    curr_qual = active_qual if active_qual else "none"
    curr_year = active_year if active_year else "none"
    curr_size = active_size if active_size else "none"
    curr_sort = active_sort if active_sort else "relevance"

    # ROW 1: Type
    row1 = []
    if has_video:
        if active_filter == "video":
            row1.append(InlineKeyboardButton("Videos ✅", callback_data="ignore"))
        else:
            row1.append(InlineKeyboardButton("Videos", callback_data=f"filter_{search_id}_video_{curr_lang}_{curr_qual}_{curr_year}_{curr_size}_{curr_sort}_0"))
            
    if has_docs:
        if active_filter == "document":
            row1.append(InlineKeyboardButton("Docs ✅", callback_data="ignore"))
        else:
            row1.append(InlineKeyboardButton("Docs", callback_data=f"filter_{search_id}_document_{curr_lang}_{curr_qual}_{curr_year}_{curr_size}_{curr_sort}_0"))
    
    if active_filter not in [None, "none"]:
         row1.append(InlineKeyboardButton("All Files", callback_data=f"filter_{search_id}_none_{curr_lang}_{curr_qual}_{curr_year}_{curr_size}_{curr_sort}_0"))

    if row1: buttons.append(row1)

    # ROW 2: Language | Quality
    row2 = []
    if has_lang_data or (active_lang and active_lang != "none"):
        btn_text = f"Lang: {active_lang} ✅" if active_lang and active_lang != "none" else "Select Language 🌐"
        row2.append(InlineKeyboardButton(btn_text, callback_data=f"lang_menu_{search_id}_{curr_type}_{curr_qual}_{curr_year}_{curr_size}_{curr_sort}_{curr_lang}"))

    if has_qual_data or (active_qual and active_qual != "none"):
        btn_text = f"Qual: {active_qual} ✅" if active_qual and active_qual != "none" else "Select Quality 📀"
        row2.append(InlineKeyboardButton(btn_text, callback_data=f"qual_menu_{search_id}_{curr_type}_{curr_lang}_{curr_year}_{curr_size}_{curr_sort}_{curr_qual}"))
    
    if row2: buttons.append(row2)

    # ROW 3: YEAR | SIZE
    row3 = []
    if has_year_data or (active_year and active_year != "none"):
        btn_text = f"Year: {active_year} ✅" if active_year and active_year != "none" else "Select Year 🗓"
        row3.append(InlineKeyboardButton(btn_text, callback_data=f"year_menu_{search_id}_{curr_type}_{curr_lang}_{curr_qual}_{curr_size}_{curr_sort}_{curr_year}"))
    
    size_label = "Select Size 📦"
    if active_size == "min500": size_label = "<500MB ✅"
    elif active_size == "500-1gb": size_label = "0.5-1GB ✅"
    elif active_size == "1gb-2gb": size_label = "1-2GB ✅"
    elif active_size == "max2gb": size_label = ">2GB ✅"
    row3.append(InlineKeyboardButton(size_label, callback_data=f"size_menu_{search_id}_{curr_type}_{curr_lang}_{curr_qual}_{curr_year}_{curr_sort}_{curr_size}"))
    
    if row3: buttons.append(row3)

    # ✅ ROW 4: SORT BY FILES
    row4 = []
    sort_label = "Sort By Files 📂"
    if active_sort == "new": sort_label = "Sort: Newest ✅"
    elif active_sort == "old": sort_label = "Sort: Oldest ✅"
    elif active_sort == "large": sort_label = "Sort: Large First ✅"
    elif active_sort == "small": sort_label = "Sort: Small First ✅"
    
    row4.append(InlineKeyboardButton(sort_label, callback_data=f"sort_menu_{search_id}_{curr_type}_{curr_lang}_{curr_qual}_{curr_year}_{curr_size}_{curr_sort}"))
    buttons.append(row4)

    # ROW 5: RESET SPECIFIC FILTERS
    row5 = []
    if active_lang and active_lang != "none":
        row5.append(InlineKeyboardButton("All Langs", callback_data=f"filter_{search_id}_{curr_type}_none_{curr_qual}_{curr_year}_{curr_size}_{curr_sort}_0"))
    if active_qual and active_qual != "none":
        row5.append(InlineKeyboardButton("All Quals", callback_data=f"filter_{search_id}_{curr_type}_{curr_lang}_none_{curr_year}_{curr_size}_{curr_sort}_0"))
    if active_year and active_year != "none":
        row5.append(InlineKeyboardButton("All Years", callback_data=f"filter_{search_id}_{curr_type}_{curr_lang}_{curr_qual}_none_{curr_size}_{curr_sort}_0"))
    if active_size and active_size != "none":
        row5.append(InlineKeyboardButton("All Sizes", callback_data=f"filter_{search_id}_{curr_type}_{curr_lang}_{curr_qual}_{curr_year}_none_{curr_sort}_0"))
    
    if row5:
        if len(row5) > 2:
            buttons.append(row5[:2])
            buttons.append(row5[2:])
        else:
            buttons.append(row5)
        
    return buttons

# ✅ NEW: SORT BUTTONS GENERATOR
def get_sort_buttons(search_id, active_type, active_lang, active_qual, active_year, active_size, active_sort):
    buttons = []
    
    options = [
        ("Relevance", "relevance"),
        ("Newest First", "new"),
        ("Oldest First", "old"),
        ("Size (High-Low)", "large"),
        ("Size (Low-High)", "small")
    ]
    
    for label, key in options:
        btn_text = label
        if key == active_sort or (key == "relevance" and not active_sort):
            btn_text += " ✅"
            
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"filter_sort_{search_id}_{key}_{active_type}_{active_lang}_{active_qual}_{active_year}_{active_size}_0")])
        
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_{search_id}_{active_type}_{active_lang}_{active_qual}_{active_year}_{active_size}_{active_sort}_0")])
    return buttons

def get_language_buttons(search_id, files, active_type=None, active_qual=None, active_year=None, active_size=None, active_lang=None, active_sort=None):
    buttons = []
    row = []
    c_type = active_type if active_type else "none"
    c_qual = active_qual if active_qual else "none"
    c_year = active_year if active_year else "none"
    c_size = active_size if active_size else "none"
    c_sort = active_sort if active_sort else "relevance"
    back_lang_state = active_lang if active_lang else "none"

    stats = {lang: 0 for lang in LANGUAGES}
    for file in files:
        text = (file.get('file_name', '') + " " + (file.get('caption') or "")).lower()
        for lang, regex in LANG_REGEX.items():
            if regex.search(text):
                stats[lang] += 1
                
    for lang, count in stats.items():
        if count > 0:
            btn_txt = f"{lang} ({count})"
            if lang == active_lang: btn_txt += " ✅"
            row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_lang_{search_id}_{lang}_{c_type}_{c_qual}_{c_year}_{c_size}_{c_sort}_0"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_{search_id}_{c_type}_{back_lang_state}_{c_qual}_{c_year}_{c_size}_{c_sort}_0")])
    return buttons

def get_quality_buttons(search_id, files, active_type=None, active_lang=None, active_year=None, active_size=None, active_qual=None, active_sort=None):
    buttons = []
    row = []
    c_type = active_type if active_type else "none"
    c_lang = active_lang if active_lang else "none"
    c_year = active_year if active_year else "none"
    c_size = active_size if active_size else "none"
    c_sort = active_sort if active_sort else "relevance"
    back_qual_state = active_qual if active_qual else "none"

    stats = {qual: 0 for qual in QUALITIES}
    for file in files:
        fname = file.get('file_name', '')
        for qual, regex in QUALITY_REGEX.items():
            if regex.search(fname):
                stats[qual] += 1
                
    for qual, count in stats.items():
        if count > 0:
            btn_txt = f"{qual} ({count})"
            if qual == active_qual: btn_txt += " ✅"
            row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_qual_{search_id}_{qual}_{c_type}_{c_lang}_{c_year}_{c_size}_{c_sort}_0"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_{search_id}_{c_type}_{c_lang}_{back_qual_state}_{c_year}_{c_size}_{c_sort}_0")])
    return buttons

def get_year_buttons(search_id, files, active_type=None, active_lang=None, active_qual=None, active_size=None, active_year=None, active_sort=None):
    buttons = []
    row = []
    c_type = active_type if active_type else "none"
    c_lang = active_lang if active_lang else "none"
    c_qual = active_qual if active_qual else "none"
    c_size = active_size if active_size else "none"
    c_sort = active_sort if active_sort else "relevance"
    back_year_state = active_year if active_year else "none"

    years = set()
    for file in files:
        fname = file.get('file_name', '')
        matches = YEAR_REGEX.findall(fname)
        for year in matches:
            years.add(year)

    sorted_years = sorted(list(years), reverse=True)
    for year in sorted_years:
        btn_txt = f"{year}"
        if str(year) == str(active_year): btn_txt += " ✅"
        
        row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_year_{search_id}_{year}_{c_type}_{c_lang}_{c_qual}_{c_size}_{c_sort}_0"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row: buttons.append(row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_{search_id}_{c_type}_{c_lang}_{c_qual}_{back_year_state}_{c_size}_{c_sort}_0")])
    return buttons

def get_size_buttons(search_id, active_type=None, active_lang=None, active_qual=None, active_year=None, active_size=None, active_sort=None):
    c_type = active_type if active_type else "none"
    c_lang = active_lang if active_lang else "none"
    c_qual = active_qual if active_qual else "none"
    c_year = active_year if active_year else "none"
    c_sort = active_sort if active_sort else "relevance"
    back_size_state = active_size if active_size else "none"

    ranges = [
        ("<500MB", "min500"),
        ("500MB - 1GB", "500-1gb"),
        ("1GB - 2GB", "1gb-2gb"),
        (">2GB", "max2gb")
    ]

    buttons = []
    for text, key in ranges:
        btn_txt = text
        if key == active_size: btn_txt += " ✅"
        
        buttons.append([InlineKeyboardButton(btn_txt, callback_data=f"filter_size_{search_id}_{key}_{c_type}_{c_lang}_{c_qual}_{c_year}_{c_sort}_0")])
            
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_{search_id}_{c_type}_{c_lang}_{c_qual}_{c_year}_{back_size_state}_{c_sort}_0")])
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
        
        caption = file.get('caption', '')
        if query.lower() not in f_name.lower() and query.lower() in caption.lower():
             clean_cap = caption.replace("<b>", "").replace("</b>", "")[:50] + "..."
             f_name = clean_cap

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
        
        caption = file.get('caption') or ""
        if query.lower() not in f_name.lower() and query.lower() in caption.lower():
             clean_cap = caption.replace("<b>", "").replace("</b>", "")[:50] + "..."
        
        link = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{f_chat_id}"
        
        q_match = re.search(r"\b(1080p|720p|480p|360p|2160p|4k|HDRip|WEBRip|BluRay|DVDRip|CAM)\b", f_name, re.IGNORECASE)
        quality = q_match.group(0) if q_match else "N/A"
        
        langs_found = []
        text_to_check = (f_name + " " + caption).lower()
        for lang, regex in LANG_REGEX.items():
            if regex.search(text_to_check):
                langs_found.append(lang)
        
        lang_str = ", ".join(sorted(set(langs_found))) if langs_found else "N/A"

        text += f"📂 <a href='{link}'>Click to get this file 📥</a>\n"
        text += f"🖥 Name: {f_name}\n"
        text += f"📀 Quality: {quality}\n"
        text += f"🌍 Language: {lang_str}\n"
        text += f"📦 Size: [{f_size}]\n\n"
        
        if len(text) > 3800:
            text += "<b>⚠️ Results truncated due to limit.</b>"
            break
            
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

def get_pagination_row(search_id, current_offset, limit, total_count, active_filter=None, active_lang=None, active_qual=None, active_year=None, active_size=None, active_sort=None):
    buttons = []
    current_page = int(current_offset / limit) + 1
    total_pages = math.ceil(total_count / limit)
    if total_pages <= 1: return []
    
    a_type = active_filter if active_filter else "none"
    a_lang = active_lang if active_lang else "none"
    a_qual = active_qual if active_qual else "none"
    a_year = active_year if active_year else "none"
    a_size = active_size if active_size else "none"
    a_sort = active_sort if active_sort else "relevance"
    
    cb_prefix = f"filter_{search_id}_{a_type}_{a_lang}_{a_qual}_{a_year}_{a_size}_{a_sort}"
    
    if current_offset >= limit:
        buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"{cb_prefix}_{current_offset - limit}"))
    buttons.append(InlineKeyboardButton(f"📑 {current_page}/{total_pages}", callback_data="pages"))
    if current_offset + limit < total_count:
        buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"{cb_prefix}_{current_offset + limit}"))
    return buttons

def btn_parser(files, chat_id, search_id, offset=0, limit=10, query=None, active_filter=None, active_lang=None, active_qual=None, active_year=None, active_size=None):
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
            if q not in f_name.lower() and q in caption.lower():
                display_name = caption.replace("<b>", "").replace("</b>", "")[:57] + "..."
        
        btn_text = f"📂 {display_name} [{f_size}]"
        if link_id is not None:
            if temp.U_NAME:
                url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}"
                buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    pagination = get_pagination_row(search_id, offset, limit, len(files), active_filter, active_lang, active_qual, active_year, active_size)
    if pagination: buttons.append(pagination)
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
