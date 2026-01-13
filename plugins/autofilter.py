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
from utils import (
    temp, 
    btn_parser, 
    format_text_results, 
    format_detailed_results, 
    format_card_result, 
    get_pagination_row,
    get_filter_buttons,       # ✅ UI Buttons Helper
    filter_by_database_type   # ✅ Strict DB Filter Helper
)

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
            caption = f"👋 Hᴇʏ fasion lovers, Yᴏᴜʀ Fɪʟᴛᴇʀ Fᴏʀ '{query}' Is Cʟᴏsᴇᴅ 📪\n\nTʜᴀɴᴋ Yᴏᴜ Fᴏʀ Usɪɴɢ! 🌟\nCᴏᴍᴇ Aɢᴀɪɴ! 😊👍"
            temp_msg = await user_message.reply_photo(photo=DELETE_IMG, caption=caption, quote=False)
            await asyncio.sleep(60)
            await temp_msg.delete()
    except: pass

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index", "set_shortner", "settings", "connect", "delreq"]))
async def auto_filter(client, message):
    raw_query = message.text

    if message.forward_from or message.forward_from_chat or message.via_bot: return
    if re.search(r"(https?://|www\.|t\.me/|@\w+)", raw_query): return
    NSFW_KEYWORDS = ["porn", "sex", "xxx", "nude", "horny", "gore", "adult", "dick", "pussy"]
    if any(word in raw_query.lower() for word in NSFW_KEYWORDS): return

    if len(raw_query) < 2: return

    clean_regex = r"\b(please|pls|plz|ples|send(\s+me)?|give|gib|find|chahiye|movie|new|latest|full\s+movie|file|link|hello|hi|bro|bhai|sir|bruh|hindi|tamil|malayalam|eng|with\s+subtitles|hd)\b"
    query = re.sub(clean_regex, "", raw_query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()
    if len(query) < 2: query = raw_query

    start_time = time.time()

    try:
        group_settings = await db.get_group_settings(message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        auto_react = group_settings.get('auto_reaction', False)
        auto_del_time = group_settings.get('auto_delete_time', 300)
        user_del = group_settings.get('auto_delete_user_msg', False)
        del_thanks = group_settings.get('delete_thanks_msg', True)

        await db.update_daily_stats(message.chat.id, 'req')

        files = await Media.get_search_results(query)
        end_time = time.time()
        time_taken = round(end_time - start_time, 2)

        if not files: return
        
        await db.update_daily_stats(message.chat.id, 'suc')
        unique_id = await Media.save_search_result(query, files)

        if auto_react:
            try: await message.react(random.choice(REACTIONS))
            except: pass 

        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        offset = 0 
        total_results = len(files)
        sent_msg = None 

        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # ✅ NEW: Generate Filter Buttons (Default: All)
        # Using '#' format: filter#{unique_id}#{active_mode}
        filter_buttons = get_filter_buttons(unique_id, "all")

        if mode == 'button':
            buttons = btn_parser(files, message.chat.id, unique_id, query=None, offset=offset, limit=limit)
            
            # Add Filter Rows
            for row in filter_buttons:
                buttons.append(row)

            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)

            msg_text = f"⚡ **Hey {message.from_user.mention}!**\n👻 **Here are your results for:** `{query}`\n⏳ **Time Taken:** {time_taken} seconds"
            sent_msg = await message.reply_text(text=msg_text, reply_markup=InlineKeyboardMarkup(buttons))

        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, query, message.chat.id)
            
            btn = []
            # Add Filter Rows
            for row in filter_buttons:
                btn.append(row)

            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)

            # Pass 'all' as default filter
            pagination = get_pagination_row(offset, limit, total_results, unique_id, "all")
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            # Add Filter Rows
            for row in filter_buttons:
                btn.append(row)
                
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)

            pagination = get_pagination_row(offset, limit, total_results, unique_id, "all")
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        elif mode == 'site':
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            final_site_url = f"{base_url}/results/{unique_id}"
            
            text = f"⚡ **Results for:** `{query}`\n📂 **Found:** {total_results} files\n⏳ **Time:** {time_taken}s\n\n👇 **Click the button below to view results online**"
            
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
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
                    InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{unique_id}_0")
                ])
            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))
            
        if sent_msg:
            if user_del:
                try: await message.delete()
                except: pass
            if auto_del_time > 0:
                asyncio.create_task(auto_delete_task(sent_msg, message, auto_del_time, del_thanks, query))

    except Exception as e:
        logger.error(f"Search Error: {e}")

