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
# ✅ Added filter_by_type and get_filter_buttons to imports
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row, filter_by_type, get_filter_buttons

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
        # Pass if message is already deleted or permission error
        pass

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index", "set_shortner", "settings", "connect", "delreq"]))
async def auto_filter(client, message):
    
    raw_query = message.text

    # ==================================================================
    # 🛑 ANTI-SPAM IGNORE LAYER (Search Block)
    # ==================================================================
    
    # 1. Block Forwards & Via Bot
    if message.forward_from or message.forward_from_chat or message.via_bot:
        return

    # 2. Block Links & Mentions (@username)
    if re.search(r"(https?://|www\.|t\.me/|@\w+)", raw_query):
        return

    # 3. Block NSFW Keywords (Extra Safety)
    NSFW_KEYWORDS = ["porn", "sex", "xxx", "nude", "horny", "gore", "adult", "dick", "pussy"]
    if any(word in raw_query.lower() for word in NSFW_KEYWORDS):
        return
    # ==================================================================

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
        
        # Display Settings
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        
        # Auto-Delete & Reaction Settings
        auto_react = group_settings.get('auto_reaction', False)
        auto_del_time = group_settings.get('auto_delete_time', 300) # Default 5 min
        user_del = group_settings.get('auto_delete_user_msg', False)
        del_thanks = group_settings.get('delete_thanks_msg', True)

        # 📊 UPDATE STATS: Total Request
        await db.update_daily_stats(message.chat.id, 'req')

        # ✅ 2. Fetch Results
        files = await Media.get_search_results(query)
        
        end_time = time.time()
        time_taken = round(end_time - start_time, 2)

        if not files:
            return
            
        # 📊 UPDATE STATS: Successful Search
        await db.update_daily_stats(message.chat.id, 'suc')

        # ✅ 3. SAVE SESSION & GET UNIQUE ID (Fixes Button Data Invalid)
        unique_id = await Media.save_search_result(query, files)

        # ✅ 4. Auto-Reaction Logic
        if auto_react:
            try:
                emoji = random.choice(REACTIONS)
                await message.react(emoji)
            except: pass 

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
        
        # Capture the message sent by bot
        sent_msg = None 

        # ✅ PREPARE BUTTONS: Filter, HowTo, Premium
        
        # 1. Filter Buttons (Default: All)
        filter_row, reset_row = get_filter_buttons(unique_id, "all")
        
        # 2. How To Download URL
        howto_url = group_settings.get('howto_url')
        howto_btn = []
        if howto_url:
            howto_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
            
        # 3. Free Premium Button
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # --- MODE A: BUTTON ---
        if mode == 'button':
            # ⚠️ Pass unique_id instead of query
            buttons = btn_parser(files, message.chat.id, unique_id, offset, limit)
            
            # ✅ Add Filters
            if filter_row: buttons.append(filter_row)
            if reset_row: buttons.append(reset_row)
            
            # Add How To Button
            if howto_btn: buttons.append(howto_btn[0])
            # Add Free Premium Button
            buttons.append(free_prem_btn)

            msg_text = (
                f"⚡ **Hey {message.from_user.mention}!**\n"
                f"👻 **Here are your results for:** `{query}`\n"
                f"⏳ **Time Taken:** {time_taken} seconds"
            )
            sent_msg = await message.reply_text(
                text=msg_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # --- MODE B: TEXT LIST ---
        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, query, message.chat.id)
            
            btn = []
            # ✅ Add Filters
            if filter_row: btn.append(filter_row)
            if reset_row: btn.append(reset_row)
            
            # Add How To Button
            if howto_btn: btn.append(howto_btn[0])
            # Add Free Premium Button
            btn.append(free_prem_btn)

            # ⚠️ Pass unique_id to pagination (default filter 'all')
            pagination = get_pagination_row(offset, limit, total_results, unique_id, "all")
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE C: DETAILED LIST ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            # ✅ Add Filters
            if filter_row: btn.append(filter_row)
            if reset_row: btn.append(reset_row)
            
            # Add How To Button
            if howto_btn: btn.append(howto_btn[0])
            # Add Free Premium Button
            btn.append(free_prem_btn)

            # ⚠️ Pass unique_id to pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id, "all")
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE D: SITE (WEB VIEW) ---
        elif mode == 'site':
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            final_site_url = f"{base_url}/results/{unique_id}"
            
            text = (
                f"⚡ **Results for:** `{query}`\n"
                f"📂 **Found:** {total_results} files\n"
                f"⏳ **Time:** {time_taken}s\n\n"
                f"👇 **Click the button below to view results online**"
            )
            
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            
            # Add How To Button
            if howto_btn: btn.append(howto_btn[0])
            # Add Free Premium Button
            btn.append(free_prem_btn)
            
            # Pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id, "all")
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(
                text, 
                reply_markup=InlineKeyboardMarkup(btn)
            )

        # --- MODE E: CARD (Single Result) ---
        elif mode == 'card':
            file = files[0]
            text = format_card_result(file, 0, total_results)
            
            btn = []
            link_id = file['link_id']
            chat_id = message.chat.id
            btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])

            # Add How To Button
            if howto_btn: btn.append(howto_btn[0])
            # Add Free Premium Button
            btn.append(free_prem_btn)

            if total_results > 1:
                # ⚠️ Use unique_id in callback data
                btn.append([
                    InlineKeyboardButton(f"1/{total_results}", callback_data="pages"),
                    InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{unique_id}_0")
                ])

            sent_msg = await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))
            
        # ==================================================================
        # 🗑️ AUTO-DELETE LOGIC (POST-SEND)
        # ==================================================================
        
        if sent_msg:
            # 1. Delete User Message (Instant) if enabled
            if user_del:
                try: await message.delete()
                except: pass
            
            # 2. Schedule Bot Message Deletion
            if auto_del_time > 0:
                asyncio.create_task(
                    auto_delete_task(
                        sent_msg,   # The message bot sent
                        message,    # The user's message (for replying)
                        auto_del_time, 
                        del_thanks,
                        query       # Pass query for the thanks caption
                    )
                )

    except Exception as e:
        logger.error(f"Search Error: {e}")


