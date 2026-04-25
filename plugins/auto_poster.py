import asyncio
import aiohttp
import logging
import json
import info
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils import temp

logger = logging.getLogger(__name__)

POSTED_MEMORY = [] 

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

async def post_trending_poster(client, custom_channel_id=None, group_chat_id=None):
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
    
    TARGET_CHANNEL = custom_channel_id if custom_channel_id else info.UPDATES_CHANNEL
    
    if not TARGET_CHANNEL:
        print("❌ [Auto-Poster] Koi Target Channel set nahi hai!")
        return

    buttons = []
    buttons.append([InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{bot_username}?start=")])

    if group_chat_id:
        from database.users_chats_db import db
        settings = await db.get_group_settings(group_chat_id)
        mu_settings = settings.get('movie_update', {})
        
        if mu_settings.get('group_link'):
            buttons.append([InlineKeyboardButton("👥 Group", url=mu_settings['group_link'])])
            
        footer_btns = mu_settings.get('footer', [])
        if footer_btns:
            f_row = [InlineKeyboardButton(btn['text'], url=btn['url']) for btn in footer_btns]
            buttons.append(f_row)

    try:
        if poster_token:
            api_url = f"https://api.telegram.org/bot{poster_token}/sendPhoto"
            raw_inline_keyboard = []
            for row in buttons:
                raw_row = [{"text": btn.text, "url": btn.url} for btn in row]
                raw_inline_keyboard.append(raw_row)

            payload = {
                "chat_id": TARGET_CHANNEL,
                "photo": poster_url,
                "caption": caption_html,
                "parse_mode": "HTML",
                "reply_markup": json.dumps({"inline_keyboard": raw_inline_keyboard})
            }
            async with aiohttp.ClientSession() as session:
                await session.post(api_url, json=payload)
            print(f"🚀 [Auto-Poster] Secondary Bot se channel {TARGET_CHANNEL} me post bhej diya!")
        else:
            caption_md = caption_html.replace("<b>", "**").replace("</b>", "**")
            await client.send_photo(
                chat_id=TARGET_CHANNEL, 
                photo=poster_url, 
                caption=caption_md, 
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            print(f"🚀 [Auto-Poster] Main Bot se channel {TARGET_CHANNEL} me post bhej diya!")
            
        if media_id not in POSTED_MEMORY: POSTED_MEMORY.append(media_id)
        else:
            POSTED_MEMORY.remove(media_id)
            POSTED_MEMORY.append(media_id)

        if len(POSTED_MEMORY) > 50: POSTED_MEMORY.pop(0)
        print(f"🎉 [Auto-Poster] SUCCESS! '{title}' channel me post ho gaya.")
        
    except Exception as e:
        print(f"❌ [Auto-Poster] Channel me bhejne me ERROR aaya: {e}")

@Client.on_message(filters.command("testpost") & filters.user(info.ADMINS))
async def force_test_post(client, message):
    m = await message.reply("⏳ TMDB se movie data nikal raha hoon, Terminal logs check karo...")
    try:
        await post_trending_poster(client)
        await m.edit("✅ **Post Command Run!** Agar channel me poster nahi aaya, toh Terminal / Console me error padho.")
    except Exception as e:
        await m.edit(f"❌ **Error:**\n`{e}`")

@Client.on_message(filters.command("post") & filters.user(info.ADMINS))
async def manual_post_movie(client, message):
    if len(message.command) < 2:
        return await message.reply("⚠️ **Sahi syntax:** `/post Movie Name`\nJaise: `/post Pushpa`")
        
    query = message.text.split(" ", 1)[1]
    wait_msg = await message.reply(f"⏳ '{query}' dhoondh raha hoon...")
    
    search_url = f"https://api.themoviedb.org/3/search/multi?api_key={info.TMDB_API_KEY}&query={query}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(search_url) as resp:
            data = await resp.json()
            results = data.get("results", [])
            
            if not results:
                return await wait_msg.edit("❌ TMDB par aisi koi movie ya series nahi mili.")
                
            media = next((m for m in results if m.get("media_type") in ["movie", "tv"]), None)
            
            if not media:
                return await wait_msg.edit("❌ TMDB par aisi koi valid movie nahi mili.")
                
            media_id = str(media['id'])
            media_type = media.get('media_type', 'movie')
            
            detail_url = f"https://api.themoviedb.org/3/tv/{media_id}?api_key={info.TMDB_API_KEY}" if media_type == 'tv' else f"https://api.themoviedb.org/3/movie/{media_id}?api_key={info.TMDB_API_KEY}"
            
            async with session.get(detail_url) as detail_resp:
                details = await detail_resp.json()
                
    title = details.get("title") or details.get("name", "Unknown")
    year = (details.get("release_date") or details.get("first_air_date", ""))[:4]
    rating = round(details.get("vote_average", 0.0), 1)
    genres = ", ".join([g["name"] for g in details.get("genres", [])])
    poster_path = details.get("poster_path")
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://graph.org/file/4d61886e61dfa37a25945.jpg"

    type_tag = "#WEB_SERIES" if media_type == 'tv' else "#MOVIE"
    header_tag = "🚨 <b>New Added</b>"

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
    TARGET_CHANNEL = getattr(info, 'UPDATES_CHANNEL', None)

    if not TARGET_CHANNEL:
        return await wait_msg.edit("❌ **Error:** info.py me UPDATES_CHANNEL set nahi hai.")

    try:
        if poster_token:
            api_url = f"https://api.telegram.org/bot{poster_token}/sendPhoto"
            payload = {
                "chat_id": TARGET_CHANNEL,
                "photo": poster_url,
                "caption": caption_html,
                "parse_mode": "HTML",
                "reply_markup": json.dumps({
                    "inline_keyboard": [[{"text": "📥 Download Now", "url": f"https://t.me/{bot_username}?start="}]]
                })
            }
            async with aiohttp.ClientSession() as session:
                await session.post(api_url, json=payload)
        else:
            caption_md = caption_html.replace("<b>", "**").replace("</b>", "**")
            buttons = [[InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{bot_username}?start=")]]
            await client.send_photo(chat_id=TARGET_CHANNEL, photo=poster_url, caption=caption_md, reply_markup=InlineKeyboardMarkup(buttons))
            
        await wait_msg.edit(f"✅ **SUCCESS:** '{title}' ka poster channel me bhej diya gaya hai!")
    except Exception as e:
        await wait_msg.edit(f"❌ **ERROR:** Channel me post karne me dikkat aayi:\n`{e}`")

# ==============================================================================
# ⏱️ BACKGROUND LOOP (UPDATED FOR SLOTS)
# ==============================================================================
async def start_auto_poster(client):
    await asyncio.sleep(60) 
    while True:
        print("⏳ [Auto-Poster] Starting global background posting cycle...")
        
        # 1. Sabse pehle info.py wale main UPDATES_CHANNEL me post karega
        try:
            await post_trending_poster(client)
        except Exception as e:
            print(f"❌ Main Channel Post Error: {e}")

        # 2. Ab Database se saare groups check karega aur unke Slots me post karega
        try:
            from database.users_chats_db import db
            async for group in db.groups.find({}):
                chat_id = group.get('id')
                mu = group.get('movie_update', {})
                
                if mu.get('is_active'):
                    slots = mu.get('slots', {})
                    active_channels = [ch for ch in slots.values() if ch is not None]
                    
                    for channel in active_channels:
                        await asyncio.sleep(3) 
                        try:
                            await post_trending_poster(client, custom_channel_id=channel, group_chat_id=chat_id)
                        except Exception as e:
                            print(f"❌ Slot Post Error for {channel}: {e}")
        except Exception as e:
            print(f"❌ Database Slot Fetch Error: {e}")

        print("✅ [Auto-Poster] Global cycle complete! Waiting for next round...")
        await asyncio.sleep(60) # 12 hours
