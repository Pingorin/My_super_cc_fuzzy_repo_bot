import logging
import time
import re
import random 
import asyncio 
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import PORT, SITE_URL
# ✅ IMPORT get_filter_buttons here
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row, get_filter_buttons

logger = logging.getLogger(__name__)

# ✅ CONSTANTS
REACTIONS = ["👍", "❤️", "🔥", "🥰", "👏", "😁", "🎉", "🤩"]
DELETE_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg" 

async def auto_delete_task(bot_message, user_message, delay, show_thanks, query="files"):
    if delay <= 0: return 
    await asyncio.sleep(delay)
    try:
        await bot_message.delete()
        if show_thanks:
            caption = (
                f"👋 Hᴇʏ fasion lovers, Yᴏᴜʀ Fɪʟᴛᴇʀ Fᴏʀ '{query}' Is Cʟᴏsᴇᴅ 📪\n\n"
                f"Tʜᴀɴᴋ Yᴏᴜ Fᴏʀ Usɪɴɢ! 🌟\nCᴏᴍᴇ Aɢᴀɪɴ! 😊👍"
            )
            temp_msg = await user_message.reply_photo(photo=DELETE_IMG, caption=caption, quote=False)
            await asyncio.sleep(60)
            await temp_msg.delete()
    except: pass

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index", "set_shortner", "settings", "connect", "delreq"]))
async def auto_filter(client, message):
    raw_query = message.text

    # --- BLOCKERS ---
    if message.forward_from or message.forward_from_chat or message.via_bot: return
    if re.search(r"(https?://|www\.|t\.me/|@\w+)", raw_query): return
    NSFW = ["porn", "sex", "xxx", "nude", "horny", "gore", "adult", "dick", "pussy"]
    if any(word in raw_query.lower() for word in NSFW): return
    if len(raw_query) < 2: return
    # ----------------

    # --- CLEANING ---
    clean_regex = r"\b(please|pls|plz|ples|send(\s+me)?|give|gib|find|chahiye|movie|new|latest|full\s+movie|file|link|hello|hi|bro|bhai|sir|bruh|hindi|tamil|malayalam|eng|with\s+subtitles|hd)\b"
    query = re.sub(clean_regex, "", raw_query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()
    if len(query) < 2: query = raw_query
    # ----------------

    start_time = time.time()

    try:
        # 1. Settings
        group_settings = await db.get_group_settings(message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        auto_react = group_settings.get('auto_reaction', False)
        auto_del_time = group_settings.get('auto_delete_time', 300)
        user_del = group_settings.get('auto_delete_user_msg', False)
        del_thanks = group_settings.get('delete_thanks_msg', True)
        howto_url = group_settings.get('howto_url')

        await db.update_daily_stats(message.chat.id, 'req')

        # 2. Search
        files = await Media.get_search_results(query)
        end_time = time.time()
        time_taken = round(end_time - start_time, 2)

        if not files: return
        await db.update_daily_stats(message.chat.id, 'suc')

        # 3. Save Session (Default: No Filter)
        # Note: Ensure Media.save_search_result accepts filter_mode in ia_filterdb.py
        unique_id = await Media.save_search_result(query, files, filter_mode=None)

        if auto_react:
            try: await message.react(random.choice(REACTIONS))
            except: pass 

        if mode == 'hybrid':
            if len(files) <= limit: mode = 'button'
            else: mode = 'text'

        offset = 0 
        total_results = len(files)
        sent_msg = None 
        
        # 4. Prepare Buttons
        howto_btn = [[InlineKeyboardButton("⁉️ How To Download", url=howto_url)]] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]
        
        # ✅ FILTER BUTTONS (State: None)
        filter_buttons = get_filter_buttons(unique_id, active_mode=None)

        # --- MODE A: BUTTON ---
        if mode == 'button':
            # ✅ FIX: Pass query as 4th arg
            buttons = btn_parser(files, message.chat.id, unique_id, query, offset, limit)
            
            # Inject Filter Buttons
            for row in reversed(filter_buttons): buttons.append(row)
            
            if howto_btn: buttons.append(howto_btn[0])
            buttons.append(free_prem_btn)

            msg_text = f"⚡ **Hey {message.from_user.mention}!**\n👻 **Here are your results for:** `{query}`\n⏳ **Time Taken:** {time_taken} seconds"
            sent_msg = await message.reply_text(text=msg_text, reply_markup=InlineKeyboardMarkup(buttons))

        # --- MODE B: TEXT ---
        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, query, message.chat.id)
            
            btn = []
            # Inject Filter Buttons
            for row in reversed(filter_buttons): btn.append(row)

            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, unique_id)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

        # --- MODE C: DETAILED ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            for row in reversed(filter_buttons): btn.append(row)

            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)

            pagination = get_pagination_row(offset, limit, total_results, unique_id)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

        # --- MODE D: SITE ---
        elif mode == 'site':
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            final_site_url = f"{base_url}/results/{unique_id}"
            text = f"⚡ **Results for:** `{query}`\n📂 **Found:** {total_results} files\n⏳ **Time:** {time_taken}s\n\n👇 **Click the button below to view results online**"
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)
            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

        # Auto Delete
        if sent_msg:
            if user_del:
                try: await message.delete()
                except: pass
            if auto_del_time > 0:
                asyncio.create_task(auto_delete_task(sent_msg, message, auto_del_time, del_thanks, query))

    except Exception as e:
        logger.error(f"Search Error: {e}")

