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
from info import SITE_URL
from utils import (
    temp, btn_parser, format_text_results, format_detailed_results, 
    format_card_result, get_pagination_row, filter_by_type, 
    get_filter_buttons, get_language_buttons, get_quality_buttons, 
    filter_by_lang, filter_by_quality, filter_by_year, get_year_buttons
)

logger = logging.getLogger(__name__)

# ✅ CONSTANTS
REACTIONS = ["👍", "❤️", "🔥", "🥰", "👏", "😁", "🎉", "🤩"]
DELETE_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg" 

# ✅ SPAM CONTROL
BUTTON_LOCK = {}

def is_spam(user_id):
    current_time = time.time()
    last_time = BUTTON_LOCK.get(user_id, 0)
    BUTTON_LOCK[user_id] = current_time
    return (current_time - last_time < 1.0) # 1 second limit

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

# ==============================================================================
# 🛠️ HELPER: ARRANGE BUTTONS
# ==============================================================================
def arrange_buttons(buttons, files, limit, filter_buttons, howto_btn, free_prem_btn):
    pagination_row = []
    if len(files) > limit:
        pagination_row = buttons.pop() 
    
    # Add Filter Buttons (Rows)
    if filter_buttons:
        for row in filter_buttons:
            buttons.append(row)
    
    if howto_btn: buttons.append(howto_btn)
    if free_prem_btn: buttons.append(free_prem_btn)
    
    # Add Pagination at the very bottom
    if pagination_row: buttons.append(pagination_row)
        
    return buttons

# ==============================================================================
# 1. MAIN SEARCH HANDLER
# ==============================================================================
@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index", "set_shortner", "settings", "connect", "delreq"]))
async def auto_filter(client, message):
    try:
        raw_query = message.text
        if message.forward_from or message.forward_from_chat or message.via_bot: return
        if re.search(r"(https?://|www\.|t\.me/|@\w+)", raw_query): return
        if len(raw_query) < 2: return

        clean_regex = r"\b(please|pls|plz|ples|send(\s+me)?|give|gib|find|chahiye|movie|new|latest|full\s+movie|file|link|hello|hi|bro|bhai|sir|bruh|hindi|tamil|malayalam|eng|with\s+subtitles|hd)\b"
        query = re.sub(clean_regex, "", raw_query, flags=re.IGNORECASE)
        query = re.sub(r"\s+", " ", query).strip()
        if len(query) < 2: query = raw_query

        start_time = time.time()
        
        task_files = Media.get_search_results(query)
        task_settings = db.get_group_settings(message.chat.id)
        
        files, group_settings = await asyncio.gather(task_files, task_settings)
        
        if not files: return

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
        
        if not temp.U_NAME:
            try: temp.U_NAME = (await client.get_me()).username
            except: temp.U_NAME = "Telegram"
            
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]
        
        # ✅ INITIAL STATE: All filters None (Year included)
        filter_buttons = get_filter_buttons(search_id, active_filter=None, active_lang=None, active_qual=None, active_year=None)

        # --- MODE A: BUTTON ---
        if mode == 'button':
            buttons = btn_parser(files, message.chat.id, search_id, offset, limit, query, active_filter=None, active_lang=None, active_qual=None, active_year=None)
            buttons = arrange_buttons(buttons, files, limit, filter_buttons, howto_btn, free_prem_btn)
            msg_text = f"⚡ **Results for:** `{query}`\nfound {len(files)} files."
            sent_msg = await message.reply_text(text=msg_text, reply_markup=InlineKeyboardMarkup(buttons))

        # --- MODE B/C: TEXT & DETAILED ---
        elif mode in ['text', 'detailed']:
            page_files = files[offset : offset + limit]
            
            if mode == 'text': text = format_text_results(page_files, query, message.chat.id)
            else: text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            if filter_buttons: 
                for row in filter_buttons: btn.append(row)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(search_id, offset, limit, total_results)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE D: SITE ---
        elif mode == 'site':
            web_id = await Media.save_search_results(query, files, message.chat.id)
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            final_site_url = f"{base_url}/results/{web_id}"
            
            text = f"⚡ **Results for:** `{query}`\n📂 **Found:** {total_results} files\n👇 **Click below to view online**"
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)

            pagination = get_pagination_row(search_id, offset, limit, total_results)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

        # --- MODE E: CARD ---
        elif mode == 'card':
            file = files[0]
            text = format_card_result(file, 0, total_results)
            btn = []
            link_id = file['link_id']
            chat_id = message.chat.id
            btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])

            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)

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
# 2. STANDARD PAGINATION
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
        
        if not cached_data: return 
        
        files = cached_data.get('files')
        req = cached_data.get('query')
        if not files: files = await Media.get_search_results(req)
        if not files: return 
            
        total_results = len(files)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10

        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]
        
        # Initial Filter State
        filter_buttons = get_filter_buttons(search_id, active_filter=None, active_lang=None, active_qual=None, active_year=None)

        if mode == 'button':
            buttons = btn_parser(files, query.message.chat.id, search_id, offset, limit, req)
            buttons = arrange_buttons(buttons, files, limit, filter_buttons, howto_btn, free_prem_btn)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode in ['text', 'detailed']:
            page_files = files[offset : offset + limit]
            if mode == 'text': text = format_text_results(page_files, req, query.message.chat.id)
            else: text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            
            btn = []
            if filter_buttons: 
                for row in filter_buttons: btn.append(row)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn) 
            pagination = get_pagination_row(search_id, offset, limit, total_results)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except MessageNotModified:
        pass
    except Exception as e:
        traceback.print_exc()

