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
# ✅ Added get_qualities, get_languages
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row, get_qualities, get_languages

logger = logging.getLogger(__name__)

# ✅ CONSTANTS
REACTIONS = ["👍", "❤️", "🔥", "🥰", "👏", "😁", "🎉", "🤩"]
DELETE_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg" # Image for Thanks Message

# ✅ HELPER: Auto-Delete Logic with Thanks Message
async def auto_delete_task(bot_message, user_message, delay, show_thanks, query="files"):
    if delay <= 0: return 
    
    await asyncio.sleep(delay)
    
    try:
        # 1. Delete the Search Results (Bot Message)
        await bot_message.delete()
        
        # 2. Show "Thanks" Message if enabled
        if show_thanks:
            caption = (
                f"👋 Hᴇʏ fasion lovers, Yᴏᴜʀ Fɪʟᴛᴇʀ Fᴏʀ '{query}' Is Cʟᴏsᴇᴅ 📪\n\n"
                f"Tʜᴀɴᴋ Yᴏᴜ Fᴏʀ Usɪɴɢ! 🌟\n"
                f"Cᴏᴍᴇ Aɢᴀɪɴ! 😊👍"
            )
            
            # Send Photo with Caption
            temp_msg = await user_message.reply_photo(
                photo=DELETE_IMG,
                caption=caption,
                quote=False
            )
            
            # Wait 1 Minute (60 seconds) then delete the thanks message
            await asyncio.sleep(60)
            await temp_msg.delete()
            
    except Exception as e:
        pass

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index", "set_shortner", "settings", "connect", "delreq"]))
async def auto_filter(client, message):
    
    raw_query = message.text

    # ==================================================================
    # 🛑 ANTI-SPAM IGNORE LAYER
    # ==================================================================
    if message.forward_from or message.forward_from_chat or message.via_bot: return
    if re.search(r"(https?://|www\.|t\.me/|@\w+)", raw_query): return
    NSFW_KEYWORDS = ["porn", "sex", "xxx", "nude", "horny", "gore", "adult", "dick", "pussy"]
    if any(word in raw_query.lower() for word in NSFW_KEYWORDS): return

    if len(raw_query) < 2: return

    # --- 🧹 CLEANING LOGIC ---
    clean_regex = r"\b(please|pls|plz|ples|send(\s+me)?|give|gib|find|chahiye|movie|new|latest|full\s+movie|file|link|hello|hi|bro|bhai|sir|bruh|hindi|tamil|malayalam|eng|with\s+subtitles|hd)\b"
    query = re.sub(clean_regex, "", raw_query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()
    if len(query) < 2: query = raw_query

    start_time = time.time()

    try:
        # ✅ 1. Get Group Settings
        group_settings = await db.get_group_settings(message.chat.id)
        
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        auto_react = group_settings.get('auto_reaction', False)
        auto_del_time = group_settings.get('auto_delete_time', 300)
        user_del = group_settings.get('auto_delete_user_msg', False)
        del_thanks = group_settings.get('delete_thanks_msg', True)
        howto_url = group_settings.get('howto_url')

        await db.update_daily_stats(message.chat.id, 'req')

        # ✅ 2. Fetch Results
        files = await Media.get_search_results(query)
        
        end_time = time.time()
        time_taken = round(end_time - start_time, 2)

        if not files: return
            
        await db.update_daily_stats(message.chat.id, 'suc')

        if auto_react:
            try: await message.react(random.choice(REACTIONS))
            except: pass 

        # ==================================================================
        # 🌟 BUTTON GENERATION LOGIC (Unified)
        # ==================================================================
        
        extra_btn = []
        
        # 1. How To Button
        if howto_url:
            extra_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        
        # 2. Filter Buttons Row (Quality | Language) 🌟
        # Initial State: Quality=None, Language=None
        filter_row = [
            InlineKeyboardButton("Select Qualities 🔽", callback_data=f"qual_menu#{query}#None#None"),
            InlineKeyboardButton("Select Language 🔽", callback_data=f"lang_menu#{query}#None#None")
        ]
        extra_btn.append(filter_row)

        # 3. Free Premium
        extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])

        # Pagination Logic
        offset = 0
        total_results = len(files)
        
        if mode == 'hybrid':
            if len(files) <= limit: mode = 'button'
            else: mode = 'text'

        # Pass filters to pagination: query#Qual#Lang
        page_btn = get_pagination_row(offset, limit, total_results, f"{query}#None#None")

        final_markup = []
        text = ""
        sent_msg = None

        if mode == 'button':
            final_markup = btn_parser(files, message.chat.id, query, offset, limit)
            text = f"⚡ Results for `{query}`\n⏳ **Time:** {time_taken}s"
            # Assemble
            final_markup.extend(extra_btn)
            if page_btn: final_markup.append(page_btn)
            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(final_markup))
        
        elif mode in ['text', 'detailed', 'site']:
            page_files = files[offset : offset + limit]
            
            if mode == 'text': text = format_text_results(page_files, query, message.chat.id)
            elif mode == 'detailed': text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            elif mode == 'site':
                search_id = await Media.save_search_results(query, files, message.chat.id)
                final_site_url = f"{SITE_URL}/results/{search_id}"
                text = f"⚡ **Results for:** `{query}`\n📂 **Found:** {total_results} files\n👇 **Click below to view online**"
                final_markup = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]

            # Assemble Buttons
            buttons = []
            if mode == 'site': buttons.extend(final_markup)
            buttons.extend(extra_btn)
            if page_btn: buttons.append(page_btn)
            
            sent_msg = await message.reply_text(
                text, 
                disable_web_page_preview=True, 
                reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
            )

        elif mode == 'card':
            file = files[0]
            text = format_card_result(file, 0, total_results)
            # Card mode specific button logic...
            # (Card mode usually has specific navigation, simplified for now)
            btn = []
            link_id = file['link_id']
            chat_id = message.chat.id
            btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])
            btn.extend(extra_btn)
            if total_results > 1:
                 short_q = query[:20]
                 btn.append([
                    InlineKeyboardButton(f"1/{total_results}", callback_data="pages"),
                    InlineKeyboardButton("Next ➡️", callback_data=f"card_next_0_{short_q}")
                ])
            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

        # ==================================================================
        # 🗑️ AUTO-DELETE LOGIC (POST-SEND)
        # ==================================================================
        if sent_msg:
            if user_del:
                try: await message.delete()
                except: pass
            
            if auto_del_time > 0:
                asyncio.create_task(
                    auto_delete_task(sent_msg, message, auto_del_time, del_thanks, query)
                )

    except Exception as e:
        logger.error(f"Search Error: {e}")

