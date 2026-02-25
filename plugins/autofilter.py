import logging
import time
import re
import random 
import asyncio 
import traceback 
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import SITE_URL, PM_SEARCH
from cachetools import TTLCache 

# ✅ Utils Imports (Now includes arrange_buttons)
from utils import (
    temp, btn_parser, format_text_results, format_detailed_results, 
    format_card_result, get_pagination_row, get_filter_buttons, 
    arrange_buttons, # <--- IMPORTED FROM UTILS
    get_language_buttons, get_quality_buttons, get_year_buttons,
    get_size_buttons, get_sort_buttons, filter_by_type, filter_by_lang, filter_by_quality, 
    filter_by_year, filter_by_size
)

logger = logging.getLogger(__name__)

# ✅ CONSTANTS
REACTIONS = ["👍", "❤️", "🔥", "🥰", "👏", "😁", "🎉", "🤩"]
DELETE_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg" 

# ✅ REGEX OPTIMIZATION
URL_REGEX = re.compile(r"(https?://|www\.|t\.me/|@\w+)")
CLEAN_REGEX = re.compile(r"\b(please|pls|plz|ples|send(\s+me)?|give|gib|find|chahiye|movie|new|latest|full\s+movie|file|link|hello|hi|bro|bhai|sir|bruh|hindi|tamil|malayalam|eng|with\s+subtitles|hd)\b", re.IGNORECASE)
WHITESPACE_REGEX = re.compile(r"\s+")

# ✅ SPAM CONTROL
BUTTON_LOCK = TTLCache(maxsize=10000, ttl=1)

def is_spam(user_id):
    if user_id in BUTTON_LOCK:
        return True
    BUTTON_LOCK[user_id] = True
    return False

async def auto_delete_task(bot_message, user_message, delay, show_thanks, query="files"):
    if delay <= 0: return 
    await asyncio.sleep(delay)
    try:
        await bot_message.delete()
        if show_thanks:
            caption = f"👋 Filter for '{query}' Closed.\nThank You! 😊"
            temp_msg = await user_message.reply_photo(photo=DELETE_IMG, caption=caption, quote=False)
            await asyncio.sleep(60)
            await temp_msg.delete()
    except: pass

# ✅ NOTE: arrange_buttons function removed from here (It is now in utils.py)

# ✅ HELPER: Get "Video | Docs" Row
def get_type_row(search_id, curr_type, curr_lang, curr_qual, curr_year, curr_size, curr_sort):
    row = []
    if curr_type == "video":
        row.append(InlineKeyboardButton("Videos ✅", callback_data="ignore"))
        row.append(InlineKeyboardButton("All Files", callback_data=f"filter_{search_id}_none_{curr_lang}_{curr_qual}_{curr_year}_{curr_size}_{curr_sort}_0"))
    elif curr_type == "document":
        row.append(InlineKeyboardButton("Docs ✅", callback_data="ignore"))
        row.append(InlineKeyboardButton("All Files", callback_data=f"filter_{search_id}_none_{curr_lang}_{curr_qual}_{curr_year}_{curr_size}_{curr_sort}_0"))
    else:
        row.append(InlineKeyboardButton("Videos", callback_data=f"filter_{search_id}_video_{curr_lang}_{curr_qual}_{curr_year}_{curr_size}_{curr_sort}_0"))
        row.append(InlineKeyboardButton("Docs", callback_data=f"filter_{search_id}_document_{curr_lang}_{curr_qual}_{curr_year}_{curr_size}_{curr_sort}_0"))
    return [row]

