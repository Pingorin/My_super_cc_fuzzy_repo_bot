import logging
import time
import re
import random 
import asyncio 
import math
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import PORT, SITE_URL
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row

logger = logging.getLogger(__name__)

# ✅ CONSTANTS
REACTIONS = ["👍", "❤️", "🔥", "🥰", "👏", "😁", "🎉", "🤩"]
DELETE_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg" 

# --- HELPER: GET QUALITY BUTTONS ---
def get_quality_buttons(files, query):
    # Standard Qualities to detect
    QUALITIES = ["480p", "720p", "1080p", "2160p", "4k", "CAM", "DVDRip", "HDRip", "HINDI", "ENGLISH"]
    found = []
    
    # Check which qualities exist in the current file list
    for q in QUALITIES:
        for f in files:
            if q.lower() in f['file_name'].lower():
                found.append(q)
                break # Found one, move to next quality
    
    buttons = []
    if found:
        row = []
        for q in found:
            # Safe query length for callback
            safe_q = query[:15]
            row.append(InlineKeyboardButton(q, callback_data=f"qual#{q}#{safe_q}"))
            if len(row) == 4: # 4 buttons per row
                buttons.append(row)
                row = []
        if row: buttons.append(row)
    return buttons

# --- HELPER: AUTO DELETE TASK ---
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

    # 1. Anti-Spam Blocks
    if message.forward_from or message.forward_from_chat or message.via_bot: return
    if re.search(r"(https?://|www\.|t\.me/|@\w+)", raw_query): return
    if any(word in raw_query.lower() for word in ["porn", "sex", "xxx", "nude", "horny", "gore", "adult", "dick", "pussy"]): return
    if len(raw_query) < 2: return

    # Clean Query
    clean_regex = r"\b(please|pls|plz|ples|send(\s+me)?|give|gib|find|chahiye|movie|new|latest|full\s+movie|file|link|hello|hi|bro|bhai|sir|bruh|hindi|tamil|malayalam|eng|with\s+subtitles|hd)\b"
    query = re.sub(clean_regex, "", raw_query, flags=re.IGNORECASE)
    query = re.sub(r"\s+", " ", query).strip()
    if len(query) < 2: query = raw_query

    start_time = time.time()

    try:
        # Settings
        group_settings = await db.get_group_settings(message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        auto_react = group_settings.get('auto_reaction', False)
        auto_del_time = group_settings.get('auto_delete_time', 300)
        user_del = group_settings.get('auto_delete_user_msg', False)
        del_thanks = group_settings.get('delete_thanks_msg', True)

        await db.update_daily_stats(message.chat.id, 'req')

        # Search
        files = await Media.get_search_results(query)
        time_taken = round(time.time() - start_time, 2)

        if not files: return
        await db.update_daily_stats(message.chat.id, 'suc')

        if auto_react:
            try: await message.react(random.choice(REACTIONS))
            except: pass 

        # Mode Logic
        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        offset = 0 
        total_results = len(files)
        sent_msg = None 
        
        # Buttons Setup
        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]
        
        # ✅ Generate Quality Buttons
        qual_btns = get_quality_buttons(files, query)

        # --- MODE A: BUTTON ---
        if mode == 'button':
            buttons = btn_parser(files, message.chat.id, query, offset, limit)
            
            # Add Extra Buttons
            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)
            
            # ✅ Add Quality Buttons at TOP (Insert at index 0)
            if qual_btns:
                for row in reversed(qual_btns):
                    buttons.insert(0, row)

            msg_text = f"⚡ **Hey {message.from_user.mention}!**\n👻 **Here are your results for:** `{query}`\n⏳ **Time Taken:** {time_taken}s"
            sent_msg = await message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(buttons))

        # --- MODE B: TEXT LIST ---
        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, query, message.chat.id)
            
            btn = []
            if qual_btns: btn.extend(qual_btns) # Add Quality Btns
            
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, query)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE C: DETAILED ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            if qual_btns: btn.extend(qual_btns) # Add Quality Btns
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            pagination = get_pagination_row(offset, limit, total_results, query)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE D: SITE ---
        elif mode == 'site':
            search_id = await Media.save_search_results(query, files, message.chat.id)
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            final_site_url = f"{base_url}/results/{search_id}"
            
            text = f"⚡ **Results for:** `{query}`\n📂 **Found:** {total_results} files\n👇 **Click below to view**"
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
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
                short_q = query[:20] 
                btn.append([InlineKeyboardButton(f"1/{total_results}", callback_data="pages"), InlineKeyboardButton("Next ➡️", callback_data=f"card_next_0_{short_q}")])
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
# 💎 QUALITY FILTER HANDLER (Clicked on 480p, 720p etc)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^qual#"))
async def quality_filter_handler(client, query):
    _, qual, req = query.data.split("#")
    
    # 1. Fetch All Files
    files = await Media.get_search_results(req)
    
    # 2. Filter List
    filtered = [f for f in files if qual.lower() in f['file_name'].lower()]
    
    if not filtered:
        return await query.answer("❌ No files found for this quality.", show_alert=True)
    
    # 3. Generate Buttons for Filtered View
    limit = 10
    offset = 0
    buttons = btn_parser(filtered, query.message.chat.id, req, offset, limit)
    
    # 4. FIX PAGINATION (Standard btn_parser adds standard pagination, we need Custom)
    if len(filtered) > limit:
        # Remove standard pagination row if it exists
        if len(buttons) > 0 and isinstance(buttons[-1][0], InlineKeyboardButton):
             if "next_" in buttons[-1][0].callback_data or "pages" in buttons[-1][0].callback_data:
                 buttons.pop()
        
        # Add Custom Pagination for Filtered Results
        total_pages = math.ceil(len(filtered)/limit)
        nav = []
        nav.append(InlineKeyboardButton(f"1/{total_pages}", callback_data="pages"))
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"qualnext_{limit}_{req}_{qual}"))
        buttons.append(nav)

    # Add Back Button
    buttons.append([InlineKeyboardButton("🔙 Back to All Results", callback_data=f"next_0_{req}")])

    await query.message.edit_text(
        f"⚡ **Filtered Results:** `{req}`\n💎 **Quality:** {qual}\n📂 **Found:** {len(filtered)}",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ==============================================================================
# ⏭️ QUALITY PAGINATION HANDLER
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^qualnext_"))
async def quality_pagination_handler(client, query):
    _, offset, req, qual = query.data.split("_", 3)
    offset = int(offset)
    limit = 10
    
    files = await Media.get_search_results(req)
    filtered = [f for f in files if qual.lower() in f['file_name'].lower()]
    
    buttons = btn_parser(filtered, query.message.chat.id, req, offset, limit)
    
    # Custom Pagination Logic
    total = len(filtered)
    total_pages = math.ceil(total/limit)
    current_page = int(offset / limit) + 1
    
    # Remove standard pagination
    if len(buttons) > 0 and isinstance(buttons[-1][0], InlineKeyboardButton):
         if "next_" in buttons[-1][0].callback_data or "pages" in buttons[-1][0].callback_data:
             buttons.pop()
             
    # Add Quality Pagination
    nav = []
    if offset >= limit:
        nav.append(InlineKeyboardButton("⬅️ Back", callback_data=f"qualnext_{offset - limit}_{req}_{qual}"))
    
    nav.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="pages"))
    
    if offset + limit < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"qualnext_{offset + limit}_{req}_{qual}"))
        
    if nav: buttons.append(nav)
    
    buttons.append([InlineKeyboardButton("🔙 Back to All Results", callback_data=f"next_0_{req}")])
    
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))

