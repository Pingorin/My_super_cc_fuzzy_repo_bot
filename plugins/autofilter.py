import logging
import time
import re
import random 
import asyncio 
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import SITE_URL
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row

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
                photo=DELETE_IMG, caption=caption, quote=False
            )
            await asyncio.sleep(60)
            await temp_msg.delete()
            
    except Exception:
        pass

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index", "set_shortner", "settings", "connect", "delreq"]))
async def auto_filter(client, message):
    
    raw_query = message.text

    # ==================================================================
    # 🛑 ANTI-SPAM & CLEANING LAYERS
    # ==================================================================
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
        # ✅ 1. Get Settings & Update Stats
        group_settings = await db.get_group_settings(message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        auto_react = group_settings.get('auto_reaction', False)
        auto_del_time = group_settings.get('auto_delete_time', 300)
        user_del = group_settings.get('auto_delete_user_msg', False)
        del_thanks = group_settings.get('delete_thanks_msg', True)

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
        # 🔢 3. GENERATE SEARCH ID (DB AUTO-INCREMENT)
        # ==================================================================
        # This ID replaces the long query string in buttons
        search_id = await Media.save_search_query(query, message.from_user.id)

        # ==================================================================
        # 🔀 MODE DISPATCHER
        # ==================================================================

        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        offset = 0 
        total_results = len(files)
        sent_msg = None 
        
        # Common Buttons
        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # --- MODE A: BUTTON ---
        if mode == 'button':
            # Pass search_id instead of query
            buttons = btn_parser(files, message.chat.id, search_id, offset, limit)
            
            if howto_btn: buttons.append(howto_btn)
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
            # Formatter uses text query for Header
            text = format_text_results(page_files, query, message.chat.id)
            
            btn = []
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)

            # Pagination uses search_id for Buttons
            pagination = get_pagination_row(search_id, offset, limit, total_results)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE C: DETAILED LIST ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)

            pagination = get_pagination_row(search_id, offset, limit, total_results)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE D: SITE (WEB VIEW) ---
        elif mode == 'site':
            # Site Mode has its own UUID logic, but we can stick to that or use search_id
            # Keeping original site mode logic for web view compatibility
            web_id = await Media.save_search_results(query, files, message.chat.id)
            
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            final_site_url = f"{base_url}/results/{web_id}"
            
            text = (
                f"⚡ **Results for:** `{query}`\n"
                f"📂 **Found:** {total_results} files\n"
                f"⏳ **Time:** {time_taken}s\n\n"
                f"👇 **Click the button below to view results online**"
            )
            
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)

            # Use DB Pagination for Site Mode Buttons if needed
            pagination = get_pagination_row(search_id, offset, limit, total_results)
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

            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)

            if total_results > 1:
                # Use search_id for Card Pagination
                btn.append([
                    InlineKeyboardButton(f"1/{total_results}", callback_data="pages"),
                    InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{search_id}_0")
                ])

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
# ⏭️ DATABASE-BASED PAGINATION HANDLER
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^page_"))
async def handle_pagination(client, query):
    try:
        # Callback Data Format: page_{search_id}_{offset}
        _, search_id_str, offset_str = query.data.split("_") 
        search_id = int(search_id_str)
        offset = int(offset_str)
        
        # 1. Fetch Original Query from DB
        req = await Media.get_search_query(search_id)
        if not req:
            return await query.answer("⚠️ Search expired. Please search again.", show_alert=True)
            
        # 2. Fetch Files
        files = await Media.get_search_results(req)
        if not files:
            return await query.answer("❌ No files found.", show_alert=True)
            
        total_results = len(files)
        
        # 3. Get Settings
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10

        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # 4. Generate New Content
        
        # --- BUTTON MODE ---
        if mode == 'button':
            buttons = btn_parser(files, query.message.chat.id, search_id, offset, limit)
            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        # --- TEXT MODE ---
        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, req, query.message.chat.id)
            
            btn = []
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn) 
            
            pagination = get_pagination_row(search_id, offset, limit, total_results)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- DETAILED MODE ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            
            btn = []
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn) 
            
            pagination = get_pagination_row(search_id, offset, limit, total_results)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- SITE MODE ---
        elif mode == 'site':
            # Note: Site Mode pagination usually stays on Buttons unless user clicks "View Online"
            # Here we just update the buttons to reflect page count if needed
            page_no = int(offset / limit) + 1
            # We need original web_id here, but for now we redirect to a fresh search or base
            # Simplification: Just update navigation buttons
            
            btn = []
            # ... Site mode logic usually relies on the Web App, but for Telegram buttons:
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn) 
            
            pagination = get_pagination_row(search_id, offset, limit, total_results)
            if pagination: btn.append(pagination)
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Pagination Error: {e}")
        await query.answer("⚠️ Error switching page.", show_alert=True)

# ==============================================================================
# 🎴 CARD MODE HANDLERS (UPDATED FOR DB PAGINATION)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^card_next_"))
async def card_next_nav(client, query):
    try:
        # Format: card_next_{search_id}_{current_index}
        _, _, search_id_str, index_str = query.data.split("_") 
        search_id = int(search_id_str)
        current_index = int(index_str)

        # Fetch Query
        req = await Media.get_search_query(search_id)
        if not req: return await query.answer("⚠️ Search expired.", show_alert=True)

        files = await Media.get_search_results(req)
        if not files: return await query.answer("No files found.", show_alert=True)
        
        total = len(files)
        next_index = current_index + 1
        if next_index >= total: next_index = 0
        file = files[next_index]
        text = format_card_result(file, next_index, total)
        
        # Buttons
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
    except Exception as e: await query.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^card_prev_"))
async def card_prev_nav(client, query):
    try:
        # Format: card_prev_{search_id}_{current_index}
        _, _, search_id_str, index_str = query.data.split("_")
        search_id = int(search_id_str)
        current_index = int(index_str)

        req = await Media.get_search_query(search_id)
        if not req: return await query.answer("⚠️ Search expired.", show_alert=True)

        files = await Media.get_search_results(req)
        if not files: return await query.answer("No files found.", show_alert=True)
        
        total = len(files)
        prev_index = current_index - 1
        if prev_index < 0: prev_index = total - 1
        file = files[prev_index]
        text = format_card_result(file, prev_index, total)
        
        # Buttons
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
    except Exception as e: await query.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^pages$"))
async def page_counter_callback(client, query):
    await query.answer(f"Current Page Indicator", show_alert=False)