# ==============================================================================
# 🌟 FILTER MENU HANDLERS (Quality & Language)
# ==============================================================================

# --- QUALITY MENU ---
@Client.on_callback_query(filters.regex(r"^qual_menu#"))
async def quality_menu_handler(client, query):
    # Data: qual_menu#{query}#{curr_qual}#{curr_lang}
    parts = query.data.split("#")
    req_query = parts[1]
    curr_qual = parts[2]
    curr_lang = parts[3]
    
    files = await Media.get_search_results(req_query)
    # If a language is already selected, filter files first
    if curr_lang != "None":
        files = filter_by_lang(files, curr_lang)

    qual_data = get_qualities(files)
    if not qual_data: return await query.answer("No specific qualities detected.", show_alert=True)
    
    buttons = []
    temp_row = []
    for qual, count in qual_data.items():
        btn_txt = f"{qual.upper()} ({count})"
        temp_row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_sel#{req_query}#{qual}#{curr_lang}"))
        if len(temp_row) == 3:
            buttons.append(temp_row)
            temp_row = []
    if temp_row: buttons.append(temp_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}")])
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# --- LANGUAGE MENU ---
@Client.on_callback_query(filters.regex(r"^lang_menu#"))
async def language_menu_handler(client, query):
    # Data: lang_menu#{query}#{curr_qual}#{curr_lang}
    parts = query.data.split("#")
    req_query = parts[1]
    curr_qual = parts[2]
    curr_lang = parts[3]
    
    files = await Media.get_search_results(req_query)
    # If a quality is already selected, filter files first
    if curr_qual != "None":
        files = filter_by_quality(files, curr_qual)

    lang_data = get_languages(files)
    if not lang_data: return await query.answer("No specific languages detected.", show_alert=True)
    
    buttons = []
    temp_row = []
    for lang, count in lang_data.items():
        btn_txt = f"{lang} ({count})"
        temp_row.append(InlineKeyboardButton(btn_txt, callback_data=f"filter_sel#{req_query}#{curr_qual}#{lang}"))
        if len(temp_row) == 3:
            buttons.append(temp_row)
            temp_row = []
    if temp_row: buttons.append(temp_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filter_sel#{req_query}#{curr_qual}#{curr_lang}")])
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# 🎯 MASTER SELECTION HANDLER (Handles Both)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^filter_sel#"))
async def filter_selection_handler(client, query):
    # Data: filter_sel#{query}#{qual}#{lang}
    parts = query.data.split("#")
    req_query = parts[1]
    sel_qual = parts[2]
    sel_lang = parts[3]
    
    # 1. Fetch & Filter
    files = await Media.get_search_results(req_query)
    
    # Apply Filters
    if sel_qual != "None": files = filter_by_quality(files, sel_qual)
    if sel_lang != "None": files = filter_by_lang(files, sel_lang)
             
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

    # --- DYNAMIC BUTTON ROW ---
    filter_row = []
    
    # Quality Button
    if sel_qual == "None":
        filter_row.append(InlineKeyboardButton("Select Qualities 🔽", callback_data=f"qual_menu#{req_query}#{sel_qual}#{sel_lang}"))
    else:
        filter_row.append(InlineKeyboardButton(f"{sel_qual.upper()} ✅", callback_data=f"qual_menu#{req_query}#{sel_qual}#{sel_lang}"))
    
    # Language Button
    if sel_lang == "None":
        filter_row.append(InlineKeyboardButton("Select Language 🔽", callback_data=f"lang_menu#{req_query}#{sel_qual}#{sel_lang}"))
    else:
        filter_row.append(InlineKeyboardButton(f"{sel_lang} ✅", callback_data=f"lang_menu#{req_query}#{sel_qual}#{sel_lang}"))
        
    extra_btn.append(filter_row)
    
    # Reset Buttons Row
    reset_row = []
    if sel_qual != "None": 
        reset_row.append(InlineKeyboardButton("All Qualities 🔄", callback_data=f"filter_sel#{req_query}#None#{sel_lang}"))
    if sel_lang != "None":
        reset_row.append(InlineKeyboardButton("All Languages 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#None"))
    
    if reset_row: extra_btn.append(reset_row)
    
    extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
    
    # Pagination passes BOTH filters
    page_btn = get_pagination_row(offset, limit, total_results, f"{req_query}#{sel_qual}#{sel_lang}")

    # 4. Generate Output
    final_markup = []
    text = f"⚡ Results for `{req_query}`"
    if sel_qual != "None": text += f"\n📀 **Quality:** {sel_qual.upper()}"
    if sel_lang != "None": text += f"\n🗣️ **Language:** {sel_lang}"

    if mode == 'button':
        final_markup = btn_parser(files, query.message.chat.id, req_query, offset, limit)
        final_markup.extend(extra_btn)
        if page_btn: final_markup.append(page_btn)
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(final_markup))
        
    elif mode in ['text', 'detailed', 'site']:
        page_files = files[offset : offset + limit]
        if mode == 'text': text = format_text_results(page_files, req_query, query.message.chat.id)
        elif mode == 'detailed': text = format_detailed_results(page_files, req_query, query.message.chat.id)
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
# 🧩 FILTER LOGIC HELPERS
# ==============================================================================
def filter_by_quality(files, quality):
    key = quality.lower()
    if key == "4k":
        return [f for f in files if "4k" in f['file_name'].lower() or "2160p" in f['file_name'].lower()]
    return [f for f in files if key in f['file_name'].lower()]

