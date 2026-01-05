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
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row, extract_qualities

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

# ✅ HELPER: Apply Quality Filter to File List
def apply_quality_filter(files, quality):
    if not quality or quality == "all": return files
    
    filtered_files = []
    pattern = re.compile(rf"\b{re.escape(quality)}\b", re.IGNORECASE)
    
    # Handle '4k' vs '2160p' normalization
    if quality == '4k':
        pattern = re.compile(r"\b(4k|2160p)\b", re.IGNORECASE)
        
    for file in files:
        fname = file.get('file_name', '').lower()
        if quality == 'other':
            # Check if it DOESN'T match any standard quality
            std_pattern = re.compile(r"\b(4k|2160p|1080p|720p|480p|360p|hd|cam)\b", re.IGNORECASE)
            if not std_pattern.search(fname):
                filtered_files.append(file)
        elif pattern.search(fname):
            filtered_files.append(file)
            
    return filtered_files

# ✅ HELPER: Generate Quality Buttons (For Non-Button Modes)
def get_quality_buttons(files, query, active_quality=None):
    safe_q = query[:20] if query else "blank"
    
    if active_quality and active_quality != "all":
        return [
            InlineKeyboardButton(f"{active_quality.upper()} ✅", callback_data="ignore"),
            InlineKeyboardButton("All Qualities", callback_data=f"qual_reset_{safe_q}")
        ]
    else:
        qual_counts = extract_qualities(files)
        if len(qual_counts) > 0:
            return [InlineKeyboardButton("✨ Select Qualities", callback_data=f"qual_menu_{safe_q}")]
    return []

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
    # -------------------------

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

        # 📊 UPDATE STATS
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
        # 🔀 MODE DISPATCHER
        # ==================================================================

        if mode == 'hybrid':
            if len(files) <= limit: mode = 'button'
            else: mode = 'text'

        offset = 0 
        total_results = len(files)
        sent_msg = None 

        # Extra Buttons
        howto_url = group_settings.get('howto_url')
        howto_btn = []
        if howto_url: howto_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # --- MODE A: BUTTON ---
        if mode == 'button':
            # btn_parser handles Quality Buttons internally
            buttons = btn_parser(files, message.chat.id, query, offset, limit, active_quality=None)
            if howto_btn: buttons.append(howto_btn[0])
            buttons.append(free_prem_btn)

            msg_text = (
                f"⚡ **Hey {message.from_user.mention}!**\n"
                f"👻 **Here are your results for:** `{query}`\n"
                f"⏳ **Time Taken:** {time_taken} seconds"
            )
            sent_msg = await message.reply_text(text=msg_text, reply_markup=InlineKeyboardMarkup(buttons))

        # --- MODE B: TEXT LIST ---
        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, query, message.chat.id)
            
            btn = []
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)
            
            # Pagination
            pagination = get_pagination_row(offset, limit, total_results, query)
            if pagination: btn.append(pagination)

            # ✨ Add Quality Buttons (Manual Injection for Text Mode)
            q_btns = get_quality_buttons(files, query, active_quality=None)
            if q_btns: btn.append(q_btns)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE C: DETAILED LIST ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)

            pagination = get_pagination_row(offset, limit, total_results, query)
            if pagination: btn.append(pagination)

            # ✨ Add Quality Buttons
            q_btns = get_quality_buttons(files, query, active_quality=None)
            if q_btns: btn.append(q_btns)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE D: SITE (WEB VIEW) ---
        elif mode == 'site':
            search_id = await Media.save_search_results(query, files, message.chat.id)
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            final_site_url = f"{base_url}/results/{search_id}"
            
            text = (
                f"⚡ **Results for:** `{query}`\n"
                f"📂 **Found:** {total_results} files\n"
                f"⏳ **Time:** {time_taken}s\n\n"
                f"👇 **Click the button below to view results online**"
            )
            
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)
            
            # Site mode typically doesn't need inline quality filter as it redirects, 
            # but we can add pagination row if needed
            pagination = get_pagination_row(offset, limit, total_results, query)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

        # --- MODE E: CARD (Single Result) ---
        elif mode == 'card':
            file = files[0]
            text = format_card_result(file, 0, total_results)
            
            btn = []
            link_id = file['link_id']
            chat_id = message.chat.id
            btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])

            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)

            if total_results > 1:
                short_q = query[:20] 
                btn.append([
                    InlineKeyboardButton(f"1/{total_results}", callback_data="pages"),
                    InlineKeyboardButton("Next ➡️", callback_data=f"card_next_0_{short_q}")
                ])
            
            # ✨ Add Quality Buttons
            q_btns = get_quality_buttons(files, query, active_quality=None)
            if q_btns: btn.append(q_btns)

            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))
            
        # ==================================================================
        # 🗑️ AUTO-DELETE LOGIC
        # ==================================================================
        if sent_msg:
            if user_del:
                try: await message.delete()
                except: pass
            
            if auto_del_time > 0:
                asyncio.create_task(auto_delete_task(sent_msg, message, auto_del_time, del_thanks, query))

    except Exception as e:
        logger.error(f"Search Error: {e}")