# ==============================================================================
# 🎞️ FILTER CALLBACK HANDLER
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^(filter_|unfilter_)"))
async def filter_media_handler(client, query):
    try:
        data = query.data
        if data.startswith("unfilter_"):
            _, unique_id = data.split("_")
            filter_type = None # Reset to All
        else:
            # filter_video_{id} or filter_doc_{id}
            _, f_type, unique_id = data.split("_")
            filter_type = "video" if f_type == "video" else "document"

        old_session = await Media.get_search_session(unique_id)
        if not old_session:
            return await query.answer("⚠️ Search expired. Please search again.", show_alert=True)
            
        original_query = old_session['query']

        # ✅ DB CALL: Get filtered files
        files = await Media.get_search_results(original_query, file_type=filter_type)
        if not files:
            return await query.answer(f"❌ No {filter_type}s found!", show_alert=True)

        # ✅ SAVE NEW SESSION with 'filter_mode'
        new_unique_id = await Media.save_search_result(original_query, files, filter_mode=filter_type)
        
        # Generate UI
        group_settings = await db.get_group_settings(query.message.chat.id)
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        howto_url = group_settings.get('howto_url')
        
        # Get Filter Buttons with correct active state
        filter_btns = get_filter_buttons(new_unique_id, active_mode=filter_type)
        
        # Extras
        extras = []
        if howto_url: extras.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        extras.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])

        # Generate File Buttons (Page 0)
        buttons = btn_parser(files, query.message.chat.id, new_unique_id, original_query, 0, limit)
        
        # Inject Filter Buttons
        for row in reversed(filter_btns): buttons.append(row)
        for row in extras: buttons.append(row)

        mode_text = filter_type.capitalize() + "s" if filter_type else "All Files"
        text = f"⚡ **Results for:** `{original_query}`\n🎞 **Filter:** {mode_text}\n📂 **Found:** {len(files)} matches"
        
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        
    except Exception as e:
        logger.error(f"Filter Error: {e}")
        await query.answer("⚠️ Error filtering.", show_alert=True)

# ==============================================================================
# ⏭️ PAGINATION HANDLER
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        _, unique_id, offset = query.data.split("_") 
        offset = int(offset)
        
        session = await Media.get_search_session(unique_id)
        if not session: return await query.answer("❌ Search expired.", show_alert=True)
            
        files = session['files']
        req = session['query']
        # ✅ RETRIEVE FILTER STATE (To keep buttons highlighted on next page)
        filter_mode = session.get('filter_mode') 

        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        if mode == 'hybrid': mode = 'button' if len(files) <= limit else 'text'

        howto_url = group_settings.get('howto_url')
        howto_btn = [[InlineKeyboardButton("⁉️ How To Download", url=howto_url)]] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]
        
        # ✅ Regenerate Filter Buttons with correct state
        filter_buttons = get_filter_buttons(unique_id, active_mode=filter_mode)

        if mode == 'button':
            # ✅ FIX: Pass 'req' (query)
            buttons = btn_parser(files, query.message.chat.id, unique_id, req, offset, limit)
            for row in reversed(filter_buttons): buttons.append(row)
            if howto_btn: buttons.append(howto_btn[0])
            buttons.append(free_prem_btn)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, req, query.message.chat.id)
            btn = []
            for row in reversed(filter_buttons): btn.append(row)
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)
            pagination = get_pagination_row(offset, limit, len(files), unique_id)
            if pagination: btn.append(pagination)
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            btn = []
            for row in reversed(filter_buttons): btn.append(row)
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)
            pagination = get_pagination_row(offset, limit, len(files), unique_id)
            if pagination: btn.append(pagination)
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Pagination Error: {e}")
        await query.answer("⚠️ Error switching page.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^pages$"))
async def page_counter_callback(client, query):
    await query.answer(f"Current Page Indicator", show_alert=False)