# ==============================================================================
# 🎯 FILTER BUTTON HANDLER (Videos / Docs / All)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^filter_media_"))
async def handle_filter_click(client, query):
    try:
        # Format: filter_media_{unique_id}_{type}
        _, _, unique_id, f_type = query.data.split("_")
        
        # 1. Get Session
        session = await Media.get_search_session(unique_id)
        if not session: return await query.answer("Search Expired.", show_alert=True)
        
        original_files = session['files']
        req = session['query']
        
        # 2. Apply Filter
        filtered_files = filter_by_type(original_files, f_type)
        total_results = len(filtered_files)
        
        if total_results == 0:
            return await query.answer(f"No {f_type}s found for this search!", show_alert=True)
            
        # 3. Settings & UI Setup
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        if mode == 'hybrid': mode = 'button' if len(filtered_files) <= limit else 'text'
        
        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]
        
        # 4. Generate Filter Buttons (Updated with Checkmark)
        filter_row, reset_row = get_filter_buttons(unique_id, f_type)
        
        offset = 0 # Reset to page 1
        
        # --- RENDER NEW RESPONSE ---
        if mode == 'button':
            buttons = btn_parser(filtered_files, query.message.chat.id, unique_id, offset, limit)
            
            # Add Filters
            if filter_row: buttons.append(filter_row)
            if reset_row: buttons.append(reset_row)
            
            if howto_btn: buttons.append(howto_btn[0])
            buttons.append(free_prem_btn)
            
            # Pagination (Pass current f_type)
            pagination = get_pagination_row(offset, limit, total_results, unique_id, f_type)
            if pagination: buttons.append(pagination)
            
            text = f"⚡ **Hey {query.from_user.mention}!**\n👻 **Results for:** `{req}`\n📂 **Filtered:** {f_type.capitalize()}"
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode == 'text':
            page_files = filtered_files[offset : offset + limit]
            text = format_text_results(page_files, req, query.message.chat.id)
            # Add header for filter
            text = f"📂 **Filter:** {f_type.capitalize()} Only\n\n" + text
            
            btn = []
            if filter_row: btn.append(filter_row)
            if reset_row: btn.append(reset_row)
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, unique_id, f_type)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))
            
        elif mode == 'detailed':
            page_files = filtered_files[offset : offset + limit]
            text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            text = f"📂 **Filter:** {f_type.capitalize()} Only\n\n" + text
            
            btn = []
            if filter_row: btn.append(filter_row)
            if reset_row: btn.append(reset_row)
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, unique_id, f_type)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Filter Error: {e}")
        await query.answer("Error filtering.", show_alert=True)


