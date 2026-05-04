import asyncio
import aiohttp
import logging
import json
import socket
import info
# 🔥 FIX: StopPropagation import kiya gaya hai Deep-Link ke liye
from pyrogram import Client, filters, StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.users_chats_db import db
from utils import temp

logger = logging.getLogger(__name__)

# ==============================================================================
# 🎭 REACTION CONFIGURATION (Screenshot Emojis)
# ==============================================================================
POSTER_REACTIONS = ["👍", "🔥", "❤️", "😍"]

# ==============================================================================
# 🕵️ SMART ENGINE (Web Series + Movies + Mega-Hit Repeat + Kachra Filter)
# ==============================================================================

async def get_fresh_or_mega_trending(posted_ids):
    url = f"https://api.themoviedb.org/3/trending/all/day?api_key={info.TMDB_API_KEY}"
    BANNED_TV_GENRES = [10766, 10764, 10767]
    
    timeout = aiohttp.ClientTimeout(total=30)
    # 🔥 IPv4 Force Fix
    connector = aiohttp.TCPConnector(ssl=False, family=socket.AF_INET)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
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
                        
                        if top_media.get("popularity", 0) > 800 and top_id not in posted_ids[-3:]:
                            return top_media, True 
                        
                        fresh_media = [m for m in valid_media if str(m["id"]) not in posted_ids]
                        if fresh_media:
                            import random
                            return random.choice(fresh_media), False
                            
        except Exception as e:
            logger.error(f"TMDB Fetch Error: {e}")
            
    return None, False

# ==============================================================================
# ⚡ HELPER: ADD REACTIONS TO MESSAGE
# ==============================================================================
async def add_poster_reactions(client, chat_id, message_id):
    try:
        for emoji in POSTER_REACTIONS:
            try:
                await client.send_reaction(chat_id, message_id, emoji)
                break 
            except Exception:
                continue
    except Exception as e:
        print(f"Failed to add reactions to {chat_id}: {e}")

# ==============================================================================
# 🧪 MANUAL POSTER (Used for /testpost & UI Test Button)
# ==============================================================================

