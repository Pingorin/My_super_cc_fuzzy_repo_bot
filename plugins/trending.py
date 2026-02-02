import aiohttp
import time
import logging
import os
import asyncio 
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from database.users_chats_db import db
# ✅ Import arrange_buttons from utils to ensure correct order
from utils import (
    btn_parser, temp, get_filter_buttons, get_pagination_row, 
    format_text_results, format_detailed_results, arrange_buttons
)

# ✅ CONFIG: Import API Key
try:
    from info import TMDB_API_KEY
except ImportError:
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "9e1353ccc623e71f80262309cda5cdfb")

logger = logging.getLogger(__name__)

# ✅ IN-MEMORY CACHE
TRENDING_CACHE = {
    'last_updated': 0,
    'data': []
}

CACHE_DURATION = 3600 

async def get_trending_data():
    """Fetches CURRENT TRENDING content (Movies + Web Series)."""
    global TRENDING_CACHE
    
    current_time = time.time()
    
    if TRENDING_CACHE['data'] and (current_time - TRENDING_CACHE['last_updated'] < CACHE_DURATION):
        return TRENDING_CACHE['data']

    url = "https://api.themoviedb.org/3/trending/all/week"
    params = {'api_key': TMDB_API_KEY, 'region': 'IN', 'language': 'en-US'}
    
    async with aiohttp.ClientSession() as session:
        items = []
        try:
            for page in range(1, 3):
                params['page'] = page
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items.extend(data.get('results', []))

            parsed_list = []
            for item in items:
                try:
                    if 'name' in item:
                        title = item['name']
                        date = item.get('first_air_date', '')
                    else:
                        title = item.get('title')
                        date = item.get('release_date', '')

                    year = date.split('-')[0] if date else "N/A"
                    if title:
                        parsed_list.append({'title': title, 'year': year})
                except: continue

            final_list = parsed_list[:30]
            TRENDING_CACHE = {'last_updated': current_time, 'data': final_list}
            return final_list

        except Exception as e:
            logger.error(f"TMDB Fetch Error: {e}")
            return []

# ==============================================================================
# 🎮 TRENDING MENU HANDLER
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^trend_list#"))
async def trending_menu_handler(client, query):
    try:
        data = query.data.split("#")
        page = int(data[1])
        prev_search_id = int(data[2]) if len(data) > 2 else 0
    except: 
        page = 0
        prev_search_id = 0
    
    trending_data = await get_trending_data()
    
    if not trending_data:
        return await query.answer("❌ Could not fetch trending data.", show_alert=True)

    ITEMS_PER_PAGE = 10
    total_items = len(trending_data)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_items = trending_data[start:end]
    
    text = (
        f"🔥 **Trending Movies & Series** 🔥\n"
        f"Page {page + 1}/{total_pages}\n\n"
        f"👇 _Click any title to search!_"
    )
    
    buttons = []
    for i, item in enumerate(current_items):
        rank = start + i + 1
        btn_text = f"{rank}. {item['title']} ({item['year']})"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"search#{item['title']}")])
        
    nav_row = []
    if page > 0: 
        nav_row.append(InlineKeyboardButton("⬅️ Back", callback_data=f"trend_list#{page-1}#{prev_search_id}"))
    
    nav_row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="ignore"))
    
    if end < total_items: 
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"trend_list#{page+1}#{prev_search_id}"))
        
    if nav_row: buttons.append(nav_row)
    
    if prev_search_id != 0:
        buttons.append([InlineKeyboardButton("⬅️ Go Back to Search Results", callback_data=f"back_search#{prev_search_id}")])
    else:
        buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
    
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Trending UI Error: {e}")

# ==============================================================================
# 🔙 BACK TO SEARCH HANDLER
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^back_search#"))
async def back_to_search_handler(client, query):
    search_id = int(query.data.split("#")[1])
    cached_data = await Media.get_search_query(search_id)
    if not cached_data:
        return await query.answer("⚠️ Previous search expired. Please search again.", show_alert=True)
    original_query = cached_data.get('query')
    await search_from_trending(client, query, forced_query=original_query)


# ==============================================================================
# 🔎 SEARCH HANDLER (AUTO DETECT MODE & SHOW FILTERS)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^search#"))
async def search_from_trending(client, query, forced_query=None):
    if forced_query:
        movie_name = forced_query
    else:
        movie_name = query.data.split("#")[1]
        
    chat_id = query.message.chat.id
    user_id = query.from_user.id

    task_files = Media.get_search_results(movie_name, sort="relevance")
    task_settings = db.get_group_settings(chat_id)
    
    files, group_settings = await asyncio.gather(task_files, task_settings)

    if not files:
        return await query.answer(f"😕 No files found for: {movie_name}", show_alert=True)

    search_id = await Media.save_search_query(movie_name, user_id, files)
    if not search_id: search_id = 0

    mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
    limit = group_settings.get('result_page_limit', 10) if group_settings else 10
    
    if mode == 'hybrid':
        mode = 'button' if len(files) <= limit else 'text'

    howto_url = group_settings.get('howto_url')
    howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
    
    free_prem_btn = [
        InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{chat_id}"),
        InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
    ]
    
    filter_buttons = get_filter_buttons(search_id, files, active_sort="relevance")

    # ------------------------------------------------------------------
    # ✅ FIX: Button Order Logic
    # ------------------------------------------------------------------
    if mode == 'button':
        buttons = btn_parser(files, chat_id, search_id, 0, limit, movie_name)
        
        # 🔥 USE arrange_buttons FUNCTION (Ensures correct order)
        # 1. Files
        # 2. Filters
        # 3. How To
        # 4. Send All / Free Premium
        # 5. Trending Button (Added inside arrange_buttons)
        # 6. Pagination (Moved to bottom by arrange_buttons)
        
        buttons = arrange_buttons(buttons, files, limit, filter_buttons, howto_btn, free_prem_btn, search_id)
        
        msg_text = f"⚡ **Results for:** `{movie_name}`\nfound {len(files)} files."
        await query.message.edit_text(text=msg_text, reply_markup=InlineKeyboardMarkup(buttons))

    elif mode in ['text', 'detailed']:
        page_files = files[:limit]
        
        if mode == 'text': text = format_text_results(page_files, movie_name, chat_id)
        else: text = format_detailed_results(page_files, movie_name, chat_id)
        
        btn = []
        if filter_buttons: 
            for row in filter_buttons: btn.append(row)
        if howto_btn: btn.append(howto_btn)
        
        # 1. Add Send All / Premium
        btn.append(free_prem_btn)
        
        # 2. Add Trending Button (Explicitly added here for Text Mode)
        #    Format: trend_list#0#{search_id}
        btn.append([InlineKeyboardButton("🔥 Today Popular Movies", callback_data=f"trend_list#0#{search_id}")])
        
        # 3. Add Pagination (Last)
        pagination = get_pagination_row(search_id, 0, limit, len(files), active_sort="relevance")
        if pagination: btn.append(pagination)
        
        await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))
    
    else:
        buttons = btn_parser(files, chat_id, search_id, 0, limit, movie_name)
        buttons.append([InlineKeyboardButton("🔥 Today Popular Movies", callback_data=f"trend_list#0#{search_id}")])
        await query.message.edit_text(f"⚡ **Results for:** `{movie_name}`", reply_markup=InlineKeyboardMarkup(buttons))
