import logging
import math
import aiohttp
from pyrogram.types import InlineKeyboardButton
from info import SHORTLINK_URL, SHORTLINK_API

logger = logging.getLogger(__name__)

class temp(object):
    U_NAME = None

def get_size(size):
    if not size: return ""
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

async def get_shortlink(link):
    url = f'https://{SHORTLINK_URL}/api'
    params = {'api': SHORTLINK_API, 'url': link}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, raise_for_status=True) as response:
                data = await response.json()
                if "shortenedUrl" in data:
                    return data["shortenedUrl"]
                else:
                    logger.error(f"Shortener Error: {data}")
                    return link
    except Exception as e:
        logger.error(f"Shortlink Exception: {e}")
        return link

# ✅ MODIFIED: Added 'chat_id' argument
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
            # ✅ NEW FORMAT: get_LINKID_CHATID
            # Hum Group ID ko link me chupakar bhej rahe hain
            url = f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}"
            buttons.append([InlineKeyboardButton(text=btn_text, url=url)])
            
    return buttons
