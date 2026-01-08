import logging
import time
import re
import random 
import asyncio 
import urllib.parse
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import PORT, SITE_URL, ADMINS
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row, get_qualities, get_languages, get_years, get_size_ranges

logger = logging.getLogger(__name__)

# ✅ CONSTANTS
REACTIONS = ["👍", "❤️", "🔥", "🥰", "👏", "😁", "🎉", "🤩"]
DELETE_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg"

# ==============================================================================
# 🧩 FILTER LOGIC HELPERS
# ==============================================================================

def filter_by_type(files, f_type):
    if f_type == "None": return files
    filtered = []
    for f in files:
        db_type = f.get('file_type', 'document').lower()
        if f_type == "Video" and db_type == "video": filtered.append(f)
        elif f_type == "Document" and db_type == "document": filtered.append(f)
    return filtered

def filter_by_quality(files, quality):
    if quality == "None": return files
    key = quality.lower()
    if key == "4k": return [f for f in files if "4k" in f['file_name'].lower() or "2160p" in f['file_name'].lower()]
    return [f for f in files if key in f['file_name'].lower()]

def filter_by_lang(files, language):
    if language == "None": return files
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
    if year == "None": return files
    return [f for f in files if str(year) in f['file_name']]

def filter_by_size(files, size_cat):
    if size_cat == "None": return files
    filtered = []
    for f in files:
        size = f.get('file_size', 0)
        if size_cat == "<500MB" and size < 524288000: filtered.append(f)
        elif size_cat == "500MB-1GB" and 524288000 <= size < 1073741824: filtered.append(f)
        elif size_cat == "1GB-2GB" and 1073741824 <= size < 2147483648: filtered.append(f)
        elif size_cat == ">2GB" and size >= 2147483648: filtered.append(f)
    return filtered

# ✅ HELPER: Auto-Delete Logic
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

# ==============================================================================
# 🚀 MAIN AUTO FILTER HANDLER
# ==============================================================================

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

    try:
        group_settings = await db.get_group_settings(message.chat.id)
        
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        auto_react = group_settings.get('auto_reaction', False)
        auto_del_time = group_settings.get('auto_delete_time', 300)
        user_del = group_settings.get('auto_delete_user_msg', False)
        del_thanks = group_settings.get('delete_thanks_msg', True)        
        howto_url = group_settings.get('howto_url')

        await db.update_daily_stats(message.chat.id, 'req')

        files = await Media.get_search_results(query, sort_mode="relevance")
        if not files: return
            
        await db.update_daily_stats(message.chat.id, 'suc')
        if auto_react:
            try: await message.react(random.choice(REACTIONS))
            except: pass 

        # ==================================================================
        # 🌟 BUTTON GENERATION LOGIC
        # ==================================================================
        
        extra_btn = []
        
        if howto_url:
            extra_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        
        # ROW 1: Media Type
        media_row = [
            InlineKeyboardButton("Videos", callback_data=f"filter_sel#{query}#None#None#None#None#Video#relevance"),
            InlineKeyboardButton("Docs", callback_data=f"filter_sel#{query}#None#None#None#None#Document#relevance")
        ]
        extra_btn.append(media_row)

        # ROW 2: Quality | Language
        row2 = [
            InlineKeyboardButton("Select Qualities 🔽", callback_data=f"qual_menu#{query}#None#None#None#None#None#relevance"),
            InlineKeyboardButton("Select Language 🔽", callback_data=f"lang_menu#{query}#None#None#None#None#None#relevance")
        ]
        extra_btn.append(row2)

        # ROW 3: Year | Size
        row3 = [
            InlineKeyboardButton("Select Year 🔽", callback_data=f"year_menu#{query}#None#None#None#None#None#relevance"),
            InlineKeyboardButton("Select Size 🔽", callback_data=f"size_menu#{query}#None#None#None#None#None#relevance")
        ]
        extra_btn.append(row3)

        # ROW 4: Sort
        extra_btn.append([InlineKeyboardButton("Sort By Files 🔽", callback_data=f"sort_menu#{query}#None#None#None#None#None#relevance")])

        # ✅ ROW 5: PROGRESSIVE RE-CHECK (STEP 0)
        # This triggers the smart search workflow
        extra_btn.append([InlineKeyboardButton("😕 Wrong Result? Click Here", callback_data=f"recheck#1#{query}")])

        # Free Premium
        extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])

        offset = 0
        total_results = len(files)
        
        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        page_btn = get_pagination_row(offset, limit, total_results, f"{query}#None#None#None#None#None#relevance")

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
            asyncio.create_task(auto_delete_task(sent_msg, message, auto_del_time, group_settings.get('delete_thanks_msg', True), query))

    except Exception as e:
        logger.error(f"Search Error: {e}")