# ==============================================================================
# 3. MASTER FILTER HANDLER (Combines Type, Language, Quality & Year)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^filter_"))
async def handle_combined_filter(client, query):
    # This handler manages ALL filters simultaneously.
    
    # Redirect specific menu clicks to their handlers
    if "filter_lang_" in query.data: return await handle_language_selection(client, query)
    if "filter_qual_" in query.data: return await handle_quality_selection(client, query)
    if "filter_year_" in query.data: return await handle_year_selection(client, query) # ✅ NEW Redirect

    if is_spam(query.from_user.id):
        try: await query.answer("Slow down! ⏳", show_alert=False)
        except: pass
        return

    try: await query.answer()
    except: pass
    
    try:
        # DATA FORMAT: filter_{id}_{type}_{lang}_{qual}_{year}_{offset}
        data = query.data.split("_")
        search_id = int(data[1])
        filter_type = data[2] # video, document, none
        filter_lang = data[3] # English, Hindi, none
        filter_qual = data[4] # 720p, 1080p, none
        
        # Backward compatibility for existing buttons without year
        if len(data) >= 7:
            filter_year = data[5]
            offset = int(data[6])
        else:
            filter_year = "none"
            offset = int(data[5])

        task_data = Media.get_search_query(search_id)
        task_settings = db.get_group_settings(query.message.chat.id)
        cached_data, group_settings = await asyncio.gather(task_data, task_settings)
        
        if not cached_data: return
        
        all_files = cached_data.get('files')
        req = cached_data.get('query')
        if not all_files: all_files = await Media.get_search_results(req)

        # 1. APPLY TYPE FILTER
        if filter_type != "none":
            capital_type = "Video" if filter_type == "video" else "Document"
            files_step_1 = filter_by_type(all_files, capital_type)
        else:
            files_step_1 = all_files

        # 2. APPLY LANGUAGE FILTER
        if filter_lang != "none":
            files_step_2 = filter_by_lang(files_step_1, filter_lang)
        else:
            files_step_2 = files_step_1
            
        # 3. APPLY QUALITY FILTER
        if filter_qual != "none":
            files_step_3 = filter_by_quality(files_step_2, filter_qual)
        else:
            files_step_3 = files_step_2

        # 4. APPLY YEAR FILTER (NEW)
        if filter_year != "none":
            final_files = filter_by_year(files_step_3, filter_year)
        else:
            final_files = files_step_3

        if not final_files:
            return await query.answer("❌ No files match these filters!", show_alert=True)

        total_results = len(final_files)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10

        if mode == 'hybrid':
            mode = 'button' if len(final_files) <= limit else 'text'

        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # ✅ PREPARE STATES FOR NEXT BUTTONS
        pass_type = filter_type if filter_type != "none" else None
        pass_lang = filter_lang if filter_lang != "none" else None
        pass_qual = filter_qual if filter_qual != "none" else None
        pass_year = filter_year if filter_year != "none" else None

        # Generate Buttons (Passing ALL states)
        filter_buttons = get_filter_buttons(search_id, active_filter=pass_type, active_lang=pass_lang, active_qual=pass_qual, active_year=pass_year)

        if mode == 'button':
            buttons = btn_parser(final_files, query.message.chat.id, search_id, offset, limit, req, active_filter=pass_type, active_lang=pass_lang, active_qual=pass_qual, active_year=pass_year)
            buttons = arrange_buttons(buttons, final_files, limit, filter_buttons, howto_btn, free_prem_btn)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode in ['text', 'detailed']:
            page_files = final_files[offset : offset + limit]
            
            if mode == 'text': text = format_text_results(page_files, req, query.message.chat.id)
            else: text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            
            btn = []
            if filter_buttons: 
                for row in filter_buttons: btn.append(row)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn) 
            
            # Manual Pagination Construction
            pagination = get_pagination_row(search_id, offset, limit, total_results, active_filter=pass_type, active_lang=pass_lang, active_qual=pass_qual, active_year=pass_year)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except MessageNotModified:
        pass
    except Exception as e:
        traceback.print_exc()

