import aiohttp
import time
import logging
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from utils import btn_parser

# ✅ CONFIG: Import API Key
try:
    from info import TMDB_API_KEY
except ImportError:
    # Fallback/Test Key
    TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "9e1353ccc623e71f80262309cda5cdfb")

logger = logging.getLogger(__name__)

# ✅ IN-MEMORY CACHE
# Structure: {'last_updated': timestamp, 'data': [list_of_30_items]}
TRENDING_CACHE = {
    'last_updated': 0,
    'data': []
}

# ⏳ CACHE DURATION (1 Hour)
CACHE_DURATION = 3600 

async def get_trending_data():
    """
    Fetches Upcoming Indian Movies (2025+) using TMDB Discover API.
    Filters: Region IN, Release Date >= 2025-01-01.
    Includes ALL Indian languages (Hindi, Tamil, Telugu, etc.)
    """
    global TRENDING_CACHE
    
    current_time = time.time()
    
    # 1. Check Cache
    if TRENDING_CACHE['data'] and (current_time - TRENDING_CACHE['last_updated'] < CACHE_DURATION):
        return TRENDING_CACHE['data']

    # 2. Fetch New Data (Discover Endpoint)
    url = "https://api.themoviedb.org/3/discover/movie"
    
    # ✅ UPDATED PARAMETERS (All India Content)
    params = {
        'api_key': TMDB_API_KEY,
        'region': 'IN',                      # Focus on India
        'sort_by': 'popularity.desc',        # Most hyped first
        'primary_release_date.gte': '2025-01-01', # 🛑 CRITICAL: Only movies after Jan 1, 2025
        # 'with_original_language': 'hi',    # ❌ REMOVED: Now it shows South Indian movies too
        'language': 'en-US'                  # Ensure titles are in English
    }
    
    async with aiohttp.ClientSession() as session:
        items = []
        try:
            # Fetch Page 1 & 2 to ensure 30 items
            for page in range(1, 3):
                params['page'] = page
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        items.extend(data.get('results', []))
            
            # 3. Parse & Clean Data
            parsed_list = []
            for item in items:
                try:
                    title = item.get('title')
                    date = item.get('release_date', '')

                    # Extract Year
                    year = date.split('-')[0] if date else "N/A"
                    
                    if title:
                        parsed_list.append({'title': title, 'year': year})
                except: continue

            # Limit to Top 30
            final_list = parsed_list[:30]
            
            # Update Cache
            TRENDING_CACHE = {
                'last_updated': current_time,
                'data': final_list
            }
            return final_list

        except Exception as e:
            logger.error(f"TMDB Fetch Error: {e}")
            return []

# ==============================================================================
# 🎮 TRENDING MENU HANDLER (Pagination)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^trend_list#"))
async def trending_menu_handler(client, query):
    try:
        # Parse page number
        page = int(query.data.split("#")[1])
    except: 
        page = 0
    
    # Fetch Data
    trending_data = await get_trending_data()
    
    if not trending_data:
        return await query.answer("❌ Could not fetch trending data. Try again later.", show_alert=True)

    ITEMS_PER_PAGE = 10
    total_items = len(trending_data)
    
    # Calculate Total Pages
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    # Slice List for Current Page
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_items = trending_data[start:end]
    
    # Build Message Text
    text = (
        f"🔥 **Upcoming Trending Movies (2025-26)** 🔥\n"
        f"Page {page + 1}/{total_pages}\n\n"
        f"👇 _Click any title to search!_"
    )
    
    buttons = []
    
    # 1. Content Buttons
    for i, item in enumerate(current_items):
        rank = start + i + 1
        btn_text = f"{rank}. {item['title']} ({item['year']})"
        # Callback triggers the search handler
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"search#{item['title']}")])
        
    # 2. Navigation Buttons
    nav_row = []
    
    # Back Button
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Back", callback_data=f"trend_list#{page-1}"))
    
    # Page Indicator (Center)
    nav_row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="ignore"))
    
    # Next Button
    if end < total_items:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"trend_list#{page+1}"))
        
    if nav_row:
        buttons.append(nav_row)
    
    # 3. Close Button
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
    
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Trending UI Error: {e}")


# ==============================================================================
# 🔎 SEARCH HANDLER (Triggers from Trending List)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^search#"))
async def search_from_trending(client, query):
    movie_name = query.data.split("#")[1]
    chat_id = query.message.chat.id
    
    # 1. Search Database
    files = await Media.get_search_results(movie_name)
    
    if not files:
        return await query.answer(f"😕 No files found for: {movie_name}", show_alert=True)
    
    # 2. Generate Result Buttons
    buttons = btn_parser(files, chat_id, movie_name, offset=0, limit=10, query=movie_name)
    
    # 3. Add "Back to Trending" Footer
    buttons.append([InlineKeyboardButton("🔙 Back to Trending List", callback_data="trend_list#0")])
    
    text = f"⚡ **Results for:** `{movie_name}`\nfound {len(files)} files."
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
