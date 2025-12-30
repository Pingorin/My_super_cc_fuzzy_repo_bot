import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from database.ia_filterdb import Media
from utils import btn_parser # Re-using your existing button parser for search results

# 🎬 STATIC LIST OF TRENDING MOVIES (You can update this manually or fetch from API)
TRENDING_MOVIES = [
    "Dhurandhar (2025)", "Pushpa 2: The Rule", "Kalki 2898 AD", "Salaar", 
    "Animal", "Fighter", "Dunki", "Tiger 3", "Jawan", "Gadar 2",
    "Leo", "Jailer", "Pathaan", "KGF Chapter 2", "RRR", "Brahmastra",
    "Drishyam 2", "Vikram", "Kantara", "Ponniyin Selvan", "Sita Ramam",
    "Avengers: Secret Wars", "Deadpool 3", "Avatar 3", "Spider-Man: Beyond the Spider-Verse",
    "Oppenheimer", "Barbie", "Mission Impossible 7", "John Wick 4", "Fast X"
]

# ==============================================================================
# ⏳ BACKGROUND SCHEDULER
# ==============================================================================

async def auto_mention_scheduler(client):
    while True:
        try:
            # Check every 60 seconds
            await asyncio.sleep(60)
            
            # Iterate through all groups in DB (Optimized query can be used for production)
            async for group in db.groups.find({"automention_enabled": True}):
                chat_id = group['id']
                interval = group.get('mention_interval', 300)
                last_time = group.get('last_mention_time', 0)
                pending = group.get('pending_mentions', [])
                
                # Check Time & Queue
                if pending and (time.time() - last_time) >= interval:
                    # Take top 5 users
                    users_to_mention = pending[:5]
                    
                    mentions = []
                    for uid in users_to_mention:
                        try:
                            # Try to get user info (might be cached)
                            user = await client.get_chat_member(chat_id, uid)
                            mentions.append(user.user.mention)
                        except:
                            # If user left or error, use a generic fallback or skip
                            pass
                    
                    if mentions:
                        text = (
                            f"Hey {', '.join(mentions)}\n\n"
                            f"Looking for the latest movies and series? Just type the name in the group to get instant download links!"
                        )
                        
                        btn = [[InlineKeyboardButton("🔥 Today Popular Movies", callback_data="trend_list#0")]]
                        
                        try:
                            await client.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(btn))
                            # Cleanup DB
                            await db.remove_pending_mentions(chat_id, users_to_mention)
                        except Exception as e:
                            print(f"AutoMention Send Error: {e}")
                            # If send fails (perm issue), clear the list to avoid stuck loop
                            await db.remove_pending_mentions(chat_id, users_to_mention)
                    else:
                        # Clean up invalid IDs
                        await db.remove_pending_mentions(chat_id, users_to_mention)

        except Exception as e:
            print(f"Scheduler Error: {e}")

# Start the task when bot starts (Add this line in your Bot.py or __init__.py)
# asyncio.create_task(auto_mention_scheduler(app))


# ==============================================================================
# 🔥 TRENDING MOVIES UI
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^trend_list#"))
async def trending_movies_page(client, query):
    page = int(query.data.split("#")[1])
    ITEMS_PER_PAGE = 10
    total_movies = len(TRENDING_MOVIES)
    
    # Slice List
    start = page * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    current_list = TRENDING_MOVIES[start:end]
    
    text = (
        f"🔥 **Today's Trending Movies (Top {total_movies})** 🔥\n\n"
        f"Page {page + 1}/{int(total_movies/ITEMS_PER_PAGE)}\n\n"
        f"👇 _Click any title to search!_"
    )
    
    buttons = []
    # Create Buttons for Movies
    for i, movie in enumerate(current_list):
        rank = start + i + 1
        # Triggers a specific search callback
        buttons.append([InlineKeyboardButton(f"{rank}. {movie}", callback_data=f"quick_search#{movie}")])
    
    # Navigation
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"trend_list#{page-1}"))
    if end < total_movies:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"trend_list#{page+1}"))
        
    if nav: buttons.append(nav)
    
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ==============================================================================
# 🔎 QUICK SEARCH HANDLER (When clicking a movie button)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^quick_search#"))
async def quick_search_handler(client, query):
    movie_name = query.data.split("#")[1]
    chat_id = query.message.chat.id
    
    # Trigger your existing AutoFilter Search Logic
    # We simulate a search by calling Media.get_search_results
    
    files = await Media.get_search_results(movie_name)
    
    if not files:
        return await query.answer("😕 No files found for this movie.", show_alert=True)
    
    # Use your existing button parser from utils.py
    # This ensures consistency with your bot's style
    buttons = btn_parser(files, chat_id, movie_name, offset=0, limit=10)
    
    text = f"👻 **Results for:** `{movie_name}`\n\n👇 Click below to download:"
    
    # We send a NEW message with results so the list doesn't disappear
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()