# ==============================================================================
# 🎯 QUALITY FILTER CALLBACK HANDLERS
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^qual_menu_"))
async def quality_menu_handler(client, query):
    _, req = query.data.split("_", 1)
    
    files = await Media.get_search_results(req)
    if not files: return await query.answer("Expired.", show_alert=True)
    
    qual_counts = extract_qualities(files)
    
    # Sort qualities (High to Low)
    priority = ['4k', '2160p', '1080p', '720p', '480p', '360p', 'hd', 'dvdrip', 'cam', 'other']
    sorted_quals = sorted(qual_counts.keys(), key=lambda x: priority.index(x) if x in priority else 99)
    
    btn = []
    row = []
    for q in sorted_quals:
        count = qual_counts[q]
        text = f"{q.upper()} ({count})"
        # Callback: qual_set_{quality}_{query}
        row.append(InlineKeyboardButton(text, callback_data=f"qual_set_{q}_{req}"))
        
        if len(row) == 3: # 3 buttons per row
            btn.append(row)
            row = []
            
    if row: btn.append(row)
    
    # Back Button
    safe_q = req[:20]
    btn.append([InlineKeyboardButton("🔙 Back", callback_data=f"qual_reset_{safe_q}")])
    
    await query.message.edit_text(
        f"✨ **Select Quality for:** `{req}`\nTap to filter results.",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query(filters.regex(r"^qual_set_"))
async def quality_select_handler(client, query):
    # data: qual_set_{quality}_{query}
    # Using maxsplit=3 because query might contain underscores
    parts = query.data.split("_", 3)
    quality = parts[2]
    req = parts[3]
    
    # Trigger Pagination handler to refresh view with active quality
    # We fake a "next_0_req_quality" call
    query.data = f"next_0_{req}_{quality}"
    await handle_next_back(client, query)

@Client.on_callback_query(filters.regex(r"^qual_reset_"))
async def quality_reset_handler(client, query):
    _, _, req = query.data.split("_", 2)
    # Trigger Pagination handler with no quality
    query.data = f"next_0_{req}_all"
    await handle_next_back(client, query)


# ==============================================================================
# ⏭️ UPDATED PAGINATION HANDLER
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        # Callback Data Format: next_{offset}_{req}_{quality}
        parts = query.data.split("_")
        offset = int(parts[1])
        req = parts[2]
        
        # Check if quality param exists (Index 3)
        active_quality = parts[3] if len(parts) > 3 else None
        if active_quality == "all": active_quality = None
        
        # 1. Fetch ALL Files
        files = await Media.get_search_results(req)
        if not files:
            return await query.answer("❌ Search expired or no files found.", show_alert=True)

        # 2. Apply Quality Filter (If active)
        filtered_files = apply_quality_filter(files, active_quality)
        total_results = len(filtered_files)

        if total_results == 0 and active_quality:
             return await query.answer("No files found for this quality.", show_alert=True)
        
        # 3. Get Settings
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10

        if mode == 'hybrid':
            mode = 'button' if total_results <= limit else 'text'

        # Extra Buttons
        howto_url = group_settings.get('howto_url')
        howto_btn = []
        if howto_url: howto_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # --- BUTTON MODE ---
        if mode == 'button':
            # btn_parser handles Quality Buttons internally
            buttons = btn_parser(files, query.message.chat.id, req, offset, limit, active_quality=active_quality)
            if howto_btn: buttons.append(howto_btn[0])
            buttons.append(free_prem_btn)
            
            txt_display = f"⚡ **Results for:** `{req}`"
            if active_quality: txt_display += f"\n💎 **Quality:** `{active_quality.upper()}`"
            
            await query.message.edit_text(txt_display, reply_markup=InlineKeyboardMarkup(buttons))
            
        # --- TEXT MODE ---
        elif mode == 'text':
            page_files = filtered_files[offset : offset + limit]
            text = format_text_results(page_files, req, query.message.chat.id)
            
            btn = []
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)
            
            # Note: Pass filtered_files count and active_quality to pagination
            pagination = get_pagination_row(offset, limit, total_results, req)
            # Hack: Patch pagination callback data to include quality
            if pagination and active_quality:
                for b in pagination:
                    if "next_" in b.callback_data:
                        b.callback_data += f"_{active_quality}"
            if pagination: btn.append(pagination)
            
            # ✨ Add Quality Buttons
            q_btns = get_quality_buttons(files, req, active_quality=active_quality)
            if q_btns: btn.append(q_btns)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- DETAILED MODE ---
        elif mode == 'detailed':
            page_files = filtered_files[offset : offset + limit]
            text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            
            btn = []
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, req)
            if pagination and active_quality:
                for b in pagination:
                    if "next_" in b.callback_data:
                        b.callback_data += f"_{active_quality}"
            if pagination: btn.append(pagination)

            q_btns = get_quality_buttons(files, req, active_quality=active_quality)
            if q_btns: btn.append(q_btns)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

    except Exception as e:
        logger.error(f"Pagination Error: {e}")
        await query.answer("⚠️ Error switching page.", show_alert=True)

# Card Mode Handlers (Existing) - Card Mode handles pagination differently, quality filter logic added via qual_menu
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

        q_btns = get_quality_buttons(files, q_text, active_quality=None)
        if q_btns: btn.append(q_btns)

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

        q_btns = get_quality_buttons(files, q_text, active_quality=None)
        if q_btns: btn.append(q_btns)

        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e: await query.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^pages$"))
async def page_counter_callback(client, query):
    await query.answer(f"Current Page Indicator", show_alert=False)