# ==============================================================================
# 4. LANGUAGE SELECTION HANDLER (Redirects to Combined Filter)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^filter_lang_"))
async def handle_language_selection(client, query):
    try:
        # DATA: filter_lang_{id}_{lang}_{type}_{qual}_{year}_{offset}
        data = query.data.split("_")
        search_id = data[2]
        lang = data[3]
        f_type = data[4]
        qual = data[5]
        
        # Check for Year param
        if len(data) >= 8:
            year = data[6]
            offset = data[7]
        else:
            year = "none"
            offset = data[6]
        
        # Route to Master Filter: filter_{id}_{type}_{lang}_{qual}_{year}_{offset}
        query.data = f"filter_{search_id}_{f_type}_{lang}_{qual}_{year}_{offset}"
        await handle_combined_filter(client, query)
    except: pass

# ==============================================================================
# 5. QUALITY SELECTION HANDLER (Redirects to Combined Filter)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^filter_qual_"))
async def handle_quality_selection(client, query):
    try:
        # DATA: filter_qual_{id}_{qual}_{type}_{lang}_{year}_{offset}
        data = query.data.split("_")
        search_id = data[2]
        qual = data[3]
        f_type = data[4]
        lang = data[5]
        
        # Check for Year param
        if len(data) >= 8:
            year = data[6]
            offset = data[7]
        else:
            year = "none"
            offset = data[6]
        
        # Route to Master Filter: filter_{id}_{type}_{lang}_{qual}_{year}_{offset}
        query.data = f"filter_{search_id}_{f_type}_{lang}_{qual}_{year}_{offset}"
        await handle_combined_filter(client, query)
    except: pass

# ==============================================================================
# 6. YEAR SELECTION HANDLER (NEW - Redirects to Combined Filter)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^filter_year_"))
async def handle_year_selection(client, query):
    try:
        # DATA: filter_year_{id}_{year}_{type}_{lang}_{qual}_{offset}
        data = query.data.split("_")
        search_id = data[2]
        year = data[3]
        f_type = data[4]
        lang = data[5]
        qual = data[6]
        offset = data[7]
        
        # Route to Master Filter: filter_{id}_{type}_{lang}_{qual}_{year}_{offset}
        query.data = f"filter_{search_id}_{f_type}_{lang}_{qual}_{year}_{offset}"
        await handle_combined_filter(client, query)
    except: pass

# ==============================================================================
# 7. LANGUAGE MENU OPENER
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^lang_menu_"))
async def handle_language_menu(client, query):
    try: await query.answer()
    except: pass

    try:
        # DATA: lang_menu_{id}_{type}_{qual}_{year}
        data = query.data.split("_")
        search_id = int(data[2])
        curr_type = data[3] 
        curr_qual = data[4]
        curr_year = data[5] if len(data) > 5 else "none"

        cached_data = await Media.get_search_query(search_id)
        if not cached_data: return await query.answer("Results expired.", show_alert=True)
        
        files = cached_data.get('files')
        
        # Filter first by Type, Qual & Year to get accurate counts
        if curr_type != "none":
            files = filter_by_type(files, "Video" if curr_type == "video" else "Document")
        if curr_qual != "none":
            files = filter_by_quality(files, curr_qual)
        if curr_year != "none":
            files = filter_by_year(files, curr_year)

        if not files: return await query.answer("No files to filter.", show_alert=True)
        
        pt = curr_type if curr_type != "none" else None
        pq = curr_qual if curr_qual != "none" else None
        py = curr_year if curr_year != "none" else None
        
        # Generate Grid (Updated to pass year)
        # Note: You'll need to update get_language_buttons in utils.py to accept active_year if you want it to persist, 
        # or just pass it in the callback data generation logic inside get_language_buttons
        # For now, assuming standard language buttons generation
        lang_buttons = get_language_buttons(search_id, files, active_type=pt, active_qual=pq) 
        # Ideally get_language_buttons needs update in utils.py to accept active_year too
        
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(lang_buttons))
        
    except Exception as e:
        logger.error(f"Lang Menu Error: {e}")