# ==============================================================================
# ⏭️ STANDARD PAGINATION HANDLER (Existing)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        _, offset, req = query.data.split("_", 2) 
        offset = int(offset)
        files = await Media.get_search_results(req)
        if not files: return await query.answer("❌ Search expired.", show_alert=True)
            
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        if mode == 'hybrid': mode = 'button' if len(files) <= limit else 'text'

        # Generate Qual Buttons for Page changes too
        qual_btns = get_quality_buttons(files, req)
        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        if mode == 'button':
            buttons = btn_parser(files, query.message.chat.id, req, offset, limit)
            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)
            # Re-add Qual Buttons
            if qual_btns:
                for row in reversed(qual_btns):
                    buttons.insert(0, row)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, req, query.message.chat.id)
            btn = []
            if qual_btns: btn.extend(qual_btns)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            pagination = get_pagination_row(offset, limit, len(files), req)
            if pagination: btn.append(pagination)
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            btn = []
            if qual_btns: btn.extend(qual_btns)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            pagination = get_pagination_row(offset, limit, len(files), req)
            if pagination: btn.append(pagination)
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

    except Exception as e:
        logger.error(f"Pagination Error: {e}")
        await query.answer("⚠️ Error switching page.", show_alert=True)

# ... (Card Handlers remain same) ...
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
        
        group_settings = await db.get_group_settings(query.message.chat.id)
        howto_url = group_settings.get('howto_url')
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
        btn = []
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])
        
        group_settings = await db.get_group_settings(query.message.chat.id)
        howto_url = group_settings.get('howto_url')
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