# ==============================================================================
# 1. MAIN SEARCH HANDLER
# ==============================================================================
@Client.on_message(filters.text & filters.incoming)
async def auto_filter(client, message):
    try:
        raw_query = message.text
        
        # ✅ UNIVERSAL COMMAND IGNORER: Agar message "/" se shuru hota hai, toh search rok do
        if raw_query.startswith("/"):
            return
            
        # ✅ PM SEARCH CHECK
        if not PM_SEARCH and message.chat.type == enums.ChatType.PRIVATE:
            return
            
        if message.forward_from or message.forward_from_chat or message.via_bot: return
        
        if URL_REGEX.search(raw_query): return
        if len(raw_query) < 2: return

        # ✅ UPDATE: 1 second delay ke sath delete, taaki reply block na ho
        if len(raw_query.split()) > 8:
            async def del_msg():
                await asyncio.sleep(1) # Bot ko pehle movie bhejne ka time dega
                try: await message.delete()
                except: pass
            asyncio.create_task(del_msg()) # Background me delete chalega

        query = CLEAN_REGEX.sub("", raw_query)
        query = WHITESPACE_REGEX.sub(" ", query).strip()
        if len(query) < 2: query = raw_query

        start_time = time.time()
        
        # Initial Search (Default sort: relevance)
        task_files = Media.get_search_results(query, sort="relevance")
        task_settings = db.get_group_settings(message.chat.id)
        
        files, group_settings = await asyncio.gather(task_files, task_settings)
        
        if not files: return

        if not temp.U_NAME:
            try: temp.U_NAME = (await client.get_me()).username
            except: temp.U_NAME = "Telegram"

        asyncio.create_task(db.update_daily_stats(message.chat.id, 'req'))
        asyncio.create_task(db.update_daily_stats(message.chat.id, 'suc'))

        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        auto_react = group_settings.get('auto_reaction', False)
        auto_del_time = group_settings.get('auto_delete_time', 300)
        user_del = group_settings.get('auto_delete_user_msg', False)
        del_thanks = group_settings.get('delete_thanks_msg', True)

        if auto_react:
            try: await message.react(random.choice(REACTIONS))
            except: pass 

        search_id = await Media.save_search_query(query, message.from_user.id, files)
        if not search_id: search_id = 0

        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        offset = 0 
        total_results = len(files)
        sent_msg = None 
        time_taken = round(time.time() - start_time, 2)
        
        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        
        free_prem_btn = [
            InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{message.chat.id}"),
            InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
        ]
        
        filter_buttons = get_filter_buttons(search_id, files, active_filter=None, active_lang=None, active_qual=None, active_year=None, active_size=None, active_sort="relevance")

        if mode == 'button':
            buttons = btn_parser(files, message.chat.id, search_id, offset, limit, query)
            # Pass search_id to arrange_buttons
            buttons = arrange_buttons(buttons, files, limit, filter_buttons, howto_btn, free_prem_btn, search_id)
            msg_text = f"⚡ **Results for:** `{query}`\nfound {len(files)} files."
            sent_msg = await message.reply_text(text=msg_text, reply_markup=InlineKeyboardMarkup(buttons))

        elif mode in ['text', 'detailed']:
            page_files = files[offset : offset + limit]
            
            if mode == 'text': text = format_text_results(page_files, query, message.chat.id)
            else: text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            if filter_buttons: 
                for row in filter_buttons: btn.append(row)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
            # Add Trending Button (Manual add for text mode)
            btn.append([InlineKeyboardButton("🔥 Today Popular Movies", callback_data=f"trend_list#0#{search_id}")])
            
            # Pass sort to pagination
            pagination = get_pagination_row(search_id, offset, limit, total_results, active_size=None, active_sort="relevance")
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        if mode == 'site':
            web_id = await Media.save_search_results(query, files, message.chat.id)
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            final_site_url = f"{base_url}/results/{web_id}"
            
            text = f"⚡ **Results for:** `{query}`\n📂 **Found:** {total_results} files\n👇 **Click below to view online**"
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
            # Add Trending Button
            btn.append([InlineKeyboardButton("🔥 Today Popular Movies", callback_data=f"trend_list#0#{search_id}")])

            pagination = get_pagination_row(search_id, offset, limit, total_results, active_size=None)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

        elif mode == 'card':
            file = files[0]
            text = format_card_result(file, 0, total_results)
            btn = []
            link_id = file['link_id']
            chat_id = message.chat.id
            btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])

            if howto_btn: btn.append(howto_btn)
            
            btn.append(free_prem_btn)
            
            # Add Trending Button
            btn.append([InlineKeyboardButton("🔥 Today Popular Movies", callback_data=f"trend_list#0#{search_id}")])

            if total_results > 1:
                btn.append([
                    InlineKeyboardButton(f"1/{total_results}", callback_data="pages"),
                    InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{search_id}_0")
                ])

            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

        if sent_msg and auto_del_time > 0:
            if user_del: 
                try: await message.delete()
                except: pass
            asyncio.create_task(auto_delete_task(sent_msg, message, auto_del_time, del_thanks, query))

    except Exception as e:
        logger.error(f"Search Error: {e}")
        traceback.print_exc()