# ==============================================================================
# 🕵️ PROGRESSIVE RE-CHECK HANDLER (SMART SEARCH)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^recheck#"))
async def recheck_handler(client, query):
    try:
        # Data format: recheck#{step}#{original_query}
        parts = query.data.split("#")
        step = int(parts[1])
        original_query = parts[2]
        
        new_query = original_query
        next_button_text = ""
        next_step = step + 1
        logic_used = ""

        # --- LOGIC STEPS ---
        if step == 1:
            # 1. Dots Logic: Replace spaces with dots
            new_query = original_query.replace(" ", ".")
            next_button_text = "🤔 Still Wrong? Click Here"
            logic_used = "Dots Logic"
            
        elif step == 2:
            # 2. Cleaner Logic: Regex to remove noise
            new_query = re.sub(r"\b(S\d+|E\d+|Season \d+|Episode \d+|\d{4}|480p|720p|1080p|2160p|Hindi|Eng|Dual Audio)\b", "", original_query, flags=re.IGNORECASE)
            new_query = re.sub(r"\s+", " ", new_query).strip()
            next_button_text = "Try Different Search"
            logic_used = "Cleaner Logic"
            
        elif step == 3:
            # 3. Longest Word Logic: Find the most significant word
            words = re.findall(r"\w+", original_query)
            if words:
                # Remove common small words to find the "real" title
                stopwords = ['the', 'and', 'with', 'for', 'mov', 'movie']
                clean_words = [w for w in words if w.lower() not in stopwords and len(w) > 2]
                if clean_words:
                    new_query = max(clean_words, key=len)
                else:
                    new_query = max(words, key=len)
            next_button_text = "Last Try"
            logic_used = "Longest Word Logic"
            
        elif step == 4:
            # 4. First Word Logic: Last resort
            words = original_query.split()
            if words:
                new_query = words[0]
            next_button_text = "None"
            logic_used = "First Word Logic"

        # --- PERFORM SEARCH ---
        files = await Media.get_search_results(new_query)
        
        # --- IF NO RESULTS, FORCE NEXT STEP OR FAIL ---
        if not files:
            if step < 4:
                # Recursively call next step immediately
                query.data = f"recheck#{next_step}#{original_query}"
                return await recheck_handler(client, query)
            else:
                # All steps failed -> Google Fallback
                google_url = f"https://www.google.com/search?q={urllib.parse.quote(original_query)}"
                req_link = f"https://t.me/{temp.U_NAME}?start=request" # Fallback link
                
                btn = [
                    [InlineKeyboardButton("🌐 Google Spelling Check", url=google_url)],
                    [InlineKeyboardButton("⚠️ Request This File", url=req_link)],
                    [InlineKeyboardButton("❌ Close", callback_data="close_data")]
                ]
                return await query.message.edit_text(
                    f"😕 **No results found.**\n\nI tried everything! Please check your spelling on Google or Request the file.\n\nLogic Used: {logic_used}",
                    reply_markup=InlineKeyboardMarkup(btn)
                )

        # --- BUILD BUTTONS FOR SUCCESS ---
        group_settings = await db.get_group_settings(query.message.chat.id)
        limit = group_settings.get('result_page_limit', 10)
        mode = group_settings.get('result_mode', 'hybrid')
        if mode == 'hybrid': mode = 'button' if len(files) <= limit else 'text'

        # Generate File Buttons
        buttons = btn_parser(files, query.message.chat.id, new_query, 0, limit)
        
        # Add the Next Progressive Button
        if step < 4:
            buttons.append([InlineKeyboardButton(next_button_text, callback_data=f"recheck#{next_step}#{original_query}")])
        else:
            # If Step 4 (Last Try), show Request Button
            req_link = f"https://t.me/{temp.U_NAME}?start=request"
            buttons.append([InlineKeyboardButton("⚠️ Request This File", url=req_link)])

        # Always offer Google Check in recheck mode
        google_url = f"https://www.google.com/search?q={urllib.parse.quote(original_query)}"
        buttons.append([InlineKeyboardButton("🌐 Google Check", url=google_url)])

        text = f"🔄 **Smart Re-Check ({logic_used})**\n🔎 Query: `{new_query}`\n📂 Found: {len(files)}"

        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

    except Exception as e:
        logger.error(f"Recheck Error: {e}")
        await query.answer("❌ Error during re-check.", show_alert=True)

