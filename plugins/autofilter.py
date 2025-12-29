import logging
import time
import re
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import PORT, SITE_URL
# ✅ Import get_pagination_row from utils
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row

logger = logging.getLogger(__name__)

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index", "set_shortner", "settings", "connect", "delreq"]))
async def auto_filter(client, message):
    
    raw_query = message.text
    if len(raw_query) < 2: return

    # --- 🧹 CLEANING LOGIC ---
    clean_regex = r"\b(please|pls|plz|ples|send(\s+me)?|give|gib|find|chahiye|movie|new|latest|full\s+movie|file|link|hello|hi|bro|bhai|sir|bruh|hindi|tamil|malayalam|eng|with\s+subtitles|hd)\b"
    
    query = re.sub(clean_regex, "", raw_query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()
    
    if len(query) < 2:
        query = raw_query
    # -------------------------

    start_time = time.time()

    try:
        # ✅ 1. Get Group Settings
        group_settings = await db.get_group_settings(message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10

        # ✅ 2. Fetch Results
        files = await Media.get_search_results(query)
        
        end_time = time.time()
        time_taken = round(end_time - start_time, 2)

        if not files:
            return

        # ==================================================================
        # 🔀 MODE DISPATCHER
        # ==================================================================

        # --- HYBRID MODE LOGIC ---
        if mode == 'hybrid':
            if len(files) <= limit: mode = 'button'
            else: mode = 'text'

        # Pagination variables for Page 1
        offset = 0 
        total_results = len(files)

        # --- MODE A: BUTTON ---
        if mode == 'button':
            # btn_parser now handles pagination internally if offset/limit is passed
            buttons = btn_parser(files, message.chat.id, query, offset, limit)
            
            msg_text = (
                f"⚡ **Hey {message.from_user.mention}!**\n"
                f"👻 **Here are your results for:** `{query}`\n"
                f"⏳ **Time Taken:** {time_taken} seconds"
            )
            await message.reply_text(
                text=msg_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # --- MODE B: TEXT LIST ---
        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, query, message.chat.id)
            
            # Add Pagination Row
            btn = []
            pagination = get_pagination_row(offset, limit, total_results, query)
            if pagination: btn.append(pagination)
            
            await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE C: DETAILED LIST ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            # Add Pagination Row
            btn = []
            pagination = get_pagination_row(offset, limit, total_results, query)
            if pagination: btn.append(pagination)
            
            await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE D: SITE (WEB VIEW) ---
        elif mode == 'site':
            # Save to MongoDB
            search_id = await Media.save_search_results(query, files, message.chat.id)
            
            # Construct Link
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            final_site_url = f"{base_url}/results/{search_id}"
            
            text = (
                f"⚡ **Results for:** `{query}`\n"
                f"📂 **Found:** {total_results} files\n"
                f"⏳ **Time:** {time_taken}s\n\n"
                f"👇 **Click the button below to view results online**"
            )
            
            # Main Button
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            
            # Add Pagination Row (Updates the Link in Next/Prev)
            pagination = get_pagination_row(offset, limit, total_results, query)
            if pagination: btn.append(pagination)
            
            await message.reply_text(
                text, 
                reply_markup=InlineKeyboardMarkup(btn)
            )

        # --- MODE E: CARD (Single Result) ---
        elif mode == 'card':
            # Card mode has its own specific pagination logic
            file = files[0]
            text = format_card_result(file, 0, total_results)
            
            btn = []
            link_id = file['link_id']
            chat_id = message.chat.id
            btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])

            if total_results > 1:
                short_q = query[:20] 
                btn.append([
                    InlineKeyboardButton(f"1/{total_results}", callback_data="pages"),
                    InlineKeyboardButton("Next ➡️", callback_data=f"card_next_0_{short_q}")
                ])

            await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Search Error: {e}")

# ==============================================================================
# ⏭️ PAGINATION CALLBACK HANDLER (Next/Back Logic)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        # Callback Data Format: next_{offset}_{req}
        _, offset, req = query.data.split("_", 2) 
        offset = int(offset)
        
        # 1. Fetch Files Again (Stateless)
        files = await Media.get_search_results(req)
        if not files:
            return await query.answer("❌ Search expired or no files found.", show_alert=True)
            
        total_results = len(files)
        
        # 2. Get Settings Again (To check for updates)
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10

        # Adjust Mode for Hybrid
        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        # 3. Generate New Content
        
        # --- BUTTON MODE ---
        if mode == 'button':
            buttons = btn_parser(files, query.message.chat.id, req, offset, limit)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        # --- TEXT MODE ---
        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, req, query.message.chat.id)
            
            btn = []
            pagination = get_pagination_row(offset, limit, total_results, req)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(
                text, 
                disable_web_page_preview=True, 
                reply_markup=InlineKeyboardMarkup(btn) if btn else None
            )

        # --- DETAILED MODE ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            # Time taken passed as 0 or empty for edits
            text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            
            btn = []
            pagination = get_pagination_row(offset, limit, total_results, req)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(
                text, 
                disable_web_page_preview=True, 
                reply_markup=InlineKeyboardMarkup(btn) if btn else None
            )

        # --- SITE MODE ---
        elif mode == 'site':
            # For site mode pagination, we generate a new ID and link pointing to the specific page
            search_id = await Media.save_search_results(req, files, query.message.chat.id)
            
            # Calculate Page Number
            page_no = int(offset / limit) + 1
            
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            final_site_url = f"{base_url}/results/{search_id}?page={page_no}"
            
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            
            pagination = get_pagination_row(offset, limit, total_results, req)
            if pagination: btn.append(pagination)
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Pagination Error: {e}")
        await query.answer("⚠️ Error switching page.", show_alert=True)

# Card Mode Handlers (Existing)
@Client.on_callback_query(filters.regex(r"^card_next_"))
async def card_next_nav(client, query):
    try:
        _, _, index, q_text = query.data.split("_", 3) 
        current_index = int(index)
        files = await Media.get_search_results(q_text)
        if not files: return await query.answer("Expired.", show_alert=True)
        total = len(files)
        next_index = current_index + 1
        if next_index >= total: next_index = 0
        file = files[next_index]
        text = format_card_result(file, next_index, total)
        btn = []
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])
        nav_row = []
        if next_index > 0: nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{next_index}_{q_text}"))
        nav_row.append(InlineKeyboardButton(f"{next_index + 1}/{total}", callback_data="pages"))
        if next_index < total - 1: nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{next_index}_{q_text}"))
        btn.append(nav_row)
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e: await query.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^card_prev_"))
async def card_prev_nav(client, query):
    try:
        _, _, index, q_text = query.data.split("_", 3)
        current_index = int(index)
        files = await Media.get_search_results(q_text)
        if not files: return await query.answer("Expired.", show_alert=True)
        total = len(files)
        prev_index = current_index - 1
        if prev_index < 0: prev_index = total - 1
        file = files[prev_index]
        text = format_card_result(file, prev_index, total)
        btn = []
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])
        nav_row = []
        if prev_index > 0: nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{prev_index}_{q_text}"))
        nav_row.append(InlineKeyboardButton(f"{prev_index + 1}/{total}", callback_data="pages"))
        if prev_index < total - 1: nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{prev_index}_{q_text}"))
        btn.append(nav_row)
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e: await query.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^pages$"))
async def page_counter_callback(client, query):
    await query.answer(f"Current Page Indicator", show_alert=False)