# ==============================================================================
# 2. PAGINATION
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^page_"))
async def handle_pagination(client, query):
    if is_spam(query.from_user.id):
        try: await query.answer("Slow down! ⏳", show_alert=False)
        except: pass
        return

    try: await query.answer()
    except: pass
    
    try:
        data = query.data.split("_")
        search_id = int(data[1])
        offset = int(data[2])
        
        task_data = Media.get_search_query(search_id)
        task_settings = db.get_group_settings(query.message.chat.id)
        cached_data, group_settings = await asyncio.gather(task_data, task_settings)
        
        if not cached_data: return await query.answer("Search Expired", show_alert=True)
        
        files = cached_data.get('files')
        req = cached_data.get('query')
        if not files: return 
            
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        
        free_prem_btn = [
            InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{query.message.chat.id}"),
            InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
        ]
        
        filter_buttons = get_filter_buttons(search_id, files)

        buttons = btn_parser(files, query.message.chat.id, search_id, offset, limit, req)
        # Arrange buttons automatically handles trending insertion
        buttons = arrange_buttons(buttons, files, limit, filter_buttons, howto_btn, free_prem_btn, search_id)
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except MessageNotModified:
        pass
    except Exception as e:
        traceback.print_exc()

# ==============================================================================
# 3. SELECTION HANDLERS
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^filter_lang_"))
async def handle_language_selection(client, query):
    try:
        data = query.data.split("_")
        if len(data) >= 10:
            search_id, lang, f_type, qual, year, size, sort, offset = data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9]
        else:
            search_id, lang, f_type, qual, year, size, sort, offset = data[2], data[3], data[4], data[5], "none", "none", "relevance", data[6]
        query.data = f"filter_{search_id}_{f_type}_{lang}_{qual}_{year}_{size}_{sort}_{offset}"
        await handle_combined_filter(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^filter_qual_"))
async def handle_quality_selection(client, query):
    try:
        data = query.data.split("_")
        if len(data) >= 10:
            search_id, qual, f_type, lang, year, size, sort, offset = data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9]
        else:
            search_id, qual, f_type, lang, year, size, sort, offset = data[2], data[3], data[4], data[5], "none", "none", "relevance", data[6]
        query.data = f"filter_{search_id}_{f_type}_{lang}_{qual}_{year}_{size}_{sort}_{offset}"
        await handle_combined_filter(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^filter_year_"))
async def handle_year_selection(client, query):
    try:
        data = query.data.split("_")
        if len(data) >= 10:
            search_id, year, f_type, lang, qual, size, sort, offset = data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9]
        else:
            search_id, year, f_type, lang, qual, size, sort, offset = data[2], data[3], data[4], data[5], "none", "none", "relevance", data[6]
        query.data = f"filter_{search_id}_{f_type}_{lang}_{qual}_{year}_{size}_{sort}_{offset}"
        await handle_combined_filter(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^filter_size_"))
async def handle_size_selection(client, query):
    try:
        data = query.data.split("_")
        if len(data) >= 10:
            search_id, size, f_type, lang, qual, year, sort, offset = data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9]
            query.data = f"filter_{search_id}_{f_type}_{lang}_{qual}_{year}_{size}_{sort}_{offset}"
            await handle_combined_filter(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^filter_sort_"))
async def handle_sort_selection(client, query):
    try:
        data = query.data.split("_")
        if len(data) >= 10:
            search_id, sort, f_type, lang, qual, year, size, offset = data[2], data[3], data[4], data[5], data[6], data[7], data[8], data[9]
            query.data = f"filter_{search_id}_{f_type}_{lang}_{qual}_{year}_{size}_{sort}_{offset}"
            await handle_combined_filter(client, query)
    except: pass

# ==============================================================================
# 4. MASTER FILTER HANDLER
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^filter_\d"))
async def handle_combined_filter(client, query):
    if is_spam(query.from_user.id):
        try: await query.answer("Slow down! ⏳", show_alert=False)
        except: pass
        return

    try: await query.answer()
    except: pass
    
    try:
        data = query.data.split("_")
        search_id = int(data[1])
        filter_type = data[2]
        filter_lang = data[3]
        filter_qual = data[4]
        
        if len(data) >= 9:
            filter_year = data[5]
            filter_size = data[6]
            filter_sort = data[7]
            offset = int(data[8])
        elif len(data) >= 8:
            filter_year = data[5]
            filter_size = data[6]
            filter_sort = "relevance"
            offset = int(data[7])
        else:
            filter_year = "none"
            filter_size = "none"
            filter_sort = "relevance"
            offset = int(data[5])

        cached_data = await Media.get_search_query(search_id)
        if not cached_data: return await query.answer("Search Expired", show_alert=True)
        
        all_files = cached_data.get('files') or []
        req = cached_data.get('query')
        if not all_files: all_files = await Media.get_search_results(req, sort=filter_sort)

        final_files = await Media.get_search_results(
            req, 
            file_type=filter_type, 
            lang=filter_lang, 
            quality=filter_qual, 
            year=filter_year,
            size_range=filter_size,
            sort=filter_sort
        )

        if not final_files:
            if filter_size == "none":
                return await query.answer("❌ No files match these filters!", show_alert=True)

        await Media.update_search_cache(search_id, final_files)

        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        if mode == 'hybrid':
            mode = 'button' if len(final_files) <= limit else 'text'

        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        
        free_prem_btn = [
            InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{query.message.chat.id}"),
            InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
        ]

        pass_type = filter_type if filter_type != "none" else None
        pass_lang = filter_lang if filter_lang != "none" else None
        pass_qual = filter_qual if filter_qual != "none" else None
        pass_year = filter_year if filter_year != "none" else None
        pass_size = filter_size if filter_size != "none" else None
        pass_sort = filter_sort if filter_sort != "relevance" else None

        filter_buttons = get_filter_buttons(search_id, all_files, active_filter=pass_type, active_lang=pass_lang, active_qual=pass_qual, active_year=pass_year, active_size=pass_size, active_sort=pass_sort)

        if mode == 'button':
            if not final_files:
                msg_text = f"👻 **Results for:** `{req}`\n\n❌ No files found with these filters."
                buttons = []
            else:
                msg_text = f"⚡ **Results for:** `{req}`\nfound {len(final_files)} files."
                buttons = btn_parser(final_files, query.message.chat.id, search_id, offset, limit, req)
                
            buttons = arrange_buttons(buttons, final_files, limit, filter_buttons, howto_btn, free_prem_btn, search_id)
            await query.message.edit_text(text=msg_text, reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode in ['text', 'detailed']:
            if not final_files:
                text = f"👻 **Results for:** `{req}`\n\n❌ No files found with these filters."
            else:
                page_files = final_files[offset : offset + limit]
                if mode == 'text': text = format_text_results(page_files, req, query.message.chat.id)
                else: text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            
            btn = []
            if filter_buttons: 
                for row in filter_buttons: btn.append(row)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn) 
            
            # Add Trending here
            btn.append([InlineKeyboardButton("🔥 Today Popular Movies", callback_data=f"trend_list#0#{search_id}")])
            
            pagination = get_pagination_row(search_id, offset, limit, len(final_files), active_filter=pass_type, active_lang=pass_lang, active_qual=pass_qual, active_year=pass_year, active_size=pass_size, active_sort=pass_sort)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except MessageNotModified:
        pass
    except Exception as e:
        traceback.print_exc()

# ==============================================================================
# MENU OPENERS (LANG, QUAL, YEAR, SIZE, SORT)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^lang_menu_"))
async def handle_language_menu(client, query):
    try: await query.answer()
    except: pass
    try:
        data = query.data.split("_")
        search_id, c_type, c_qual, c_year, c_size = int(data[2]), data[3], data[4], data[5], data[6]
        c_sort = data[7] if len(data) > 7 else "relevance"
        c_lang = data[8] if len(data) > 8 else "none"

        cached_data = await Media.get_search_query(search_id)
        if not cached_data: return
        req = cached_data.get('query')
        files = await Media.get_search_results(req, file_type=c_type, lang=None, quality=c_qual, year=c_year, size_range=c_size, sort=c_sort)
        
        pt = c_type if c_type != "none" else None
        pq = c_qual if c_qual != "none" else None
        ps = c_sort if c_sort != "relevance" else None
        
        howto_url = (await db.get_group_settings(query.message.chat.id)).get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        
        free_prem_btn = [
            InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{query.message.chat.id}"),
            InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
        ]

        type_buttons = get_type_row(search_id, c_type, "none", c_qual, c_year, c_size, c_sort)
        lang_buttons = get_language_buttons(search_id, files, active_type=pt, active_qual=pq, active_year=c_year, active_size=c_size, active_lang=c_lang, active_sort=ps) 
        middle_buttons = type_buttons + lang_buttons
        
        buttons = arrange_buttons([], [], 10, middle_buttons, howto_btn, free_prem_btn, search_id)
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except: pass

@Client.on_callback_query(filters.regex(r"^qual_menu_"))
async def handle_quality_menu(client, query):
    try: await query.answer()
    except: pass
    try:
        data = query.data.split("_")
        search_id, c_type, c_lang, c_year, c_size = int(data[2]), data[3], data[4], data[5], data[6]
        c_sort = data[7] if len(data) > 7 else "relevance"
        c_qual = data[8] if len(data) > 8 else "none"

        cached_data = await Media.get_search_query(search_id)
        if not cached_data: return
        req = cached_data.get('query')
        files = await Media.get_search_results(req, file_type=c_type, lang=c_lang, quality=None, year=c_year, size_range=c_size, sort=c_sort)
        
        pt = c_type if c_type != "none" else None
        pl = c_lang if c_lang != "none" else None
        ps = c_sort if c_sort != "relevance" else None
        
        howto_url = (await db.get_group_settings(query.message.chat.id)).get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [
            InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{query.message.chat.id}"),
            InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
        ]

        type_buttons = get_type_row(search_id, c_type, c_lang, "none", c_year, c_size, c_sort)
        qual_buttons = get_quality_buttons(search_id, files, active_type=pt, active_lang=pl, active_year=c_year, active_size=c_size, active_qual=c_qual, active_sort=ps)
        middle_buttons = type_buttons + qual_buttons
        
        buttons = arrange_buttons([], [], 10, middle_buttons, howto_btn, free_prem_btn, search_id)
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except: pass

@Client.on_callback_query(filters.regex(r"^year_menu_"))
async def handle_year_menu(client, query):
    try: await query.answer()
    except: pass
    try:
        data = query.data.split("_")
        search_id, c_type, c_lang, c_qual, c_size = int(data[2]), data[3], data[4], data[5], data[6]
        c_sort = data[7] if len(data) > 7 else "relevance"
        c_year = data[8] if len(data) > 8 else "none"

        cached_data = await Media.get_search_query(search_id)
        if not cached_data: return
        req = cached_data.get('query')
        files = await Media.get_search_results(req, file_type=c_type, lang=c_lang, quality=c_qual, year=None, size_range=c_size, sort=c_sort)
        
        pt = c_type if c_type != "none" else None
        pl = c_lang if c_lang != "none" else None
        pq = c_qual if c_qual != "none" else None
        ps = c_sort if c_sort != "relevance" else None
        
        howto_url = (await db.get_group_settings(query.message.chat.id)).get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [
            InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{query.message.chat.id}"),
            InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
        ]

        type_buttons = get_type_row(search_id, c_type, c_lang, c_qual, "none", c_size, c_sort)
        year_buttons = get_year_buttons(search_id, files, active_type=pt, active_lang=pl, active_qual=pq, active_size=c_size, active_year=c_year, active_sort=ps)
        middle_buttons = type_buttons + year_buttons
        
        buttons = arrange_buttons([], [], 10, middle_buttons, howto_btn, free_prem_btn, search_id)
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except: pass

@Client.on_callback_query(filters.regex(r"^size_menu_"))
async def handle_size_menu(client, query):
    try: await query.answer()
    except: pass
    try:
        data = query.data.split("_")
        search_id, c_type, c_lang, c_qual, c_year = int(data[2]), data[3], data[4], data[5], data[6]
        c_sort = data[7] if len(data) > 7 else "relevance"
        c_size = data[8] if len(data) > 8 else "none"

        howto_url = (await db.get_group_settings(query.message.chat.id)).get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [
            InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{query.message.chat.id}"),
            InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
        ]

        type_buttons = get_type_row(search_id, c_type, c_lang, c_qual, c_year, "none", c_sort)
        size_buttons = get_size_buttons(search_id, active_type=c_type, active_lang=c_lang, active_qual=c_qual, active_year=c_year, active_size=c_size, active_sort=c_sort)
        middle_buttons = type_buttons + size_buttons
        
        buttons = arrange_buttons([], [], 10, middle_buttons, howto_btn, free_prem_btn, search_id)
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except: pass

# ✅ NEW: SORT MENU OPENER
@Client.on_callback_query(filters.regex(r"^sort_menu_"))
async def handle_sort_menu(client, query):
    try: await query.answer()
    except: pass
    try:
        data = query.data.split("_")
        search_id, c_type, c_lang, c_qual, c_year, c_size = int(data[2]), data[3], data[4], data[5], data[6], data[7]
        c_sort = "relevance"
        if len(data) > 8: c_sort = data[8]

        howto_url = (await db.get_group_settings(query.message.chat.id)).get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [
            InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{query.message.chat.id}"),
            InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
        ]

        # Header Row
        type_buttons = get_type_row(search_id, c_type, c_lang, c_qual, c_year, c_size, c_sort)
        # Sort Buttons
        sort_buttons = get_sort_buttons(search_id, c_type, c_lang, c_qual, c_year, c_size, c_sort)
        
        middle_buttons = type_buttons + sort_buttons
        buttons = arrange_buttons([], [], 10, middle_buttons, howto_btn, free_prem_btn, search_id)
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Sort Menu Error: {e}")
        traceback.print_exc()

# ==============================================================================
# 13. RESET & IGNORE & CARD NAV
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^unfilter_"))
async def handle_unfilter(client, query):
    try:
        search_id = int(query.data.split("_")[1])
        query.data = f"filter_{search_id}_none_none_none_none_none_relevance_0"
        await handle_combined_filter(client, query)
    except: pass

@Client.on_callback_query(filters.regex(r"^ignore"))
async def ignore_callback(client, query):
    await query.answer()

@Client.on_callback_query(filters.regex(r"^pages$"))
async def page_counter_callback(client, query):
    await query.answer(f"Current Page Indicator", show_alert=False)

@Client.on_callback_query(filters.regex(r"^card_next_"))
async def card_next_nav(client, query):
    if is_spam(query.from_user.id): return
    try: await query.answer()
    except: pass
    try:
        data = query.data.split("_")
        if data[2] == "None": return
        search_id = int(data[2])
        current_index = int(data[3])
        cached_data = await Media.get_search_query(search_id)
        if not cached_data: return
        files = cached_data.get('files')
        if not files: return 
        total = len(files)
        next_index = current_index + 1
        if next_index >= total: next_index = 0
        file = files[next_index]
        text = format_card_result(file, next_index, total)
        group_settings = await db.get_group_settings(query.message.chat.id)
        howto_url = group_settings.get('howto_url')
        btn = []
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])
        if howto_url: btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        
        # Swapped Position in Card Mode as well
        btn.append([
            InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{chat_id}"),
            InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
        ])
        
        # Add Trending Button
        btn.append([InlineKeyboardButton("🔥 Today Popular Movies", callback_data=f"trend_list#0#{search_id}")])

        nav_row = []
        if next_index > 0: nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{search_id}_{next_index}"))
        nav_row.append(InlineKeyboardButton(f"{next_index + 1}/{total}", callback_data="pages"))
        if next_index < total - 1: nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{search_id}_{next_index}"))
        btn.append(nav_row)
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except: pass