# ==============================================================================
# 8. QUALITY MENU OPENER
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^qual_menu_"))
async def handle_quality_menu(client, query):
    try: await query.answer()
    except: pass

    try:
        # DATA: qual_menu_{id}_{type}_{lang}_{year}
        data = query.data.split("_")
        search_id = int(data[2])
        curr_type = data[3]
        curr_lang = data[4]
        curr_year = data[5] if len(data) > 5 else "none"

        cached_data = await Media.get_search_query(search_id)
        if not cached_data: return await query.answer("Results expired.", show_alert=True)
        
        files = cached_data.get('files')
        
        # Filter first by Type, Lang & Year
        if curr_type != "none":
            files = filter_by_type(files, "Video" if curr_type == "video" else "Document")
        if curr_lang != "none":
            files = filter_by_lang(files, curr_lang)
        if curr_year != "none":
            files = filter_by_year(files, curr_year)

        if not files: return await query.answer("No files to filter.", show_alert=True)
        
        pt = curr_type if curr_type != "none" else None
        pl = curr_lang if curr_lang != "none" else None
        
        # Generate Grid
        qual_buttons = get_quality_buttons(search_id, files, active_type=pt, active_lang=pl)
        
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(qual_buttons))
        
    except Exception as e:
        logger.error(f"Qual Menu Error: {e}")

# ==============================================================================
# 9. YEAR MENU OPENER (NEW)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^year_menu_"))
async def handle_year_menu(client, query):
    try: await query.answer()
    except: pass

    try:
        # DATA: year_menu_{id}_{type}_{lang}_{qual}
        data = query.data.split("_")
        search_id = int(data[2])
        curr_type = data[3]
        curr_lang = data[4]
        curr_qual = data[5]

        cached_data = await Media.get_search_query(search_id)
        if not cached_data: return await query.answer("Results expired.", show_alert=True)
        
        files = cached_data.get('files')
        
        # Filter first by Type, Lang, Qual to get relevant years
        if curr_type != "none":
            files = filter_by_type(files, "Video" if curr_type == "video" else "Document")
        if curr_lang != "none":
            files = filter_by_lang(files, curr_lang)
        if curr_qual != "none":
            files = filter_by_quality(files, curr_qual)

        if not files: return await query.answer("No files to filter.", show_alert=True)
        
        pt = curr_type if curr_type != "none" else None
        pl = curr_lang if curr_lang != "none" else None
        pq = curr_qual if curr_qual != "none" else None
        
        # Generate Grid
        year_buttons = get_year_buttons(search_id, files, active_type=pt, active_lang=pl, active_qual=pq)
        
        await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(year_buttons))
        
    except Exception as e:
        logger.error(f"Year Menu Error: {e}")

# ==============================================================================
# 10. RESET HANDLER
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^unfilter_"))
async def handle_unfilter(client, query):
    try:
        search_id = int(query.data.split("_")[1])
        # Reset everything to 0: filter_{id}_none_none_none_none_0
        query.data = f"filter_{search_id}_none_none_none_none_0"
        await handle_combined_filter(client, query)
    except: 
        try: await query.answer("Error Resetting", show_alert=True)
        except: pass

@Client.on_callback_query(filters.regex(r"^ignore"))
async def ignore_callback(client, query):
    await query.answer()

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
        if not files: files = await Media.get_search_results(cached_data.get('query'))
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
        btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])

        nav_row = []
        if next_index > 0: 
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{search_id}_{next_index}"))
        nav_row.append(InlineKeyboardButton(f"{next_index + 1}/{total}", callback_data="pages"))
        if next_index < total - 1: 
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{search_id}_{next_index}"))
        btn.append(nav_row)
        
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except MessageNotModified:
        pass
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
        if not files: files = await Media.get_search_results(cached_data.get('query'))
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
        btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
        
        nav_row = []
        if prev_index > 0: 
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{search_id}_{prev_index}"))
        nav_row.append(InlineKeyboardButton(f"{prev_index + 1}/{total}", callback_data="pages"))
        if prev_index < total - 1: 
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{search_id}_{prev_index}"))
        btn.append(nav_row)
        
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except FloodWait as e:
        await asyncio.sleep(e.value)
    except MessageNotModified:
        pass
    except: pass

@Client.on_callback_query(filters.regex(r"^pages$"))
async def page_counter_callback(client, query):
    await query.answer(f"Current Page Indicator", show_alert=False)
