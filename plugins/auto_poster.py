import asyncio
import aiohttp
import logging
import json
import info
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from utils import temp

logger = logging.getLogger(__name__)

# ==============================================================================
# 🕵️ SMART ENGINE (Web Series + Movies + Mega-Hit Repeat + Kachra Filter)
# ==============================================================================

async def get_fresh_or_mega_trending(posted_ids):
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={info.TMDB_API_KEY}"
    
    # Kachra Filter (10766=Soap, 10764=Reality, 10767=Talk Shows)
    BANNED_TV_GENRES = [10766, 10764, 10767]
    
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
                            return None, False
                            
                        top_media = valid_media[0] 
                        top_id = str(top_media["id"])
                        
                        # Mega-Hit Logic
                        if top_media.get("popularity", 0) > 800 and top_id not in posted_ids[-3:]:
                            return top_media, True 
                        
                        # Fresh Logic
                        fresh_media = [m for m in valid_media if str(m["id"]) not in posted_ids]
                        if fresh_media:
                            import random
                            return random.choice(fresh_media), False
                            
        except Exception as e:
            logger.error(f"TMDB Fetch Error: {e}")
            
    return None, False

async def post_trending_poster(client):
    posted_data = await db.bot_settings.find_one({"_id": "posted_movies"})
    posted_ids = posted_data.get("ids", []) if posted_data else []

    media, is_mega_hit = await get_fresh_or_mega_trending(posted_ids)
    if not media: return

    media_id = str(media['id'])
    media_type = media.get('media_type', 'movie')
    
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
    header_tag = "🔥 <b>STILL TRENDING</b>" if is_mega_hit else "🚨 <b>New Added</b>"

    caption_html = (
        f"{header_tag} {type_tag}\n\n"
        f"✨ <b>TITLE :</b> {title} ({year})\n"
        f"━─────━✨━─────━\n\n"
        f"🎭 <b>GENRES :</b> {genres if genres else 'Drama, Action'}\n"
        f"📺 <b>OTT :</b> N/A\n"
        f"🎞️ <b>QUALITY :</b> HD 1080p\n"
        f"🎧 <b>AUDIO :</b> Hindi\n"
        f"🔥 <b>RATING :</b> {rating}/10\n\n"
        f"━─────━✨━─────━"
    )

    bot_username = temp.U_NAME if hasattr(temp, 'U_NAME') and temp.U_NAME else "Search_Bot"
    poster_token = getattr(info, 'POSTER_BOT_TOKEN', None)
    
    try:
        if poster_token: # Dusre bot se bhejna (Raw API)
            api_url = f"https://api.telegram.org/bot{poster_token}/sendPhoto"
            payload = {
                "chat_id": info.UPDATES_CHANNEL,
                "photo": poster_url,
                "caption": caption_html,
                "parse_mode": "HTML",
                "reply_markup": json.dumps({
                    "inline_keyboard": [[{"text": "📥 Download Now", "url": f"https://t.me/{bot_username}?start="}]]
                })
            }
            async with aiohttp.ClientSession() as session:
                await session.post(api_url, json=payload)
        else: # Main bot se bhejna
            caption_md = caption_html.replace("<b>", "**").replace("</b>", "**")
            buttons = [[InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{bot_username}?start=")]]
            await client.send_photo(chat_id=info.UPDATES_CHANNEL, photo=poster_url, caption=caption_md, reply_markup=InlineKeyboardMarkup(buttons))
            
        # DB Update
        if media_id not in posted_ids: posted_ids.append(media_id)
        else:
            posted_ids.remove(media_id)
            posted_ids.append(media_id)

        if len(posted_ids) > 50: posted_ids.pop(0)
        await db.bot_settings.update_one({"_id": "posted_movies"}, {"$set": {"ids": posted_ids}}, upsert=True)
        
    except Exception as e:
        logger.error(f"❌ Auto-post failed: {e}")

# ==============================================================================
# ⏱️ BACKGROUND LOOP (Timer)
# ==============================================================================
async def start_auto_poster(client):
    await asyncio.sleep(60) # Bot start hone ke 1 min baad shuru hoga
    while True:
        await post_trending_poster(client)
        await asyncio.sleep(60) # Har 12 Ghante mein post karega (Change to 86400 for 24 hours)
