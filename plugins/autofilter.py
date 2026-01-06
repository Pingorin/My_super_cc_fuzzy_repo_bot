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
# ✅ Added filter_by_type
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row, get_qualities, get_languages, get_years, get_size_ranges, filter_by_type

logger = logging.getLogger(__name__)

# ✅ CONSTANTS
REACTIONS = ["👍", "❤️", "🔥", "🥰", "👏", "😁", "🎉", "🤩"]
DELETE_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg"

# ... (auto_delete_task remains the same) ...
async def auto_delete_task(bot_message, user_message, delay, show_thanks, query="files"):
    if delay <= 0: return 
    await asyncio.sleep(delay)
    try:
        await bot_message.delete()
        if show_thanks:
            caption = (
                f"👋 Hᴇʏ fasion lovers, Yᴏᴜʀ Fɪʟᴛᴇʀ Fᴏʀ '{query}' Is Cʟᴏsᴇᴅ 📪\n\n"
                f"Tʜᴀɴᴋ Yᴏᴜ Fᴏʀ Usɪɴɢ! 🌟\n"
                f"Cᴏᴍᴇ Aɢᴀɪɴ! 😊👍"
            )
            temp_msg = await user_message.reply_photo(photo=DELETE_IMG, caption=caption, quote=False)
            await asyncio.sleep(60)
            await temp_msg.delete()
    except Exception as e:
        pass

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index", "set_shortner", "settings", "connect", "delreq"]))
async def auto_filter(client, message):
    
    raw_query = message.text

    # ... (Anti-Spam & Cleaning Logic remains same) ...
    if message.forward_from or message.forward_from_chat or message.via_bot: return
    if re.search(r"(https?://|www\.|t\.me/|@\w+)", raw_query): return
    NSFW_KEYWORDS = ["porn", "sex", "xxx", "nude", "horny", "gore", "adult", "dick", "pussy"]
    if any(word in raw_query.lower() for word in NSFW_KEYWORDS): return
    if len(raw_query) < 2: return

    clean_regex = r"\b(please|pls|plz|ples|send(\s+me)?|give|gib|find|chahiye|movie|new|latest|full\s+movie|file|link|hello|hi|bro|bhai|sir|bruh|hindi|tamil|malayalam|eng|with\s+subtitles|hd)\b"
    query = re.sub(clean_regex, "", raw_query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()
    if len(query) < 2: query = raw_query

    try:
        group_settings = await db.get_group_settings(message.chat.id)
        # ... (Settings fetch logic remains same) ...
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        auto_react = group_settings.get('auto_reaction', False)
        auto_del_time = group_settings.get('auto_delete_time', 300)
        howto_url = group_settings.get('howto_url')

        await db.update_daily_stats(message.chat.id, 'req')

        files = await Media.get_search_results(query)
        if not files: return
            
        await db.update_daily_stats(message.chat.id, 'suc')
        if auto_react:
            try: await message.react(random.choice(REACTIONS))
            except: pass 

        # ==================================================================
        # 🌟 BUTTON GENERATION LOGIC
        # ==================================================================
        
        extra_btn = []
        
        # 1. How To Button
        if howto_url:
            extra_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        
        # 2. ✅ NEW: Media Type Filter (Row 0 - Above Language)
        # Data: filter_sel#{query}#{Qual}#{Lang}#{Year}#{Size}#{Type}
        # Initially Type is 'None'
        row_media = [
            InlineKeyboardButton("Videos", callback_data=f"filter_sel#{query}#None#None#None#None#Videos"),
            InlineKeyboardButton("Docs", callback_data=f"filter_sel#{query}#None#None#None#None#Docs")
        ]
        extra_btn.append(row_media)

        # 3. Filter Row 1 (Quality | Language)
        row1 = [
            InlineKeyboardButton("Select Qualities 🔽", callback_data=f"qual_menu#{query}#None#None#None#None#None"),
            InlineKeyboardButton("Select Language 🔽", callback_data=f"lang_menu#{query}#None#None#None#None#None")
        ]
        extra_btn.append(row1)

        # 4. Filter Row 2 (Year | Size)
        row2 = [
            InlineKeyboardButton("Select Year 🔽", callback_data=f"year_menu#{query}#None#None#None#None#None"),
            InlineKeyboardButton("Select Size 🔽", callback_data=f"size_menu#{query}#None#None#None#None#None")
        ]
        extra_btn.append(row2)

        # 5. Free Premium
        extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])

        # Pagination
        offset = 0
        total_results = len(files)
        
        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        # Pass filters: query#Qual#Lang#Year#Size#Type
        page_btn = get_pagination_row(offset, limit, total_results, f"{query}#None#None#None#None#None")

        final_markup = []
        text = ""
        sent_msg = None

        if mode == 'button':
            final_markup = btn_parser(files, message.chat.id, query, offset, limit)
            text = f"⚡ Results for `{query}`"
            final_markup.extend(extra_btn)
            if page_btn: final_markup.append(page_btn)
            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(final_markup))
        
        elif mode in ['text', 'detailed', 'site']:
            # ... (Existing Text/Site mode logic, ensure buttons are passed) ...
            page_files = files[offset : offset + limit]
            
            if mode == 'text': text = format_text_results(page_files, query, message.chat.id)
            elif mode == 'detailed': text = format_detailed_results(page_files, query, message.chat.id, 0)
            elif mode == 'site':
                search_id = await Media.save_search_results(query, files, message.chat.id)
                final_site_url = f"{SITE_URL}/results/{search_id}"
                text = f"⚡ **Results for:** `{query}`\n📂 **Found:** {total_results} files\n👇 **Click below to view online**"
                final_markup = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]

            buttons = []
            if mode == 'site': buttons.extend(final_markup)
            buttons.extend(extra_btn)
            if page_btn: buttons.append(page_btn)
            
            sent_msg = await message.reply_text(
                text, 
                disable_web_page_preview=True, 
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )

        if sent_msg and auto_del_time > 0:
            asyncio.create_task(auto_delete_task(sent_msg, message, auto_del_time, False, query))

    except Exception as e:
        logger.error(f"Search Error: {e}")

