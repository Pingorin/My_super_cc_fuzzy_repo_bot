import aiohttp
import time
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from utils import btn_parser, temp

# ✅ CONFIG (Add TMDB_API_KEY to your info.py for better limits)
try:
    from info import TMDB_API_KEY
except ImportError:
    # Public Test Key (Use your own if this hits limits)
    TMDB_API_KEY = "b2866c1b35bc5156a64d603a11977755" 

logger = logging.getLogger(__name__)

# ✅ IN-MEMORY CACHE (RAM Optimized)
# Structure: {'last_updated': timestamp, 'data': [list_of_30_items]}
TRENDING_CACHE = {
    'last_updated': 0,
    'data': []
}

CACHE_DURATION = 3600 # 1 Hour

async def get_trending_data():
    """
    Fetches trending movies/series from TMDB.
    Uses cached data if available and fresh (< 1 hour).
    Fetches Page 1 & 2 to ensure 30 items.
    """
    global TRENDING_CACHE
    
    current_time = time.time()
    
    # 1. Check Cache
    if TRENDING_CACHE['data'] and (current_time - TRENDING_CACHE['last_updated'] < CACHE_DURATION):
        return TRENDING_CACHE['data']

    # 2. Fetch New Data
    url = "https://api.themoviedb.org/3/trending/all/week"
    params = {'api_key': TMDB_API_KEY, 'language': 'en-US'}
    
    async with aiohttp.ClientSession() as session:
        items = []
        try:
            # Fetch Page 1
            async with session.get(url, params={**params, 'page': 1}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items.extend(data.get('results', []))

            # Fetch Page 2 (To ensure we have 30 items)
            async with session.get(url, params={**params, 'page': 2}) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items.extend(data.get('results', []))
            
            # 3. Parse & Clean Data
            parsed_list = []
            for item in items:
                try:
                    # Handle Movie vs TV
                    media_type = item.get('media_type')
                    if media_type == 'movie':
                        title = item.get('title')
                        date = item.get('release_date', '')
                    elif media_type == 'tv':
                        title = item.get('name')
                        date = item.get('first_air_date', '')
                    else:
                        continue 

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
# 🎮 TRENDING MENU HANDLER
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^trend_list#"))
async def trending_menu_handler(client, query):
    try:
        page = int(query.data.split("#")[1])
    except: page = 0
    
    # Fetch Data
    trending_data = await get_trending_data()
    
    if not trending_data:
        return await query.answer("❌ Could not fetch trending data. Try again later.", show_alert=True)

    ITEMS_PER_PAGE = 10
    total_items = len(trending_data)
    total_pages = (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    
    # Slicing
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_items = trending_data[start:end]
    
    # Build Text
    text = (
        f"🔥 **Today's Trending Movies (Top {total_items})** 🔥\n"
        f"Page {page + 1}/{total_pages}\n\n"
        f"👇 _Click any title to search!_"
    )
    
    buttons = []
    
    # Content Buttons
    for i, item in enumerate(current_items):
        rank = start + i + 1
        btn_text = f"{rank}. {item['title']} ({item['year']})"
        # Callback triggers the search handler below
        buttons.append([InlineKeyboardButton(btn_text, callback_data=f"search#{item['title']}")])
        
    # Navigation Buttons
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Back", callback_data=f"trend_list#{page-1}"))
    
    nav_row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="ignore"))
    
    if end < total_items:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"trend_list#{page+1}"))
        
    buttons.append(nav_row)
    
    # Go Back (Deletes the menu to return to chat)
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
    
    try:
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Trending UI Error: {e}")


# ==============================================================================
# 🔎 SEARCH HANDLER (Simulate Search from Trending List)
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
    # We use limit=10 (Page 1) directly. Pagination inside this view is complex, 
    # so we just show the top results for quick access.
    
    buttons = btn_parser(files, chat_id, movie_name, offset=0, limit=10, query=movie_name)
    
    # 3. Add "Back to Trending" Footer
    buttons.append([InlineKeyboardButton("🔙 Back to Trending List", callback_data="trend_list#0")])
    
    text = f"👻 **Results for:** `{movie_name}`\nfound {len(files)} files."
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