@Client.on_callback_query(filters.regex(r"^close_data"))
async def close_data(client, query):
    await query.message.delete()

# ==============================================================================
# 🎯 MASTER SELECTION HANDLER (EXISTING)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^filter_sel#"))
async def filter_selection_handler(client, query):
    # Data: filter_sel#{query}#{qual}#{lang}#{year}#{size}#{type}#{sort}
    parts = query.data.split("#")
    req_query = parts[1]
    sel_qual = parts[2]
    sel_lang = parts[3]
    sel_year = parts[4]
    sel_size = parts[5]
    sel_type = parts[6]
    sel_sort = parts[7] if len(parts) > 7 else "relevance"
    
    files = await Media.get_search_results(req_query, sort_mode=sel_sort)
    
    if sel_qual != "None": files = filter_by_quality(files, sel_qual)
    if sel_lang != "None": files = filter_by_lang(files, sel_lang)
    if sel_year != "None": files = filter_by_year(files, sel_year)
    if sel_size != "None": files = filter_by_size(files, sel_size)
    if sel_type != "None": files = filter_by_type(files, sel_type)
             
    if not files: return await query.answer("No files found for this combination.", show_alert=True)

    total_results = len(files)
    limit = 10
    offset = 0
    group_settings = await db.get_group_settings(query.message.chat.id)
    mode = group_settings.get('result_mode', 'hybrid')
    howto_url = group_settings.get('howto_url')
    
    if mode == 'hybrid':
        mode = 'button' if len(files) <= limit else 'text'

    extra_btn = []
    if howto_url: extra_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])

    # ROW 1: Media Type
    media_row = []
    if sel_type == "None":
        media_row.append(InlineKeyboardButton("Videos", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#Video#{sel_sort}"))
        media_row.append(InlineKeyboardButton("Docs", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#Document#{sel_sort}"))
    elif sel_type == "Video":
        media_row.append(InlineKeyboardButton("Videos ✅", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#None#{sel_sort}"))
        media_row.append(InlineKeyboardButton("Docs", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#Document#{sel_sort}"))
    elif sel_type == "Document":
        media_row.append(InlineKeyboardButton("Videos", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#Video#{sel_sort}"))
        media_row.append(InlineKeyboardButton("Docs ✅", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#None#{sel_sort}"))
    extra_btn.append(media_row)

    # ROW 2: Quality & Language
    row2 = []
    q_txt = "Select Qualities 🔽" if sel_qual == "None" else f"{sel_qual.upper()} ✅"
    row2.append(InlineKeyboardButton(q_txt, callback_data=f"qual_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
    l_txt = "Select Language 🔽" if sel_lang == "None" else f"{sel_lang} ✅"
    row2.append(InlineKeyboardButton(l_txt, callback_data=f"lang_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
    extra_btn.append(row2)

    # ROW 3: Year & Size
    row3 = []
    y_txt = "Select Year 🔽" if sel_year == "None" else f"{sel_year} ✅"
    row3.append(InlineKeyboardButton(y_txt, callback_data=f"year_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
    s_txt = "Select Size 🔽" if sel_size == "None" else f"{sel_size} ✅"
    row3.append(InlineKeyboardButton(s_txt, callback_data=f"size_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
    extra_btn.append(row3)

    # ROW 4: Sort
    sort_label = "Sort By Files 🔽"
    if sel_sort != "relevance": sort_label = "Sort By Files (Active) 🔽"
    extra_btn.append([InlineKeyboardButton(sort_label, callback_data=f"sort_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}")])

    # ✅ ROW 5: RECHECK (Preserve it in filters too so it doesn't disappear)
    extra_btn.append([InlineKeyboardButton("😕 Wrong Result? Click Here", callback_data=f"recheck#1#{req_query}")])

    # RESET
    reset_row = []
    if sel_qual != "None": reset_row.append(InlineKeyboardButton("All Qualities 🔄", callback_data=f"filter_sel#{req_query}#None#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
    if sel_lang != "None": reset_row.append(InlineKeyboardButton("All Languages 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#None#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
    if reset_row: extra_btn.append(reset_row)
    
    reset_row_2 = []
    if sel_year != "None": reset_row_2.append(InlineKeyboardButton("All Years 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#None#{sel_size}#{sel_type}#{sel_sort}"))
    if sel_size != "None": reset_row_2.append(InlineKeyboardButton("All Sizes 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#None#{sel_type}#{sel_sort}"))
    if reset_row_2: extra_btn.append(reset_row_2)
    
    if sel_type != "None":
        extra_btn.append([InlineKeyboardButton("All Media Types 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#None#{sel_sort}")])

    extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
    
    page_btn = get_pagination_row(offset, limit, total_results, f"{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}")

    final_markup = []
    text = f"⚡ Results for `{req_query}`"
    if sel_type != "None": text += f"\n📂 **Type:** {sel_type}"
    if sel_qual != "None": text += f"\n📀 **Quality:** {sel_qual.upper()}"
    if sel_lang != "None": text += f"\n🗣️ **Language:** {sel_lang}"
    if sel_year != "None": text += f"\n📅 **Year:** {sel_year}"
    if sel_size != "None": text += f"\n💾 **Size:** {sel_size}"
    if sel_sort != "relevance": text += f"\n📶 **Sort:** {sel_sort.replace('_', ' ').title()}"

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
# ✅ SORT BY FILES MENU
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^sort_menu#"))
async def sort_menu_handler(client, query):
    # Data: sort_menu#{query}#{qual}#{lang}#{year}#{size}#{type}#{sort}
    parts = query.data.split("#")
    req_query, curr_qual, curr_lang, curr_year, curr_size, curr_type, curr_sort = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
    
    def tick(val): return " ✅" if curr_sort == val else ""
    
    base = f"{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}"
    
    buttons = [
        [InlineKeyboardButton(f"Relevance{tick('relevance')}", callback_data=f"filter_sel#{base}#relevance")],
        [InlineKeyboardButton(f"Newest First{tick('newest')}", callback_data=f"filter_sel#{base}#newest")],
        [InlineKeyboardButton(f"Oldest First{tick('oldest')}", callback_data=f"filter_sel#{base}#oldest")],
        [InlineKeyboardButton(f"Size (High-Low){tick('size_desc')}", callback_data=f"filter_sel#{base}#size_desc")],
        [InlineKeyboardButton(f"Size (Low-High){tick('size_asc')}", callback_data=f"filter_sel#{base}#size_asc")],
        [InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{base}#{curr_sort}")]
    ]
    
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🧩 OTHER FILTER MENUS
# ==============================================================================

# --- QUALITY MENU ---
@Client.on_callback_query(filters.regex(r"^qual_menu#"))
async def quality_menu_handler(client, query):
    parts = query.data.split("#")
    req_query, curr_qual, curr_lang, curr_year, curr_size, curr_type, curr_sort = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
    
    files = await Media.get_search_results(req_query, sort_mode=curr_sort)
    if curr_lang != "None": files = filter_by_lang(files, curr_lang)
    if curr_year != "None": files = filter_by_year(files, curr_year)
    if curr_size != "None": files = filter_by_size(files, curr_size)
    if curr_type != "None": files = filter_by_type(files, curr_type)

    qual_data = get_qualities(files)
    if not qual_data: return await query.answer("No specific qualities detected.", show_alert=True)
    
    buttons = []
    temp_row = []
    for qual, count in qual_data.items():
        btn_txt = f"{qual.upper()} ({count})"
        temp_row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_sel#{req_query}#{qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}#{curr_sort}"))
        if len(temp_row) == 3:
            buttons.append(temp_row)
            temp_row = []
    if temp_row: buttons.append(temp_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}#{curr_sort}")])
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# --- LANGUAGE MENU ---
@Client.on_callback_query(filters.regex(r"^lang_menu#"))
async def language_menu_handler(client, query):
    parts = query.data.split("#")
    req_query, curr_qual, curr_lang, curr_year, curr_size, curr_type, curr_sort = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
    
    files = await Media.get_search_results(req_query, sort_mode=curr_sort)
    if curr_qual != "None": files = filter_by_quality(files, curr_qual)
    if curr_year != "None": files = filter_by_year(files, curr_year)
    if curr_size != "None": files = filter_by_size(files, curr_size)
    if curr_type != "None": files = filter_by_type(files, curr_type)

    lang_data = get_languages(files)
    if not lang_data: return await query.answer("No specific languages detected.", show_alert=True)
    
    buttons = []
    temp_row = []
    for lang, count in lang_data.items():
        btn_txt = f"{lang} ({count})"
        temp_row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_sel#{req_query}#{curr_qual}#{lang}#{curr_year}#{curr_size}#{curr_type}#{curr_sort}"))
        if len(temp_row) == 3:
            buttons.append(temp_row)
            temp_row = []
    if temp_row: buttons.append(temp_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}#{curr_sort}")])
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# --- YEAR MENU ---
@Client.on_callback_query(filters.regex(r"^year_menu#"))
async def year_menu_handler(client, query):
    parts = query.data.split("#")
    req_query, curr_qual, curr_lang, curr_year, curr_size, curr_type, curr_sort = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
    
    files = await Media.get_search_results(req_query, sort_mode=curr_sort)
    if curr_qual != "None": files = filter_by_quality(files, curr_qual)
    if curr_lang != "None": files = filter_by_lang(files, curr_lang)
    if curr_size != "None": files = filter_by_size(files, curr_size)
    if curr_type != "None": files = filter_by_type(files, curr_type)

    year_data = get_years(files)
    if not year_data: return await query.answer("No specific years detected.", show_alert=True)
    
    buttons = []
    temp_row = []
    for year, count in year_data.items():
        btn_txt = f"{year}"
        temp_row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{year}#{curr_size}#{curr_type}#{curr_sort}"))
        if len(temp_row) == 3:
            buttons.append(temp_row)
            temp_row = []
    if temp_row: buttons.append(temp_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}#{curr_sort}")])
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# --- SIZE MENU ---
@Client.on_callback_query(filters.regex(r"^size_menu#"))
async def size_menu_handler(client, query):
    parts = query.data.split("#")
    req_query, curr_qual, curr_lang, curr_year, curr_size, curr_type, curr_sort = parts[1], parts[2], parts[3], parts[4], parts[5], parts[6], parts[7]
    
    files = await Media.get_search_results(req_query, sort_mode=curr_sort)
    if curr_qual != "None": files = filter_by_quality(files, curr_qual)
    if curr_lang != "None": files = filter_by_lang(files, curr_lang)
    if curr_year != "None": files = filter_by_year(files, curr_year)
    if curr_type != "None": files = filter_by_type(files, curr_type)

    size_ranges = get_size_ranges(files)
    if not size_ranges: return await query.answer("No files found.", show_alert=True)
    
    buttons = []
    temp_row = []
    for size_cat in size_ranges:
        temp_row.append(InlineKeyboardButton(size_cat, callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{size_cat}#{curr_type}#{curr_sort}"))
        if len(temp_row) == 2:
            buttons.append(temp_row)
            temp_row = []
    if temp_row: buttons.append(temp_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}#{curr_year}#{curr_size}#{curr_type}#{curr_sort}")])
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# ⏭️ PAGINATION HANDLER
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        raw_data = query.data.split("_", 2)
        offset = int(raw_data[1])
        remainder = raw_data[2]
        
        # Format: query#qual#lang#year#size#type#sort
        if "#" in remainder:
            parts = remainder.split("#")
            req_query = parts[0]
            sel_qual = parts[1]
            sel_lang = parts[2] if len(parts) > 2 else "None"
            sel_year = parts[3] if len(parts) > 3 else "None"
            sel_size = parts[4] if len(parts) > 4 else "None"
            sel_type = parts[5] if len(parts) > 5 else "None"
            sel_sort = parts[6] if len(parts) > 6 else "relevance"
        else:
            req_query = remainder
            sel_qual = "None"
            sel_lang = "None"
            sel_year = "None"
            sel_size = "None"
            sel_type = "None"
            sel_sort = "relevance"
            
        files = await Media.get_search_results(req_query, sort_mode=sel_sort)
        if sel_qual != "None": files = filter_by_quality(files, sel_qual)
        if sel_lang != "None": files = filter_by_lang(files, sel_lang)
        if sel_year != "None": files = filter_by_year(files, sel_year)
        if sel_size != "None": files = filter_by_size(files, sel_size)
        if sel_type != "None": files = filter_by_type(files, sel_type)
        
        total_results = len(files)
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid')
        limit = group_settings.get('result_page_limit', 10)
        howto_url = group_settings.get('howto_url')
        
        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        extra_btn = []
        if howto_url: extra_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        
        # ROW 1: Media Type
        media_row = []
        if sel_type == "None":
            media_row.append(InlineKeyboardButton("Videos", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#Video#{sel_sort}"))
            media_row.append(InlineKeyboardButton("Docs", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#Document#{sel_sort}"))
        elif sel_type == "Video":
            media_row.append(InlineKeyboardButton("Videos ✅", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#None#{sel_sort}"))
            media_row.append(InlineKeyboardButton("Docs", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#Document#{sel_sort}"))
        elif sel_type == "Document":
            media_row.append(InlineKeyboardButton("Videos", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#Video#{sel_sort}"))
            media_row.append(InlineKeyboardButton("Docs ✅", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#None#{sel_sort}"))
        extra_btn.append(media_row)

        row2 = []
        q_txt = "Select Qualities 🔽" if sel_qual == "None" else f"{sel_qual.upper()} ✅"
        row2.append(InlineKeyboardButton(q_txt, callback_data=f"qual_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
        l_txt = "Select Language 🔽" if sel_lang == "None" else f"{sel_lang} ✅"
        row2.append(InlineKeyboardButton(l_txt, callback_data=f"lang_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
        extra_btn.append(row2)

        row3 = []
        y_txt = "Select Year 🔽" if sel_year == "None" else f"{sel_year} ✅"
        row3.append(InlineKeyboardButton(y_txt, callback_data=f"year_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
        s_txt = "Select Size 🔽" if sel_size == "None" else f"{sel_size} ✅"
        row3.append(InlineKeyboardButton(s_txt, callback_data=f"size_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
        extra_btn.append(row3)

        # ROW 4: Sort
        sort_label = "Sort By Files 🔽"
        if sel_sort != "relevance": sort_label = "Sort By Files (Active) 🔽"
        extra_btn.append([InlineKeyboardButton(sort_label, callback_data=f"sort_menu#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}")])

        # ✅ ROW 5: RECHECK (Preserve it in filters too so it doesn't disappear)
        extra_btn.append([InlineKeyboardButton("😕 Wrong Result? Click Here", callback_data=f"recheck#1#{req_query}")])

        # RESET
        reset_row = []
        if sel_qual != "None": reset_row.append(InlineKeyboardButton("All Qualities 🔄", callback_data=f"filter_sel#{req_query}#None#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
        if sel_lang != "None": reset_row.append(InlineKeyboardButton("All Languages 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#None#{sel_year}#{sel_size}#{sel_type}#{sel_sort}"))
        if reset_row: extra_btn.append(reset_row)
        
        reset_row_2 = []
        if sel_year != "None": reset_row_2.append(InlineKeyboardButton("All Years 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#None#{sel_size}#{sel_type}#{sel_sort}"))
        if sel_size != "None": reset_row_2.append(InlineKeyboardButton("All Sizes 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#None#{sel_type}#{sel_sort}"))
        if reset_row_2: extra_btn.append(reset_row_2)
        
        if sel_type != "None":
            extra_btn.append([InlineKeyboardButton("All Media Types 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#None#{sel_sort}")])

        extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
        
        page_btn = get_pagination_row(offset, limit, total_results, f"{req_query}#{sel_qual}#{sel_lang}#{sel_year}#{sel_size}#{sel_type}#{sel_sort}")
        
        if mode == 'button':
            buttons = btn_parser(files, query.message.chat.id, req_query, offset, limit)
            buttons.extend(extra_btn)
            if page_btn: buttons.append(page_btn)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode in ['text', 'detailed']:
            page_files = files[offset : offset + limit]
            if mode == 'text': text = format_text_results(page_files, req_query, query.message.chat.id)
            else: text = format_detailed_results(page_files, req_query, query.message.chat.id, 0)
            
            buttons = []
            buttons.extend(extra_btn)
            if page_btn: buttons.append(page_btn)
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(buttons))
            
    except Exception as e:
        logger.error(f"Pagination Error: {e}")