async def post_trending_poster(client, custom_channel_id=None, group_chat_id=None):
    bot_settings_col = db.db["bot_settings"]
    posted_data = await bot_settings_col.find_one({"_id": "posted_movies"})
    posted_ids = posted_data.get("ids", []) if posted_data else []

    media, is_mega_hit = await get_fresh_or_mega_trending(posted_ids)
    
    if not media: 
        url = f"https://api.themoviedb.org/3/trending/all/day?api_key={info.TMDB_API_KEY}"
        connector = aiohttp.TCPConnector(ssl=False, family=socket.AF_INET)
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30), connector=connector) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        media = results[0]  
                        is_mega_hit = False
                    else:
                        raise Exception("TMDB ne khali data bheja hai!")
                else:
                    raise Exception(f"TMDB Error Code: {resp.status}")

    media_id = str(media['id'])
    media_type = media.get('media_type', 'movie')
    
    detail_url = f"https://api.themoviedb.org/3/tv/{media_id}?api_key={info.TMDB_API_KEY}" if media_type == 'tv' else f"https://api.themoviedb.org/3/movie/{media_id}?api_key={info.TMDB_API_KEY}"

    connector = aiohttp.TCPConnector(ssl=False, family=socket.AF_INET)
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30), connector=connector) as session:
        async with session.get(detail_url) as resp:
            details = await resp.json()

    title = details.get("title") or details.get("name", "Unknown")
    year = (details.get("release_date") or details.get("first_air_date", ""))[:4]
    rating = round(details.get("vote_average", 0.0), 1)
    genres = ", ".join([g["name"] for g in details.get("genres", [])])
    poster_path = details.get("poster_path")
    poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://graph.org/file/4d61886e61dfa37a25945.jpg"

    type_tag = "#WEB_SERIES" if media_type == 'tv' else "#MOVIE"
    header_tag = "🔥 STILL TRENDING" if is_mega_hit else "📥 New"

    caption_html = (
        f"{header_tag} {type_tag} Added\n\n"
        f"✨ <b>TITLE :</b> <code>{title} {year}</code>\n"
        f"───•✧•───\n\n"
        f"🎭 <b>GENRES :</b> {genres if genres else 'Drama, Action'}\n"
        f"📺 <b>OTT :</b> N/A\n"
        f"🎞 <b>QUALITY :</b> HD\n"
        f"🎧 <b>AUDIO :</b> Hindi\n"
        f"🔥 <b>RATING :</b> {rating}\n\n"
        f"───•✧•───"
    )

    second_bot = getattr(info, 'FILE_STORE_BOT', None)
    if second_bot:
        target_bot_username = second_bot.replace("@", "")
    else:
        target_bot_username = temp.U_NAME if hasattr(temp, 'U_NAME') and temp.U_NAME else "Search_Bot"

    poster_token = getattr(info, 'POSTER_BOT_TOKEN', "")
    if poster_token:
        poster_token = poster_token.strip() # 🔥 Clean Token Spaces
        
    TARGET_CHANNEL = custom_channel_id if custom_channel_id else info.UPDATES_CHANNEL
    
    if not TARGET_CHANNEL: 
        raise Exception("Info.py ya Group settings me koi Target Channel set nahi hai!")

    buttons = [[InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{target_bot_username}?start=")]]

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
                "chat_id": TARGET_CHANNEL, 
                "photo": poster_url, 
                "caption": caption_html,
                "parse_mode": "HTML", 
                "reply_markup": json.dumps({"inline_keyboard": raw_inline_keyboard})
            }
            timeout = aiohttp.ClientTimeout(total=60)
            connector = aiohttp.TCPConnector(ssl=False, family=socket.AF_INET)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                resp = await session.post(api_url, json=payload)
                if resp.status != 200:
                    err_msg = await resp.text()
                    raise Exception(f"TELEGRAM ERROR: {err_msg}")
        else:
            caption_md = caption_html.replace("<b>", "**").replace("</b>", "**")
            sent_msg = await client.send_photo(chat_id=TARGET_CHANNEL, photo=poster_url, caption=caption_md, reply_markup=InlineKeyboardMarkup(buttons))
            if sent_msg:
                asyncio.create_task(add_poster_reactions(client, TARGET_CHANNEL, sent_msg.id))
        return True
    except Exception as e:
        print(f"❌ Test Post Error: {e}")
        raise e

# ==============================================================================
# 🔗 DEEP-LINK CATCHER (Main Bot se aane wala Test Post)
# ==============================================================================
@Client.on_message(filters.command("start") & filters.private, group=-1)
async def deep_link_test_post(client, message):
    if len(message.command) > 1 and message.command[1].startswith("testpost_"):
        # Security: Sirf Admins ye test chala sakte hain
        if message.from_user.id not in info.ADMINS:
            await message.reply("❌ You are not an admin.")
            raise StopPropagation
            
        chat_id = int(message.command[1].split("_")[1])
        m = await message.reply("⏳ Command received from Main Bot! Running Test Post...")
        
        try:
            settings = await db.get_group_settings(chat_id)
            mu = settings.get('movie_update', {})
            active_channels = [ch for ch in mu.get('slots', {}).values() if ch is not None]
            
            if not active_channels:
                await m.edit("❌ No slots set! Pehle Group Settings me channel add karein.")
                raise StopPropagation
                
            success_count = 0
            error_logs = ""
            for channel in active_channels:
                try:
                    await post_trending_poster(client, custom_channel_id=channel, group_chat_id=chat_id)
                    success_count += 1
                except Exception as e:
                    error_logs += f"\n• `{channel}`: {str(e)}"
                    
            if success_count > 0:
                await m.edit(f"✅ **Test successful!**\nPosted to {success_count}/{len(active_channels)} channel(s) from Database.")
            else:
                await m.edit(f"❌ **Test Failed!**\n{error_logs}")
                
        except Exception as e:
            await m.edit(f"❌ **Error:** {e}")
            
        raise StopPropagation # Ye code ko dusre normal /start trigger hone se rok dega

# ==============================================================================
# 🎮 MANUAL COMMANDS (/post Pushpa)
# ==============================================================================

@Client.on_message(filters.command("testpost") & filters.user(info.ADMINS))
async def force_test_post(client, message):
    m = await message.reply("⏳ TMDB se movie data nikal raha hoon, wait kijiye...")
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
    
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(ssl=False, family=socket.AF_INET)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
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
        f"📥 New {type_tag} Added\n\n"
        f"✨ <b>TITLE :</b> <code>{title} {year}</code>\n"
        f"───•✧•───\n\n"
        f"🎭 <b>GENRES :</b> {genres if genres else 'Drama, Action'}\n"
        f"📺 <b>OTT :</b> N/A\n"
        f"🎞 <b>QUALITY :</b> HD\n"
        f"🎧 <b>AUDIO :</b> Hindi\n"
        f"🔥 <b>RATING :</b> {rating}\n\n"
        f"───•✧•───"
    )

    second_bot = getattr(info, 'FILE_STORE_BOT', None)
    if second_bot:
        target_bot_username = second_bot.replace("@", "")
    else:
        target_bot_username = temp.U_NAME if hasattr(temp, 'U_NAME') and temp.U_NAME else "Search_Bot"

    poster_token = getattr(info, 'POSTER_BOT_TOKEN', "")
    if poster_token:
        poster_token = poster_token.strip()
        
    TARGET_CHANNEL = getattr(info, 'UPDATES_CHANNEL', None)

    if not TARGET_CHANNEL: return await wait_msg.edit("❌ **Error:** info.py me UPDATES_CHANNEL nahi hai.")

    try:
        if poster_token:
            api_url = f"https://api.telegram.org/bot{poster_token}/sendPhoto"
            payload = {
                "chat_id": TARGET_CHANNEL, "photo": poster_url, "caption": caption_html, "parse_mode": "HTML",
                "reply_markup": json.dumps({"inline_keyboard": [[{"text": "📥 Download Now", "url": f"https://t.me/{target_bot_username}?start="}]]})
            }
            timeout_api = aiohttp.ClientTimeout(total=60)
            connector_api = aiohttp.TCPConnector(ssl=False, family=socket.AF_INET)
            async with aiohttp.ClientSession(timeout=timeout_api, connector=connector_api) as session: 
                resp = await session.post(api_url, json=payload)
                if resp.status != 200:
                    err_msg = await resp.text()
                    raise Exception(f"TELEGRAM ERROR: {err_msg}")
        else:
            caption_md = caption_html.replace("<b>", "**").replace("</b>", "**")
            buttons = [[InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{target_bot_username}?start=")]]
            sent_msg = await client.send_photo(chat_id=TARGET_CHANNEL, photo=poster_url, caption=caption_md, reply_markup=InlineKeyboardMarkup(buttons))
            if sent_msg:
                asyncio.create_task(add_poster_reactions(client, TARGET_CHANNEL, sent_msg.id))
            
        await wait_msg.edit(f"✅ **SUCCESS:** '{title}' manual post done!")
    except Exception as e:
        await wait_msg.edit(f"❌ **ERROR:** `{e}`")

# ==============================================================================
# ⏱️ THE MASTER BROADCAST LOOP
# ==============================================================================

async def start_auto_poster(client):
    await asyncio.sleep(60) 
    
    poster_token = getattr(info, 'POSTER_BOT_TOKEN', "")
    my_token = getattr(info, 'BOT_TOKEN', "")
    
    if poster_token and poster_token.strip() != my_token.strip():
        print("🛑 [Auto-Poster] Main Bot will skip TMDB loop. Second Bot will handle it independently.")
        return 

    print("🎬 [Auto-Poster] Poster Engine Activated on this Bot!")
    bot_settings_col = db.db["bot_settings"]

    while True:
        try:
            posted_data = await bot_settings_col.find_one({"_id": "posted_movies"})
            posted_ids = posted_data.get("ids", []) if posted_data else []

            media, is_mega_hit = await get_fresh_or_mega_trending(posted_ids)
            
            if media:
                media_id = str(media['id'])
                media_type = media.get('media_type', 'movie')
                
                detail_url = f"https://api.themoviedb.org/3/tv/{media_id}?api_key={info.TMDB_API_KEY}" if media_type == 'tv' else f"https://api.themoviedb.org/3/movie/{media_id}?api_key={info.TMDB_API_KEY}"
                
                timeout = aiohttp.ClientTimeout(total=30)
                connector = aiohttp.TCPConnector(ssl=False, family=socket.AF_INET)
                async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                    async with session.get(detail_url) as resp:
                        details = await resp.json()

                title = details.get("title") or details.get("name", "Unknown")
                year = (details.get("release_date") or details.get("first_air_date", ""))[:4]
                rating = round(details.get("vote_average", 0.0), 1)
                genres = ", ".join([g["name"] for g in details.get("genres", [])])
                poster_path = details.get("poster_path")
                poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "https://graph.org/file/4d61886e61dfa37a25945.jpg"

                type_tag = "#WEB_SERIES" if media_type == 'tv' else "#MOVIE"
                header_tag = "🔥 STILL TRENDING" if is_mega_hit else "📥 New"
                
                caption_html = (
                    f"{header_tag} {type_tag} Added\n\n"
                    f"✨ <b>TITLE :</b> <code>{title} {year}</code>\n"
                    f"───•✧•───\n\n"
                    f"🎭 <b>GENRES :</b> {genres if genres else 'Drama, Action'}\n"
                    f"📺 <b>OTT :</b> N/A\n"
                    f"🎞 <b>QUALITY :</b> HD\n"
                    f"🎧 <b>AUDIO :</b> Hindi\n"
                    f"🔥 <b>RATING :</b> {rating}\n\n"
                    f"───•✧•───"
                )

                second_bot_username = getattr(info, 'FILE_STORE_BOT', None)
                target_bot = second_bot_username.replace("@", "") if second_bot_username else (temp.U_NAME if hasattr(temp, 'U_NAME') and temp.U_NAME else "Search_Bot")
                
                buttons = [[InlineKeyboardButton("📥 Download Now", url=f"https://t.me/{target_bot}?start=")]]

                async def broadcast_msg(channel_id, custom_btns):
                    try:
                        sent_msg = await client.send_photo(
                            chat_id=channel_id, 
                            photo=poster_url, 
                            caption=caption_html.replace("<b>", "**").replace("</b>", "**"), 
                            reply_markup=InlineKeyboardMarkup(custom_btns)
                        )
                        print(f"🚀 Broadcasted to {channel_id}")
                        if sent_msg:
                            asyncio.create_task(add_poster_reactions(client, channel_id, sent_msg.id))
                            
                    except Exception as e:
                        print(f"❌ Post Failed for {channel_id}: {e}")

                if getattr(info, 'UPDATES_CHANNEL', None):
                    await broadcast_msg(info.UPDATES_CHANNEL, buttons)

                async for group in db.groups.find({}):
                    mu = group.get('movie_update', {})
                    if mu.get('is_active'):
                        slots = mu.get('slots', {})
                        active_chs = [ch for ch in slots.values() if ch]
                        
                        grp_buttons = list(buttons) 
                        if mu.get('group_link'):
                            grp_buttons.append([InlineKeyboardButton("👥 Group", url=mu['group_link'])])
                        if mu.get('footer'):
                            grp_buttons.append([InlineKeyboardButton(btn['text'], url=btn['url']) for btn in mu['footer']])

                        for ch in active_chs:
                            await asyncio.sleep(2) 
                            await broadcast_msg(ch, grp_buttons)

                if media_id not in posted_ids: posted_ids.append(media_id)
                if len(posted_ids) > 50: posted_ids.pop(0)
                await bot_settings_col.update_one({"_id": "posted_movies"}, {"$set": {"ids": posted_ids}}, upsert=True)

        except Exception as e:
            print(f"Poster Loop Error: {e}")
        
        await asyncio.sleep(3600) 