def filter_by_lang(files, language):
    lang_map = {
        "Hindi": ["hindi", "hin", "hind"], "English": ["english", "eng"],
        "Tamil": ["tamil", "tam"], "Telugu": ["telugu", "tel"],
        "Malayalam": ["malayalam", "mal"], "Kannada": ["kannada", "kan"],
        "Bengali": ["bengali", "ben"], "Punjabi": ["punjabi", "pun"],
        "Urdu": ["urdu"], "Dual": ["dual"], "Multi": ["multi"]
    }
    keywords = lang_map.get(language, [language.lower()])
    filtered = []
    for f in files:
        name = f['file_name'].lower()
        if any(k in name for k in keywords):
            filtered.append(f)
    return filtered

# ==============================================================================
# ⏭️ PAGINATION HANDLER (Supports Double Filters)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        # Format: next_{offset}_{req}#{qual}#{lang}
        raw_data = query.data.split("_", 2)
        offset = int(raw_data[1])
        remainder = raw_data[2]
        
        if "#" in remainder:
            parts = remainder.split("#")
            req_query = parts[0]
            sel_qual = parts[1]
            sel_lang = parts[2] if len(parts) > 2 else "None"
        else:
            req_query = remainder
            sel_qual = "None"
            sel_lang = "None"
            
        # 1. Fetch & Filter
        files = await Media.get_search_results(req_query)
        if sel_qual != "None": files = filter_by_quality(files, sel_qual)
        if sel_lang != "None": files = filter_by_lang(files, sel_lang)
        
        total_results = len(files)
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid')
        limit = group_settings.get('result_page_limit', 10)
        howto_url = group_settings.get('howto_url')
        
        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        # 2. Buttons
        extra_btn = []
        if howto_url: extra_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        
        filter_row = []
        if sel_qual == "None":
            filter_row.append(InlineKeyboardButton("Select Qualities 🔽", callback_data=f"qual_menu#{req_query}#{sel_qual}#{sel_lang}"))
        else:
            filter_row.append(InlineKeyboardButton(f"{sel_qual.upper()} ✅", callback_data=f"qual_menu#{req_query}#{sel_qual}#{sel_lang}"))
    
        if sel_lang == "None":
            filter_row.append(InlineKeyboardButton("Select Language 🔽", callback_data=f"lang_menu#{req_query}#{sel_qual}#{sel_lang}"))
        else:
            filter_row.append(InlineKeyboardButton(f"{sel_lang} ✅", callback_data=f"lang_menu#{req_query}#{sel_qual}#{sel_lang}"))
        
        extra_btn.append(filter_row)

        reset_row = []
        if sel_qual != "None": reset_row.append(InlineKeyboardButton("All Qualities 🔄", callback_data=f"filter_sel#{req_query}#None#{sel_lang}"))
        if sel_lang != "None": reset_row.append(InlineKeyboardButton("All Languages 🔄", callback_data=f"filter_sel#{req_query}#{sel_qual}#None"))
        if reset_row: extra_btn.append(reset_row)
        
        extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
        
        # 3. Render
        page_btn = get_pagination_row(offset, limit, total_results, f"{req_query}#{sel_qual}#{sel_lang}")
        
        if mode == 'button':
            buttons = btn_parser(files, query.message.chat.id, req_query, offset, limit)
            buttons.extend(extra_btn)
            if page_btn: buttons.append(page_btn)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode in ['text', 'detailed']:
            page_files = files[offset : offset + limit]
            if mode == 'text': text = format_text_results(page_files, req_query, query.message.chat.id)
            else: text = format_detailed_results(page_files, req_query, query.message.chat.id)
            
            buttons = []
            buttons.extend(extra_btn)
            if page_btn: buttons.append(page_btn)
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(buttons))
            
    except Exception as e:
        logger.error(f"Pagination Error: {e}")
        await query.answer("⚠️ Error switching page.", show_alert=True)

# ... (Keep existing Card Mode Handlers card_next_ and card_prev_) ...
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
        group_settings = await db.get_group_settings(query.message.chat.id)
        howto_url = group_settings.get('howto_url')
        btn = []
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])
        if howto_url: btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
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
        group_settings = await db.get_group_settings(query.message.chat.id)
        howto_url = group_settings.get('howto_url')
        btn = []
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])
        if howto_url: btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
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
