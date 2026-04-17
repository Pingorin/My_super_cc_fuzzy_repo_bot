import asyncio
import aiohttp
import logging
import json
import info
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp

logger = logging.getLogger(__name__)

# Error se bachne ke liye Temporary Memory (DB ki jagah)
POSTED_MEMORY = [] 

# ==============================================================================
# 🕵️ SMART ENGINE
# ==============================================================================

async def get_fresh_or_mega_trending():
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={info.TMDB_API_KEY}"
    BANNED_TV_GENRES = [10766, 10764, 10767]
    
    print("⏳ [Auto-Poster] TMDB API se data nikal raha hoon...")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    
                    if results:
                        valid_media = []
                        for m in results:
                            media_type = m.get("media_type")
                            if media_type == "movie":
                                valid_media.append(m)
                            elif media_type == "tv":
                                show_genres = m.get("genre_ids", [])
                                if not any(banned_id in show_genres for banned_id in BANNED_TV_GENRES):
                                    valid_media.append(m)

                        if not valid_media:
                            print("❌ [Auto-Poster] TMDB par koi valid show nahi mila.")
                            return None, False
                            
                        top_media = valid_media[0] 
                        top_id = str(top_media["id"])
                        
                        if top_media.get("popularity", 0) > 800 and top_id not in POSTED_MEMORY[-3:]:
                            return top_media, True 
                        
                        fresh_media = [m for m in valid_media if str(m["id"]) not in POSTED_MEMORY]
                        if fresh_media:
                            import random
                            return random.choice(fresh_media), False
                            
        except Exception as e:
            print(f"❌ [Auto-Poster] TMDB Fetch Error: {e}")
            
    return None, False

async def post_trending_poster(client):
    global POSTED_MEMORY
    
    media, is_mega_hit = await get_fresh_or_mega_trending()
    if not media: 
        print("⚠️ [Auto-Poster] Aaj koi nayi movie/series nahi mili. Skip kar raha hoon.")
        return

    media_id = str(media['id'])
    media_type = media.get('media_type', 'movie')
    
    print(f"✅ [Auto-Poster] Movie mil gayi: ID {media_id}. Details nikal raha hoon...")
    
    detail_url = f"https://api.themoviedb.org/3/tv/{media_id}?api_key={info.TMDB_API_KEY}" if media_type == 'tv' else f"https://api.themoviedb.org/3/movie/{media_id}?api_key={info.TMDB_API_KEY}"

    async with aiohttp.ClientSession() as session:
        async with session.get(detail_url) as resp:
            details = await resp.json()

    title = details.get("title") or details.get("name", "Unknown")
    year = (details.get("release_date") or details.get("first_air_date", ""))[:4]
    rating = round(details.get("vote_average", 0.0), 1)
    genres = ", ".join([g["name"] for g in details.get("genres", [])])
    poster_path = details.get("poster_path")
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://graph.org/file/4d61886e61dfa37a25945.jpg"

    type_tag = "#WEB_SERIES" if media_type == 'tv' else "#MOVIE"
    header_tag = "🔥 **STILL TRENDING**" if is_mega_hit else "🚨 **New Added**"

    caption_md = (
        f"{header_tag} {type_tag}\n\n"
        f"✨ **TITLE :** {title} ({year})\n"
        f"━─────━✨━─────━\n\n"
        f"🎭 **GENRES :** {genres if genres else 'Drama, Action'}\n"
        f"📺 **OTT :** N/A\n"
        f"🎞️ **QUALITY :** HD 1080p\n"
        f"🎧 **AUDIO :** Hindi\n"
        f"🔥 **RATING :** {rating}/10\n\n"
        f"━─────━✨━─────━"
    )

    bot_username = temp.U_NAME if hasattr(temp, 'U_NAME') and temp.U_NAME else "Search_Bot"
    buttons = [[InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{bot_username}?start=")]]

    try:
        print(f"🚀 [Auto-Poster] Channel {info.UPDATES_CHANNEL} me post bhej raha hoon...")
        
        await client.send_photo(
            chat_id=info.UPDATES_CHANNEL, 
            photo=poster_url, 
            caption=caption_md, 
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
        if media_id not in POSTED_MEMORY: POSTED_MEMORY.append(media_id)
        else:
            POSTED_MEMORY.remove(media_id)
            POSTED_MEMORY.append(media_id)

        if len(POSTED_MEMORY) > 50: POSTED_MEMORY.pop(0)
        print(f"🎉 [Auto-Poster] SUCCESS! '{title}' channel me post ho gaya.")
        
    except Exception as e:
        print(f"❌ [Auto-Poster] Channel me bhejne me ERROR aaya: {e}")

# ==============================================================================
# 🎮 MANUAL TEST COMMAND (Instant Check Ke Liye)
# ==============================================================================
@Client.on_message(filters.command("testpost") & filters.user(info.ADMINS))
async def force_test_post(client, message):
    m = await message.reply("⏳ TMDB se movie data nikal raha hoon, Terminal logs check karo...")
    try:
        await post_trending_poster(client)
        await m.edit("✅ **Post Command Run!** Agar channel me poster nahi aaya, toh Terminal / Console me error padho.")
    except Exception as e:
        await m.edit(f"❌ **Error:**\n`{e}`")

# ==============================================================================
# ⏱️ BACKGROUND LOOP
# ==============================================================================
async def start_auto_poster(client):
    await asyncio.sleep(60) 
    while True:
        await post_trending_poster(client)
        await asyncio.sleep(60) # 1 Min ki testing
