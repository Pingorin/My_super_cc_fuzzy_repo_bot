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

# ✅ 1. TEXT FORMATTERS (Added Helpers for Result Modes)
def get_size(size):
    if not size: return "0 B"
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

def format_text_results(files, query):
    text = f"👻 **Results for:** `{query}`\n\n"
    for i, file in enumerate(files, 1):
        f_name = file['file_name']
        f_size = get_size(file['file_size'])
        link_id = file['link_id']
        chat_id = file.get('chat_id')
        cmd_link = f"/get_{link_id}" 
        text += f"{i}. 📂 [{f_name}](https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}) [{f_size}]\n\n"
    return text

def format_detailed_results(files, query):
    text = f"👻 **Detailed Results for:** `{query}`\n\n"
    for file in files:
        f_name = file['file_name']
        f_size = get_size(file['file_size'])
        link_id = file['link_id']
        chat_id = file.get('chat_id')
        caption = file.get('caption', 'N/A')
        if len(caption) > 50: caption = caption[:50] + "..."
        
        text += f"🎬 **Title:** `{f_name}`\n"
        text += f"💾 **Size:** `{f_size}`\n"
        text += f"📝 **Info:** {caption}\n"
        text += f"🔗 **Link:** [Get File](https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id})\n"
        text += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    return text

def format_card_result(file, current_index, total_count):
    f_name = file['file_name']
    f_size = get_size(file['file_size'])
    caption = file.get('caption', '')
    
    f_type = "Document"
    if f_name.endswith(('.mkv', '.mp4', '.avi')): f_type = "Video"
    elif f_name.endswith(('.mp3', '.flac')): f_type = "Audio"

    text = f"🎬 **{f_name}**\n\n"
    text += f"🗂️ **Type:** {f_type}\n"
    text += f"💾 **Size:** {f_size}\n"
    if len(caption) > 100: text += f"📝 **Info:** {caption[:100]}...\n"
    
    text += f"\n**File {current_index + 1} of {total_count}**"
    return text

# ✅ 2. TELEGRAPH POSTER (Site Mode Helper)
# Note: You might need to install 'telegraph' library or remove this if not using it
try:
    from telegraph import Telegraph
    telegraph_client = Telegraph()
    telegraph_client.create_account(short_name='AutoFilter')
except:
    telegraph_client = None

async def post_to_telegraph(files, query):
    if not telegraph_client: return None
    html_content = f"<h3>Search Results for: {query}</h3><br>"
    for file in files:
        f_name = file['file_name']
        f_size = get_size(file['file_size'])
        link_id = file['link_id']
        chat_id = file.get('chat_id')
        link = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}"
        html_content += f"<p>📂 <a href='{link}'>{f_name}</a> [{f_size}]</p><hr>"
    
    try:
        response = telegraph_client.create_page(title=f"Results: {query}", html_content=html_content)
        return response['url']
    except Exception as e:
        logger.error(f"Telegraph Error: {e}")
        return None

# ✅ 3. SHORTLINK GENERATOR
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

# ✅ 4. BUTTON PARSER
def btn_parser(files, chat_id, query=None):
    buttons = []
    for file in files:
        f_name = file.get('file_name', 'Unknown File')
        f_size = get_size(file.get('file_size', 0))
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
            url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}"
            buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    return buttons

# ✅ 5. FSUB STATUS LOGIC
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