@Client.on_callback_query(filters.regex(r"^card_prev_"))
async def card_prev_nav(client, query):
    if is_spam(query.from_user.id): return
    try: await query.answer()
    except: pass
    try:
        data = query.data.split("_")
        if data[2] == "None": return 
        search_id = int(data[2])
        current_index = int(data[3])
        cached_data = await Media.get_search_query(search_id)
        if not cached_data: return
        files = cached_data.get('files')
        if not files: return 
        total = len(files)
        prev_index = current_index - 1
        if prev_index < 0: prev_index = total - 1
        file = files[prev_index]
        text = format_card_result(file, prev_index, total)
        group_settings = await db.get_group_settings(query.message.chat.id)
        howto_url = group_settings.get('howto_url')
        btn = []
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])
        if howto_url: btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        
        # Swapped Position in Card Mode as well
        btn.append([
            InlineKeyboardButton("📂 Send All", url=f"https://t.me/{temp.U_NAME}?start=sendall_{search_id}_{chat_id}"),
            InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")
        ])
        
        # Add Trending Button
        btn.append([InlineKeyboardButton("🔥 Today Popular Movies", callback_data=f"trend_list#0#{search_id}")])

        nav_row = []
        if prev_index > 0: nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{search_id}_{prev_index}"))
        nav_row.append(InlineKeyboardButton(f"{prev_index + 1}/{total}", callback_data="pages"))
        if prev_index < total - 1: nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{search_id}_{prev_index}"))
        btn.append(nav_row)
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except: pass
