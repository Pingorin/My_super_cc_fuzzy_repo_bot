import asyncio
import aiohttp
import logging
import json
import info
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from utils import temp

logger = logging.getLogger(__name__)

# ==============================================================================
# 🕵️ SMART ENGINE (Web Series + Movies + Mega-Hit Repeat + Kachra Filter)
# ==============================================================================

async def get_fresh_or_mega_trending(posted_ids):
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={info.TMDB_API_KEY}"
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

# ==============================================================================
# 🧪 MANUAL POSTER (Used for /testpost & UI Test Button)
# ==============================================================================

async def post_trending_poster(client, custom_channel_id=None, group_chat_id=None):
    # Testing ke dauran hum DB update nahi karte, warna schedule bigad jayega
    bot_settings_col = db.db["bot_settings"]
    posted_data = await bot_settings_col.find_one({"_id": "posted_movies"})
    posted_ids = posted_data.get("ids", []) if posted_data else []

    media, is_mega_hit = await get_fresh_or_mega_trending(posted_ids)
    if not media: return False

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
    TARGET_CHANNEL = custom_channel_id if custom_channel_id else info.UPDATES_CHANNEL
    
    if not TARGET_CHANNEL: return False

    buttons = [[InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{bot_username}?start=")]]

    if group_chat_id:
        settings = await db.get_group_settings(group_chat_id)
        mu_settings = settings.get('movie_update', {})
        if mu_settings.get('group_link'):
            buttons.append([InlineKeyboardButton("👥 Group", url=mu_settings['group_link'])])
        footer_btns = mu_settings.get('footer', [])
        if footer_btns:
            buttons.append([InlineKeyboardButton(btn['text'], url=btn['url']) for btn in footer_btns])
    
    try:
        if poster_token:
            api_url = f"https://api.telegram.org/bot{poster_token}/sendPhoto"
            raw_inline_keyboard = [[{"text": btn.text, "url": btn.url} for btn in row] for row in buttons]
            payload = {
                "chat_id": TARGET_CHANNEL, "photo": poster_url, "caption": caption_html,
                "parse_mode": "HTML", "reply_markup": json.dumps({"inline_keyboard": raw_inline_keyboard})
            }
            async with aiohttp.ClientSession() as session:
                await session.post(api_url, json=payload)
        else:
            caption_md = caption_html.replace("<b>", "**").replace("</b>", "**")
            await client.send_photo(chat_id=TARGET_CHANNEL, photo=poster_url, caption=caption_md, reply_markup=InlineKeyboardMarkup(buttons))
        return True
    except Exception as e:
        print(f"❌ Test Post Error: {e}")
        raise e

# ==============================================================================
# 🎮 MANUAL COMMANDS
# ==============================================================================

@Client.on_message(filters.command("testpost") & filters.user(info.ADMINS))
async def force_test_post(client, message):
    m = await message.reply("⏳ TMDB se movie data nikal raha hoon, Terminal logs check karo...")
    try:
        await post_trending_poster(client)
        await m.edit("✅ **Test Post Run!** Check your channel.")
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
            if not results: return await wait_msg.edit("❌ Aisi koi movie/series nahi mili.")
                
            media = next((m for m in results if m.get("media_type") in ["movie", "tv"]), None)
            if not media: return await wait_msg.edit("❌ Koi valid movie nahi mili.")
                
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

    caption_html = (
        f"🚨 <b>New Added</b> {type_tag}\n\n"
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

    if not TARGET_CHANNEL: return await wait_msg.edit("❌ **Error:** info.py me UPDATES_CHANNEL nahi hai.")

    try:
        if poster_token:
            api_url = f"https://api.telegram.org/bot{poster_token}/sendPhoto"
            payload = {
                "chat_id": TARGET_CHANNEL, "photo": poster_url, "caption": caption_html, "parse_mode": "HTML",
                "reply_markup": json.dumps({"inline_keyboard": [[{"text": "📥 Download Now", "url": f"https://t.me/{bot_username}?start="}]]})
            }
            async with aiohttp.ClientSession() as session: await session.post(api_url, json=payload)
        else:
            caption_md = caption_html.replace("<b>", "**").replace("</b>", "**")
            buttons = [[InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{bot_username}?start=")]]
            await client.send_photo(chat_id=TARGET_CHANNEL, photo=poster_url, caption=caption_md, reply_markup=InlineKeyboardMarkup(buttons))
            
        await wait_msg.edit(f"✅ **SUCCESS:** '{title}' manual post done!")
    except Exception as e:
        await wait_msg.edit(f"❌ **ERROR:** `{e}`")

# ==============================================================================
# ⏱️ THE MASTER BROADCAST LOOP (ULTIMATE FIX)
# ==============================================================================

async def start_auto_poster(client):
    await asyncio.sleep(60) 
    bot_settings_col = db.db["bot_settings"]

    while True:
        print("⏳ [Auto-Poster] Starting global broadcast cycle...")
        
        try:
            # 1. DB se List ONCE fetch karo
            posted_data = await bot_settings_col.find_one({"_id": "posted_movies"})
            posted_ids = posted_data.get("ids", []) if posted_data else []

            # 2. Sirf EK movie fetch karo iss ghante ke liye
            media, is_mega_hit = await get_fresh_or_mega_trending(posted_ids)
            
            if media:
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
                caption_md = caption_html.replace("<b>", "**").replace("</b>", "**")

                # HELPER: Send Engine
                async def send_to_target(target_channel, buttons):
                    try:
                        if poster_token:
                            api_url = f"https://api.telegram.org/bot{poster_token}/sendPhoto"
                            raw_inline_keyboard = [[{"text": btn.text, "url": btn.url} for btn in row] for row in buttons]
                            payload = {
                                "chat_id": target_channel, "photo": poster_url, "caption": caption_html,
                                "parse_mode": "HTML", "reply_markup": json.dumps({"inline_keyboard": raw_inline_keyboard})
                            }
                            async with aiohttp.ClientSession() as session:
                                await session.post(api_url, json=payload)
                        else:
                            await client.send_photo(chat_id=target_channel, photo=poster_url, caption=caption_md, reply_markup=InlineKeyboardMarkup(buttons))
                        print(f"🚀 Broadcasted to {target_channel}")
                    except Exception as e:
                        print(f"❌ Broadcast Failed for {target_channel}: {e}")

                # --- PHASE 3: THE MASTER BROADCAST ---
                print(f"🎬 Broadcasting '{title}' to ALL channels...")
                
                # A. Send to info.py Channel
                if info.UPDATES_CHANNEL:
                    main_buttons = [[InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{bot_username}?start=")]]
                    await send_to_target(info.UPDATES_CHANNEL, main_buttons)

                # B. Send to All Group Slots
                async for group in db.groups.find({}):
                    mu = group.get('movie_update', {})
                    if mu.get('is_active'):
                        slots = mu.get('slots', {})
                        active_channels = [ch for ch in slots.values() if ch is not None]
                        
                        if active_channels:
                            grp_buttons = [[InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{bot_username}?start=")]]
                            if mu.get('group_link'):
                                grp_buttons.append([InlineKeyboardButton("👥 Group", url=mu['group_link'])])
                            footer_btns = mu.get('footer', [])
                            if footer_btns:
                                grp_buttons.append([InlineKeyboardButton(btn['text'], url=btn['url']) for btn in footer_btns])

                            for channel in active_channels:
                                await asyncio.sleep(2) # Safe FloodWait Delay
                                await send_to_target(channel, grp_buttons)

                # --- PHASE 4: DB UPDATE (Sirf 1 Baar) ---
                if media_id not in posted_ids: posted_ids.append(media_id)
                else:
                    posted_ids.remove(media_id)
                    posted_ids.append(media_id)
                
                if len(posted_ids) > 50: posted_ids.pop(0)
                await bot_settings_col.update_one({"_id": "posted_movies"}, {"$set": {"ids": posted_ids}}, upsert=True)
                print("✅ Global Poster cycle complete and DB safely updated!")

            else:
                print("⚠️ [Auto-Poster] No fresh movie found for this cycle.")

        except Exception as e:
            print(f"❌ Global Cycle Error: {e}")

        # Wait 1 Hour for the next broadcast
        await asyncio.sleep(3600) 