# ==============================================================================
# 🌟 FILTER MENU HANDLERS (UPDATED FOR TYPE ARGUMENT)
# ==============================================================================

# --- QUALITY MENU ---
@Client.on_callback_query(filters.regex(r"^qual_menu#"))
async def quality_menu_handler(client, query):
    # Data: qual_menu#{query}#{Qual}#{Lang}#{Year}#{Size}#{Type}
    parts = query.data.split("#")
    req_query, curr_qual, curr_lang, curr_year, curr_size, curr_type = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
    
    files = await Media.get_search_results(req_query)
    # Apply filters
    if curr_lang != "None": files = filter_by_lang(files, curr_lang)
    if curr_year != "None": files = filter_by_year(files, curr_year)
    if curr_size != "None": files = filter_by_size(files, curr_size)
    if curr_type != "None": files = filter_by_type(files, curr_type) # ✅

    qual_data = get_qualities(files)
    if not qual_data: return await query.answer("No specific qualities detected.", show_alert=True)
    
    buttons = []
    temp_row = []
    for qual, count in qual_data.items():
        btn_txt = f"{qual.upper()} ({count})"
        temp_row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_sel#{req_query}#{qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}"))
        if len(temp_row) == 3:
            buttons.append(temp_row)
            temp_row = []
    if temp_row: buttons.append(temp_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}")])
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# --- LANGUAGE MENU ---
@Client.on_callback_query(filters.regex(r"^lang_menu#"))
async def language_menu_handler(client, query):
    parts = query.data.split("#")
    req_query, curr_qual, curr_lang, curr_year, curr_size, curr_type = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
    
    files = await Media.get_search_results(req_query)
    if curr_qual != "None": files = filter_by_quality(files, curr_qual)
    if curr_year != "None": files = filter_by_year(files, curr_year)
    if curr_size != "None": files = filter_by_size(files, curr_size)
    if curr_type != "None": files = filter_by_type(files, curr_type) # ✅

    lang_data = get_languages(files)
    if not lang_data: return await query.answer("No specific languages detected.", show_alert=True)
    
    buttons = []
    temp_row = []
    for lang, count in lang_data.items():
        btn_txt = f"{lang} ({count})"
        temp_row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_sel#{req_query}#{curr_qual}#{lang}#{curr_year}#{curr_size}#{curr_type}"))
        if len(temp_row) == 3:
            buttons.append(temp_row)
            temp_row = []
    if temp_row: buttons.append(temp_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}")])
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# --- YEAR MENU ---
@Client.on_callback_query(filters.regex(r"^year_menu#"))
async def year_menu_handler(client, query):
    parts = query.data.split("#")
    req_query, curr_qual, curr_lang, curr_year, curr_size, curr_type = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
    
    files = await Media.get_search_results(req_query)
    if curr_qual != "None": files = filter_by_quality(files, curr_qual)
    if curr_lang != "None": files = filter_by_lang(files, curr_lang)
    if curr_size != "None": files = filter_by_size(files, curr_size)
    if curr_type != "None": files = filter_by_type(files, curr_type) # ✅

    year_data = get_years(files)
    if not year_data: return await query.answer("No specific years detected.", show_alert=True)
    
    buttons = []
    temp_row = []
    for year, count in year_data.items():
        btn_txt = f"{year}" 
        temp_row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{year}#{curr_size}#{curr_type}"))
        if len(temp_row) == 3:
            buttons.append(temp_row)
            temp_row = []
    if temp_row: buttons.append(temp_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}")])
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# --- SIZE MENU ---
@Client.on_callback_query(filters.regex(r"^size_menu#"))
async def size_menu_handler(client, query):
    parts = query.data.split("#")
    req_query, curr_qual, curr_lang, curr_year, curr_size, curr_type = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]
    
    files = await Media.get_search_results(req_query)
    # Apply other filters
    if curr_qual != "None": files = filter_by_quality(files, curr_qual)
    if curr_lang != "None": files = filter_by_lang(files, curr_lang)
    if curr_year != "None": files = filter_by_year(files, curr_year)
    if curr_type != "None": files = filter_by_type(files, curr_type) # ✅

    size_ranges = get_size_ranges(files)
    if not size_ranges: return await query.answer("No files found.", show_alert=True)
    
    buttons = []
    temp_row = []
    for size_cat in size_ranges:
        temp_row.append(InlineKeyboardButton(size_cat, callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{size_cat}#{curr_type}"))
        if len(temp_row) == 2: 
            buttons.append(temp_row)
            temp_row = []
    if temp_row: buttons.append(temp_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}")])
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🎯 MASTER SELECTION HANDLER (UPDATED)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^filter_sel#"))
async def filter_selection_handler(client, query):
    # Data: filter_sel#{query}#{qual}#{lang}#{year}#{size}#{type}
    parts = query.data.split("#")
    req_query, sel_qual, sel_lang, sel_year, sel_size, sel_type = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6]

    # Toggle Logic for Media Type
    # If user clicked "Videos" and it is already "Videos", reset to "None"
    # Actually, the button generator below decides what callback data to put.
    # Here we just execute the filter provided in `sel_type`.
    
    # 1. Fetch & Filter
    files = await Media.get_search_results(req_query)
    if sel_qual != "None": files = filter_by_quality(files, sel_qual)
    if sel_lang != "None": files = filter_by_lang(files, sel_lang)
    if sel_year != "None": files = filter_by_year(files, sel_year)
    if sel_size != "None": files = filter_by_size(files, sel_size)
    if sel_type != "None": files = filter_by_type(files, sel_type) # ✅
             
    if not files: return await query.answer("No files found for this combination.", show_alert=True)

    # 2. Build Response
    total_results = len(files)
    limit = 10
    offset = 0
    group_settings = await db.get_group_settings(query.message.chat.id)
    mode = group_settings.get('result_mode', 'hybrid')
    howto_url = group_settings.get('howto_url')
    
    if mode == 'hybrid':
        mode = 'button' if len(files) <= limit else 'text'

    # 3. Build Buttons
    extra_btn = []
    if howto_url: extra_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])

    # --- ROW 0: Media Type (Videos | Docs) ---
    # Logic: If Videos selected, button shows "Videos ✅" and clicking it resets to None (All)
    # If Docs selected, button shows "Docs ✅" and clicking it resets to None
    
    vid_txt = "Videos ✅" if sel_type == "Videos" else "Videos"
    doc_txt = "Docs ✅" if sel_type == "Docs" else "Docs"
    
    # If currently Videos, clicking Videos button -> None (Reset). Clicking Docs -> Docs
    vid_data = "None" if sel_type == "Videos" else "Videos"
    doc_data = "None" if sel_type == "Docs" else "Docs"
    
    row_media = [
        InlineKeyboardButton(vid_txt, callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{vid_data}"),
        InlineKeyboardButton(doc_txt, callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{doc_data}")
    ]
    extra_btn.append(row_media)

    # --- ROW 1: Quality & Language ---
    row1 = []
    q_txt = "Select Qualities 🔽" if sel_qual == "None" else f"{sel_qual.upper()} ✅"
    row1.append(InlineKeyboardButton(q_txt, callback_data=f"qual_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}"))
    l_txt = "Select Language 🔽" if sel_lang == "None" else f"{sel_lang} ✅"
    row1.append(InlineKeyboardButton(l_txt, callback_data=f"lang_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}"))
    extra_btn.append(row1)

    # --- ROW 2: Year & Size ---
    row2 = []
    y_txt = "Select Year 🔽" if sel_year == "None" else f"{sel_year} ✅"
    row2.append(InlineKeyboardButton(y_txt, callback_data=f"year_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}"))
    s_txt = "Select Size 🔽" if sel_size == "None" else f"{sel_size} ✅"
    row2.append(InlineKeyboardButton(s_txt, callback_data=f"size_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}"))
    extra_btn.append(row2)

    # --- ROW 3: Reset Buttons ---
    reset_row = []
    if sel_qual != "None": reset_row.append(InlineKeyboardButton("All Qualities 🔄", callback_data=f"filter_sel#{req_query}#None#{sel_lang}#{sel_year}#{sel_size}#{sel_type}"))
    if sel_lang != "None": reset_row.append(InlineKeyboardButton("All Languages 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#None#{sel_year}#{sel_size}#{sel_type}"))
    if reset_row: extra_btn.append(reset_row)
    
    reset_row_2 = []
    if sel_year != "None": reset_row_2.append(InlineKeyboardButton("All Years 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#None#{sel_size}#{sel_type}"))
    if sel_size != "None": reset_row_2.append(InlineKeyboardButton("All Sizes 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#None#{sel_type}"))
    if reset_row_2: extra_btn.append(reset_row_2)
    
    # Media Reset Button (Optional, but "All Media Types" logic is handled by clicking the Active button)
    if sel_type != "None":
         extra_btn.append([InlineKeyboardButton("All Media Types 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#None")])

    extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
    
    # Pagination
    page_btn = get_pagination_row(offset, limit, total_results, f"{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}")

    # 4. Generate Output
    final_markup = []
    text = f"⚡ Results for `{req_query}`"
    if sel_type != "None": text += f"\n📂 **Type:** {sel_type}"
    if sel_qual != "None": text += f"\n📀 **Quality:** {sel_qual.upper()}"
    if sel_lang != "None": text += f"\n🗣️ **Language:** {sel_lang}"
    if sel_year != "None": text += f"\n📅 **Year:** {sel_year}"
    if sel_size != "None": text += f"\n💾 **Size:** {sel_size}"

    if mode == 'button':
        final_markup = btn_parser(files, query.message.chat.id, req_query, offset, limit)
        final_markup.extend(extra_btn)
        if page_btn: final_markup.append(page_btn)
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(final_markup))
        
    elif mode in ['text', 'detailed', 'site']:
        page_files = files[offset : offset + limit]
        if mode == 'text': text = format_text_results(page_files, req_query, query.message.chat.id)
        elif mode == 'detailed': text = format_detailed_results(page_files, req_query, query.message.chat.id, 0)
        elif mode == 'site':
            search_id = await Media.save_search_results(req_query, files, query.message.chat.id)
            text = f"⚡ Results for `{req_query}`\n📂 Found: {total_results}"
            final_markup = [[InlineKeyboardButton("🔎 View Results Online", url=f"{SITE_URL}/results/{search_id}")]]

        buttons = []
        if mode == 'site': buttons.extend(final_markup)
        buttons.extend(extra_btn)
        if page_btn: buttons.append(page_btn)
        
        await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# ⏭️ PAGINATION HANDLER (UPDATED)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        raw_data = query.data.split("_", 2)
        offset = int(raw_data[1])
        remainder = raw_data[2]
        
        # Format: query#Qual#Lang#Year#Size#Type
        if "#" in remainder:
            parts = remainder.split("#")
            req_query = parts[0]
            sel_qual = parts[1]
            sel_lang = parts[2] if len(parts) > 2 else "None"
            sel_year = parts[3] if len(parts) > 3 else "None"
            sel_size = parts[4] if len(parts) > 4 else "None"
            sel_type = parts[5] if len(parts) > 5 else "None" # ✅
        else:
            req_query = remainder
            sel_qual = "None"
            sel_lang = "None"
            sel_year = "None"
            sel_size = "None"
            sel_type = "None"
            
        files = await Media.get_search_results(req_query)
        if sel_qual != "None": files = filter_by_quality(files, sel_qual)
        if sel_lang != "None": files = filter_by_lang(files, sel_lang)
        if sel_year != "None": files = filter_by_year(files, sel_year)
        if sel_size != "None": files = filter_by_size(files, sel_size)
        if sel_type != "None": files = filter_by_type(files, sel_type) # ✅
        
        total_results = len(files)
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid')
        limit = group_settings.get('result_page_limit', 10)
        howto_url = group_settings.get('howto_url')
        
        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        extra_btn = []
        if howto_url: extra_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        
        # --- ROW 0: Media Type ---
        vid_txt = "Videos ✅" if sel_type == "Videos" else "Videos"
        doc_txt = "Docs ✅" if sel_type == "Docs" else "Docs"
        vid_data = "None" if sel_type == "Videos" else "Videos"
        doc_data = "None" if sel_type == "Docs" else "Docs"
        
        row_media = [
            InlineKeyboardButton(vid_txt, callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{vid_data}"),
            InlineKeyboardButton(doc_txt, callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{doc_data}")
        ]
        extra_btn.append(row_media)

        # --- ROW 1 ---
        row1 = []
        q_txt = "Select Qualities 🔽" if sel_qual == "None" else f"{sel_qual.upper()} ✅"
        row1.append(InlineKeyboardButton(q_txt, callback_data=f"qual_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}"))
        l_txt = "Select Language 🔽" if sel_lang == "None" else f"{sel_lang} ✅"
        row1.append(InlineKeyboardButton(l_txt, callback_data=f"lang_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}"))
        extra_btn.append(row1)

        # --- ROW 2 ---
        row2 = []
        y_txt = "Select Year 🔽" if sel_year == "None" else f"{sel_year} ✅"
        row2.append(InlineKeyboardButton(y_txt, callback_data=f"year_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}"))
        s_txt = "Select Size 🔽" if sel_size == "None" else f"{sel_size} ✅"
        row2.append(InlineKeyboardButton(s_txt, callback_data=f"size_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}"))
        extra_btn.append(row2)

        # --- ROW 3: Resets ---
        reset_row = []
        if sel_qual != "None": reset_row.append(InlineKeyboardButton("All Qualities 🔄", callback_data=f"filter_sel#{req_query}#None#{sel_lang}#{sel_year}#{sel_size}#{sel_type}"))
        if sel_lang != "None": reset_row.append(InlineKeyboardButton("All Languages 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#None#{sel_year}#{sel_size}#{sel_type}"))
        if reset_row: extra_btn.append(reset_row)
        
        reset_row_2 = []
        if sel_year != "None": reset_row_2.append(InlineKeyboardButton("All Years 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#None#{sel_size}#{sel_type}"))
        if sel_size != "None": reset_row_2.append(InlineKeyboardButton("All Sizes 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#None#{sel_type}"))
        if reset_row_2: extra_btn.append(reset_row_2)

        if sel_type != "None":
             extra_btn.append([InlineKeyboardButton("All Media Types 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#None")])
        
        extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
        
        page_btn = get_pagination_row(offset, limit, total_results, f"{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}")
        
        if mode == 'button':
            buttons = btn_parser(files, query.message.chat.id, req_query, offset, limit)
            buttons.extend(extra_btn)
            if page_btn: buttons.append(page_btn)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode in ['text', 'detailed']:
            # ... (Existing Text mode logic) ...
            page_files = files[offset : offset + limit]
            if mode == 'text': text = format_text_results(page_files, req_query, query.message.chat.id)
            else: text = format_detailed_results(page_files, req_query, query.message.chat.id, 0)
            
            buttons = []
            buttons.extend(extra_btn)
            if page_btn: buttons.append(page_btn)
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(buttons))
            
    except Exception as e:
        logger.error(f"Pagination Error: {e}")

# ... (Rest of existing filters like filter_by_quality, etc.) ...
def filter_by_quality(files, quality):
    key = quality.lower()
    if key == "4k": return [f for f in files if "4k" in f['file_name'].lower() or "2160p" in f['file_name'].lower()]
    return [f for f in files if key in f['file_name'].lower()]

def filter_by_lang(files, language):
    lang_map = {
        "Hindi": ["hindi", "hin", "hind"], "English": ["english", "eng"], "Tamil": ["tamil", "tam"],
        "Telugu": ["telugu", "tel"], "Malayalam": ["malayalam", "mal"], "Kannada": ["kannada", "kan"],
        "Bengali": ["bengali", "ben"], "Punjabi": ["punjabi", "pun"], "Urdu": ["urdu"],
        "Dual": ["dual"], "Multi": ["multi"]
    }
    keywords = lang_map.get(language, [language.lower()])
    filtered = []
    for f in files:
        name = f['file_name'].lower()
        if any(k in name for k in keywords): filtered.append(f)
    return filtered

def filter_by_year(files, year):
    return [f for f in files if str(year) in f['file_name']]

def filter_by_size(files, size_cat):
    filtered = []
    for f in files:
        size = f.get('file_size', 0)
        if size_cat == "<500MB" and size < 524288000: filtered.append(f)
        elif size_cat == "500MB-1GB" and 524288000 <= size < 1073741824: filtered.append(f)
        elif size_cat == "1GB-2GB" and 1073741824 <= size < 2147483648: filtered.append(f)
        elif size_cat == ">2GB" and size >= 2147483648: filtered.append(f)
    return filtered
