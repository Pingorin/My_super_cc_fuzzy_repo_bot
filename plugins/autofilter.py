import logging
import time
import re
import random 
import asyncio 
import traceback 
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified, QueryIdInvalid
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import SITE_URL
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row, filter_by_type, get_filter_buttons

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

        # Get Default Filter Buttons
        filter_buttons = get_filter_buttons(search_id, active_filter=None)

        if mode == 'button':
            buttons = btn_parser(files, message.chat.id, search_id, offset, limit, query)
            if filter_buttons: buttons.append(filter_buttons)
            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)

            msg_text = f"⚡ **Results for:** `{query}`\nfound {len(files)} files."
            sent_msg = await message.reply_text(text=msg_text, reply_markup=InlineKeyboardMarkup(buttons))

        elif mode in ['text', 'detailed']:
            page_files = files[offset : offset + limit]
            
            if mode == 'text': text = format_text_results(page_files, query, message.chat.id)
            else: text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            if filter_buttons: btn.append(filter_buttons)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(search_id, offset, limit, total_results)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

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
# 2. STANDARD PAGINATION (Handles Reset/Unfilter too)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^page_"))
async def handle_pagination(client, query):
    # ✅ Check Spam but allow navigation
    if is_spam(query.from_user.id):
        try: await query.answer("Slow down! ⏳", show_alert=False)
        except: pass
        return

    try: await query.answer()
    except: pass
    
    try:
        data = query.data.split("_")
        if len(data) != 3: return 
        if data[1] == "None": return 
        
        search_id = int(data[1])
        offset = int(data[2])
        
        task_data = Media.get_search_query(search_id)
        task_settings = db.get_group_settings(query.message.chat.id)
        
        cached_data, group_settings = await asyncio.gather(task_data, task_settings)
        
        if not cached_data: return 
        
        files = cached_data.get('files')
        req = cached_data.get('query')
        
        # Fallback if cache lost
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

        # ✅ SHOW DEFAULT FILTERS (Because this is standard/reset view)
        filter_buttons = get_filter_buttons(search_id, active_filter=None)

        if mode == 'button':
            buttons = btn_parser(files, query.message.chat.id, search_id, offset, limit, req)
            if filter_buttons: buttons.append(filter_buttons)
            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode in ['text', 'detailed']:
            page_files = files[offset : offset + limit]
            
            if mode == 'text': text = format_text_results(page_files, req, query.message.chat.id)
            else: text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            
            btn = []
            if filter_buttons: btn.append(filter_buttons)
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
# 3. FILTER PAGINATION HANDLER
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^filter_"))
async def handle_filter_pagination(client, query):
    if is_spam(query.from_user.id):
        try: await query.answer("Slow down! ⏳", show_alert=False)
        except: pass
        return

    try: await query.answer()
    except: pass
    
    try:
        data = query.data.split("_")
        search_id = int(data[1])
        filter_type = data[3]
        offset = int(data[4])

        task_data = Media.get_search_query(search_id)
        task_settings = db.get_group_settings(query.message.chat.id)
        
        cached_data, group_settings = await asyncio.gather(task_data, task_settings)
        
        if not cached_data: return
        
        all_files = cached_data.get('files')
        req = cached_data.get('query')
        if not all_files: all_files = await Media.get_search_results(req)

        # Apply Filter
        filter_capital = "Video" if filter_type == "video" else "Document"
        filtered_files = filter_by_type(all_files, filter_capital)
        
        if not filtered_files:
            return await query.answer(f"❌ No {filter_type}s found!", show_alert=True)

        total_results = len(filtered_files)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10

        if mode == 'hybrid':
            mode = 'button' if len(filtered_files) <= limit else 'text'

        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # ✅ SHOW ACTIVE FILTER STATE
        filter_buttons = get_filter_buttons(search_id, active_filter=filter_type)

        if mode == 'button':
            buttons = btn_parser(filtered_files, query.message.chat.id, search_id, offset, limit, req, filter_type=filter_type)
            if filter_buttons: buttons.append(filter_buttons)
            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode in ['text', 'detailed']:
            page_files = filtered_files[offset : offset + limit]
            
            if mode == 'text': text = format_text_results(page_files, req, query.message.chat.id)
            else: text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            
            btn = []
            if filter_buttons: btn.append(filter_buttons)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn) 
            
            pagination = get_pagination_row(search_id, offset, limit, total_results, filter_type=filter_type)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except MessageNotModified:
        pass
    except Exception as e:
        traceback.print_exc()

# ==============================================================================
# 4. RESET & CARD HANDLERS (FIXED)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^unfilter_"))
async def handle_unfilter(client, query):
    # ❌ Removed `is_spam` check from Reset (Reset should always work)
    # ❌ Removed `query.answer` from here (Let handle_pagination do it)
    
    try:
        search_id = int(query.data.split("_")[1])
        # Manually create a redirect
        query.data = f"page_{search_id}_0"
        await handle_pagination(client, query)
    except: 
        # Fallback if redirect fails
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