# ==============================================================================
# 🎬 FILTER & UNFILTER HANDLER (Strict Type Logic)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^(filter|unfilter)#"))
async def media_type_filter_handler(client, query):
    try:
        # Data: action#unique_id#type#page
        data = query.data.split("#")
        action = data[0]
        unique_id = data[1]
        target_type = data[2] # video / document / all
        page = int(data[3])

        # 1. Fetch Session
        session = await Media.get_search_session(unique_id)
        if not session: 
            return await query.answer("❌ Search expired. Please search again.", show_alert=True)
            
        original_files = session['files']
        original_query = session['query']
        
        # 2. Strict Filter
        if action == "unfilter" or target_type == "all":
            final_files = original_files
            active_mode = "all"
        else:
            final_files = filter_by_database_type(original_files, target_type)
            active_mode = target_type

        if not final_files:
            return await query.answer(f"⚠️ No {target_type} files found!", show_alert=True)

        # 3. Settings
        settings = await db.get_group_settings(query.message.chat.id)
        mode = settings.get('result_mode', 'hybrid') if settings else 'hybrid'
        limit = settings.get('result_page_limit', 10) if settings else 10
        if mode == 'hybrid': mode = 'button' if len(final_files) <= limit else 'text'

        offset = page * limit
        total_results = len(final_files)

        howto_url = settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # 4. Generate Filter Buttons
        filter_rows = get_filter_buttons(unique_id, active_mode)

        if mode == 'button':
            buttons = btn_parser(final_files, query.message.chat.id, unique_id, query=None, offset=offset, limit=limit)
            
            # Append Filter Buttons
            for row in filter_rows:
                buttons.append(row)

            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)
            
            # Pagination (Includes active_mode)
            pagination = get_pagination_row(offset, limit, total_results, unique_id, active_mode)
            if pagination: buttons.append(pagination)

            header_text = f"⚡ **Results for:** `{original_query}`\n"
            if active_mode != "all":
                header_text += f"📂 **Filter:** {active_mode.capitalize()} Only ✅\n"
            header_text += f"🔢 **Found:** {total_results}"

            await query.message.edit_text(header_text, reply_markup=InlineKeyboardMarkup(buttons))

        elif mode == 'text':
            page_files = final_files[offset : offset + limit]
            text = format_text_results(page_files, original_query, query.message.chat.id)
            
            if active_mode != "all": 
                text = f"📂 **Filter:** {active_mode.capitalize()} Only ✅\n\n" + text
            
            btn = []
            for row in filter_rows:
                btn.append(row)
                
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, unique_id, active_mode)
            if pagination: btn.append(pagination)

            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Filter Logic Error: {e}")
        await query.answer("Error applying filter.", show_alert=True)

# ==============================================================================
# ⏭️ PAGINATION HANDLER (Persist Filter)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^next#"))
async def handle_next_back(client, query):
    try:
        # Data: next#{unique_id}#{offset}#{active_filter}
        data_parts = query.data.split("#")
        unique_id = data_parts[1]
        offset = int(data_parts[2])
        active_filter = data_parts[3] if len(data_parts) > 3 else "all"
        
        session = await Media.get_search_session(unique_id)
        if not session: return await query.answer("Expired.", show_alert=True)
        
        original_files = session['files']
        req = session['query']
        
        # Apply Filter
        if active_filter == "all":
            final_files = original_files
        else:
            final_files = filter_by_database_type(original_files, active_filter)
            
        total_results = len(final_files)
        
        settings = await db.get_group_settings(query.message.chat.id)
        mode = settings.get('result_mode', 'hybrid') if settings else 'hybrid'
        limit = settings.get('result_page_limit', 10) if settings else 10
        if mode == 'hybrid': mode = 'button' if len(final_files) <= limit else 'text'

        howto_url = settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # Generate Filter Buttons (Keep Checkmark active)
        filter_rows = get_filter_buttons(unique_id, active_filter)

        if mode == 'button':
            buttons = btn_parser(final_files, query.message.chat.id, unique_id, query=None, offset=offset, limit=limit)
            
            for row in filter_rows:
                buttons.append(row)

            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, unique_id, active_filter)
            if pagination: buttons.append(pagination)
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode == 'text':
            page_files = final_files[offset : offset + limit]
            text = format_text_results(page_files, req, query.message.chat.id)
            if active_filter != "all": 
                text = f"📂 **Filter:** {active_filter.capitalize()} Only ✅\n\n" + text
            
            btn = []
            for row in filter_rows:
                btn.append(row)

            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, unique_id, active_filter)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Pagination Error: {e}")
        await query.answer("Error switching page.", show_alert=True)

# Card Mode Handlers (No Changes needed, kept for compatibility)
@Client.on_callback_query(filters.regex(r"^card_next_"))
async def card_next_nav(client, query):
    # ... (Existing code for card next)
    pass 

@Client.on_callback_query(filters.regex(r"^card_prev_"))
async def card_prev_nav(client, query):
    # ... (Existing code for card prev)
    pass

@Client.on_callback_query(filters.regex(r"^pages$"))
async def page_counter_callback(client, query):
    await query.answer(f"Current Page Indicator", show_alert=False)