# ==============================================================================
# ⏭️ PAGINATION CALLBACK HANDLER (Next/Back Logic)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        # ✅ Updated Format: next_{unique_id}_{offset}_{active_filter}
        data_parts = query.data.split("_")
        unique_id = data_parts[1]
        offset = int(data_parts[2])
        
        # Check if filter param exists (backwards compatibility)
        active_filter = data_parts[3] if len(data_parts) > 3 else "all"
        
        # 1. Fetch Saved Data using Unique ID
        session = await Media.get_search_session(unique_id)
        
        if not session:
            return await query.answer("❌ Search expired or no files found.", show_alert=True)
            
        original_files = session['files']
        req = session['query'] # Original Query for display
        
        # ✅ Apply Filter Before slicing pages
        filtered_files = filter_by_type(original_files, active_filter)
        total_results = len(filtered_files)
        
        # 2. Get Settings Again
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10

        # Adjust Mode for Hybrid
        if mode == 'hybrid':
            mode = 'button' if len(filtered_files) <= limit else 'text'

        # ✅ NEW: Get How To Download URL (For Pagination)
        howto_url = group_settings.get('howto_url')
        howto_btn = []
        if howto_url:
            howto_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
            
        # ✅ NEW: Free Premium Button
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # ✅ Generate Filter Row (Keep current state)
        filter_row, reset_row = get_filter_buttons(unique_id, active_filter)

        # 3. Generate New Content
        
        # --- BUTTON MODE ---
        if mode == 'button':
            # Pass unique_id to btn_parser
            buttons = btn_parser(filtered_files, query.message.chat.id, unique_id, offset, limit)
            
            # Insert Filter Buttons
            if filter_row: buttons.append(filter_row)
            if reset_row: buttons.append(reset_row)

            # Add How To Button
            if howto_btn: buttons.append(howto_btn[0])
            # Add Free Premium
            buttons.append(free_prem_btn)
            
            # Pagination with active_filter
            pagination = get_pagination_row(offset, limit, total_results, unique_id, active_filter)
            if pagination: buttons.append(pagination)
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        # --- TEXT MODE ---
        elif mode == 'text':
            page_files = filtered_files[offset : offset + limit]
            text = format_text_results(page_files, req, query.message.chat.id)
            if active_filter != "all": text = f"📂 **Filter:** {active_filter.capitalize()}\n\n" + text
            
            btn = []
            if filter_row: btn.append(filter_row)
            if reset_row: btn.append(reset_row)
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn) # Add Free Premium
            
            # Pass unique_id to pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id, active_filter)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(
                text, 
                disable_web_page_preview=True, 
                reply_markup=InlineKeyboardMarkup(btn) if btn else None
            )

        # --- DETAILED MODE ---
        elif mode == 'detailed':
            page_files = filtered_files[offset : offset + limit]
            # Time taken passed as 0 or empty for edits
            text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            if active_filter != "all": text = f"📂 **Filter:** {active_filter.capitalize()}\n\n" + text
            
            btn = []
            if filter_row: btn.append(filter_row)
            if reset_row: btn.append(reset_row)
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn) # Add Free Premium
            
            # Pass unique_id to pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id, active_filter)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(
                text, 
                disable_web_page_preview=True, 
                reply_markup=InlineKeyboardMarkup(btn) if btn else None
            )

        # --- SITE MODE ---
        elif mode == 'site':
            # Reuse unique_id for site link
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            page_no = int(offset / limit) + 1
            final_site_url = f"{base_url}/results/{unique_id}?page={page_no}"
            
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn) # Add Free Premium
            
            # Pass unique_id to pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id, "all")
            if pagination: btn.append(pagination)
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Pagination Error: {e}")
        await query.answer("⚠️ Error switching page.", show_alert=True)

# Card Mode Handlers (Updated for Session ID)
@Client.on_callback_query(filters.regex(r"^card_next_"))
async def card_next_nav(client, query):
    try:
        # Format: card_next_{unique_id}_{current_index}
        _, _, unique_id, index = query.data.split("_") 
        current_index = int(index)
        
        # 1. Fetch Session
        session = await Media.get_search_session(unique_id)
        if not session: return await query.answer("Expired.", show_alert=True)
        files = session['files']
        
        total = len(files)
        next_index = current_index + 1
        if next_index >= total: next_index = 0
        file = files[next_index]
        text = format_card_result(file, next_index, total)
        
        # ✅ Fetch Settings for Buttons
        group_settings = await db.get_group_settings(query.message.chat.id)
        howto_url = group_settings.get('howto_url')
        
        btn = []
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])
        
        if howto_url: btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        # Add Free Premium
        btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])

        nav_row = []
        # Updated callbacks to use unique_id
        if next_index > 0: nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{unique_id}_{next_index}"))
        nav_row.append(InlineKeyboardButton(f"{next_index + 1}/{total}", callback_data="pages"))
        if next_index < total - 1: nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{unique_id}_{next_index}"))
        btn.append(nav_row)
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e: await query.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^card_prev_"))
async def card_prev_nav(client, query):
    try:
        # Format: card_prev_{unique_id}_{current_index}
        _, _, unique_id, index = query.data.split("_")
        current_index = int(index)
        
        # 1. Fetch Session
        session = await Media.get_search_session(unique_id)
        if not session: return await query.answer("Expired.", show_alert=True)
        files = session['files']
        
        total = len(files)
        prev_index = current_index - 1
        if prev_index < 0: prev_index = total - 1
        file = files[prev_index]
        text = format_card_result(file, prev_index, total)
        
        # ✅ Fetch Settings for Buttons
        group_settings = await db.get_group_settings(query.message.chat.id)
        howto_url = group_settings.get('howto_url')
        
        btn = []
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{chat_id}")])
        
        if howto_url: btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        # Add Free Premium
        btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
        
        nav_row = []
        # Updated callbacks to use unique_id
        if prev_index > 0: nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{unique_id}_{prev_index}"))
        nav_row.append(InlineKeyboardButton(f"{prev_index + 1}/{total}", callback_data="pages"))
        if prev_index < total - 1: nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{unique_id}_{prev_index}"))
        btn.append(nav_row)
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e: await query.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^pages$"))
async def page_counter_callback(client, query):
    await query.answer(f"Current Page Indicator", show_alert=False)
