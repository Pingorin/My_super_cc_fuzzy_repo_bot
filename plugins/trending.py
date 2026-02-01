import aiohttp
import time
import logging
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from utils import btn_parser

# ✅ CONFIG
try:
    from info import TMDB_API_KEY
except ImportError:
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "9e1353ccc623e71f80262309cda5cdfb")

logger = logging.getLogger(__name__)

# ✅ CACHE SETTINGS
TRENDING_CACHE = {'last_updated': 0, 'data': []}
CACHE_DURATION = 3600 

async def get_trending_data():
    """
    Fetches ONLY Indian Movies (Hindi, Tamil, Telugu, etc.) released after 2025.
    Filters out Hollywood/International movies using 'with_origin_country'.
    """
    global TRENDING_CACHE
    current_time = time.time()
    
    # 1. Check Cache
    if CACHE_DURATION > 0 and TRENDING_CACHE['data'] and (current_time - TRENDING_CACHE['last_updated'] < CACHE_DURATION):
        return TRENDING_CACHE['data']

    # 2. Fetch Data (Discover API)
    url = "https://api.themoviedb.org/3/discover/movie"
    
    # ✅ STRICT INDIAN CONTENT FILTER
    params = {
        'api_key': TMDB_API_KEY,
        'sort_by': 'popularity.desc',
        'primary_release_date.gte': '2025-01-01', # 2025+ Movies
        'with_origin_country': 'IN',   # 🛑 CRITICAL: Sirf India me bani movies dikhayega (No Hollywood)
        'language': 'en-US'            # Titles English me rahenge
    }
    
    async with aiohttp.ClientSession() as session:
        items = []
        try:
            # Fetch Page 1 & 2 (Total 30+ items)
            for page in range(1, 3):
                params['page'] = page
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items.extend(data.get('results', []))
            
            # 3. Parsing
            parsed_list = []
            for item in items:
                try:
                    title = item.get('title')
                    date = item.get('release_date', '')
                    year = date.split('-')[0] if date else "N/A"
                    if title:
                        parsed_list.append({'title': title, 'year': year})
                except: continue

            # Top 30 Movies
            final_list = parsed_list[:30]
            
            # Update Cache
            TRENDING_CACHE = {'last_updated': current_time, 'data': final_list}
            return final_list

        except Exception as e:
            logger.error(f"TMDB Error: {e}")
            return []

# ==============================================================================
# 🎮 BUTTON HANDLERS
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^trend_list#"))
async def trending_menu_handler(client, query):
    try:
        page = int(query.data.split("#")[1])
    except: page = 0
    
    data = await get_trending_data()
    
    if not data:
        return await query.answer("List empty or API Error!", show_alert=True)

    LIMIT = 10
    total_items = len(data)
    total_pages = (total_items + LIMIT - 1) // LIMIT
    
    start = page * LIMIT
    end = start + LIMIT
    current_items = data[start:end]
    
    text = f"🔥 **Upcoming Indian Movies (2025-26)** 🔥\nPage {page + 1}/{total_pages}\n\n👇 _Click any title to search!_"
    
    buttons = []
    for i, item in enumerate(current_items):
        rank = start + i + 1
        buttons.append([InlineKeyboardButton(f"{rank}. {item['title']} ({item['year']})", callback_data=f"search#{item['title']}")])
        
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"trend_list#{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="ignore"))
    if end < total_items:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"trend_list#{page+1}"))
        
    buttons.append(nav)
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^search#"))
async def search_from_trending(client, query):
    movie_name = query.data.split("#")[1]
    files = await Media.get_search_results(movie_name)
    
    if not files:
        # Agar exact match nahi mila to database me search buttons dikhao
        return await query.answer(f"Checking files for: {movie_name}...", show_alert=False)
        # Note: Aap yahan apna purana logic bhi use kar sakte hain
    
    buttons = btn_parser(files, query.message.chat.id, movie_name, offset=0, limit=10, query=movie_name)
    buttons.append([InlineKeyboardButton("🔙 Back to Trending", callback_data="trend_list#0")])
    await query.message.edit_text(f"🎬 Results for: **{movie_name}**", reply_markup=InlineKeyboardMarkup(buttons))
