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
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row, get_filter_buttons

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

        # ✅ 3. SAVE SESSION (Generates Unique ID for Cache)
        # We pass file_type=None because this is a fresh global search
        unique_id = await Media.save_search_result(query, files, file_type=None)

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

        # ✅ NEW: Get How To Download URL
        howto_url = group_settings.get('howto_url')
        howto_btn = []
        if howto_url:
            howto_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
            
        # ✅ NEW: Free Premium Button
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # --- MODE A: BUTTON ---
        if mode == 'button':
            # ✅ Pass unique_id and query
            buttons = btn_parser(files, message.chat.id, unique_id, query, offset, limit)
            
            # ✅ INJECT FILTER BUTTONS (Video/Docs)
            # Default is None (All Files)
            filter_btns = get_filter_buttons(unique_id, active_mode=None)
            for row in reversed(filter_btns):
                buttons.append(row)

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
            
            # ✅ INJECT FILTER BUTTONS
            filter_btns = get_filter_buttons(unique_id, active_mode=None)
            for row in filter_btns:
                btn.append(row)

            # Add How To Button FIRST
            if howto_btn: btn.append(howto_btn[0])
            # Add Free Premium Button
            btn.append(free_prem_btn)

            # ✅ Use unique_id for pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE C: DETAILED LIST ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            
            # ✅ INJECT FILTER BUTTONS
            filter_btns = get_filter_buttons(unique_id, active_mode=None)
            for row in filter_btns:
                btn.append(row)

            # Add How To Button FIRST
            if howto_btn: btn.append(howto_btn[0])
            # Add Free Premium Button
            btn.append(free_prem_btn)

            # ✅ Use unique_id for pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id)
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE D: SITE (WEB VIEW) ---
        elif mode == 'site':
            # Use same unique_id for site
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

            # ✅ Use unique_id for pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id)
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
                # ✅ Use unique_id in callback
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
# ⏭️ PAGINATION CALLBACK HANDLER (Next/Back Logic)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        # ✅ Callback Format: next_{unique_id}_{offset}
        _, unique_id, offset = query.data.split("_") 
        offset = int(offset)
        
        # 1. Fetch Saved Data using Unique ID (Session)
        session = await Media.get_search_session(unique_id)
        
        if not session:
            return await query.answer("❌ Search expired or no files found.", show_alert=True)
            
        files = session['files']
        req = session['query'] # Original Query for display
        
        # ✅ CRITICAL: Retrieve the 'file_type' (Video/Doc) from session to maintain state
        active_filter = session.get('file_type') 
        
        total_results = len(files)
        
        # 2. Get Settings Again
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10

        # Adjust Mode for Hybrid
        if mode == 'hybrid':
            mode = 'button' if len(files) <= limit else 'text'

        # ✅ NEW: Get How To Download URL
        howto_url = group_settings.get('howto_url')
        howto_btn = []
        if howto_url:
            howto_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
            
        # ✅ NEW: Free Premium Button
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # 3. Generate New Content
        
        # --- BUTTON MODE ---
        if mode == 'button':
            # ✅ Pass unique_id and req (query)
            buttons = btn_parser(files, query.message.chat.id, unique_id, req, offset, limit)
            
            # ✅ RE-INJECT FILTER BUTTONS (Passing 'active_filter' to keep checkmark ✅)
            filter_btns = get_filter_buttons(unique_id, active_mode=active_filter)
            for row in reversed(filter_btns):
                buttons.append(row)

            # Add How To Button
            if howto_btn: buttons.append(howto_btn[0])
            # Add Free Premium
            buttons.append(free_prem_btn)
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        # --- TEXT MODE ---
        elif mode == 'text':
            page_files = files[offset : offset + limit]
            text = format_text_results(page_files, req, query.message.chat.id)
            
            btn = []
            
            # ✅ RE-INJECT FILTER BUTTONS (Passing 'active_filter')
            filter_btns = get_filter_buttons(unique_id, active_mode=active_filter)
            for row in filter_btns:
                btn.append(row)

            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn) 
            
            # ✅ Use unique_id for pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(
                text, 
                disable_web_page_preview=True, 
                reply_markup=InlineKeyboardMarkup(btn) if btn else None
            )

        # --- DETAILED MODE ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            
            btn = []
            
            # ✅ RE-INJECT FILTER BUTTONS
            filter_btns = get_filter_buttons(unique_id, active_mode=active_filter)
            for row in filter_btns:
                btn.append(row)

            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn) 
            
            # ✅ Use unique_id for pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(
                text, 
                disable_web_page_preview=True, 
                reply_markup=InlineKeyboardMarkup(btn) if btn else None
            )

        # --- SITE MODE ---
        elif mode == 'site':
            base_url = SITE_URL.rstrip('/') if (SITE_URL and SITE_URL.startswith("http")) else "http://127.0.0.1:8080"
            page_no = int(offset / limit) + 1
            final_site_url = f"{base_url}/results/{unique_id}?page={page_no}"
            
            btn = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]
            
            if howto_btn: btn.append(howto_btn[0])
            btn.append(free_prem_btn) 
            
            # ✅ Use unique_id for pagination
            pagination = get_pagination_row(offset, limit, total_results, unique_id)
            if pagination: btn.append(pagination)
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Pagination Error: {e}")
        await query.answer("⚠️ Error switching page.", show_alert=True)

# ==============================================================================
# 🎞️ FILTER CALLBACK HANDLER (Strict Video vs Docs Logic)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^(filter_|unfilter_)"))
async def filter_media_handler(client, query):
    try:
        # Parse Data
        data = query.data
        if data.startswith("unfilter_"):
            action = "reset"
            _, unique_id = data.split("_")
            filter_type = None
        else:
            # format: filter_video_{unique_id} or filter_doc_{unique_id}
            _, f_type, unique_id = data.split("_")
            action = "filter"
            # Map simplified callback data to DB values
            filter_type = "video" if f_type == "video" else "document"

        # 1. Retrieve Original Search Query from Old Session
        old_session = await Media.get_search_session(unique_id)
        if not old_session:
            return await query.answer("⚠️ Search expired. Please search again.", show_alert=True)
            
        original_query = old_session['query']

        # 2. Perform NEW Strict Database Search
        # This calls our modified get_search_results with the file_type argument
        files = await Media.get_search_results(original_query, file_type=filter_type)
        
        if not files:
            return await query.answer(f"❌ No {filter_type}s found for this search!", show_alert=True)

        # 3. Create NEW Session for this Filtered View
        # ✅ CRITICAL: Save 'filter_type' so pagination knows we are in a filtered view
        new_unique_id = await Media.save_search_result(original_query, files, file_type=filter_type)
        
        # 4. Generate New Buttons
        group_settings = await db.get_group_settings(query.message.chat.id)
        limit = group_settings.get('result_page_limit', 10) if group_settings else 10
        howto_url = group_settings.get('howto_url')
        
        # A. File Buttons (Page 1)
        buttons = btn_parser(files, query.message.chat.id, new_unique_id, original_query, 0, limit)
        
        # B. Inject Filter Buttons (The Toggle UI)
        filter_btns = get_filter_buttons(new_unique_id, active_mode=filter_type)
        for row in reversed(filter_btns): 
            buttons.append(row) 

        # C. Add Extra Buttons 
        extras = []
        if howto_url: extras.append(InlineKeyboardButton("⁉️ How To Download", url=howto_url))
        extras.append(InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info"))
        
        if extras: buttons.append(extras)

        # 5. Update Message
        mode_text = filter_type.capitalize() if filter_type else "All Files"
        text = (
            f"⚡ **Results for:** `{original_query}`\n"
            f"🎞 **Filter:** {mode_text}\n"
            f"📂 **Found:** {len(files)} matches"
        )
        
        await query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except Exception as e:
        logger.error(f"Filter Error: {e}")
        await query.answer("⚠️ Error filtering results.", show_alert=True)


# ==============================================================================
# 🃏 CARD MODE CALLBACKS (Updated for Unique ID)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^card_next_"))
async def card_next_nav(client, query):
    try:
        # Format: card_next_{unique_id}_{current_index}
        _, _, unique_id, index = query.data.split("_") 
        current_index = int(index)
        
        # Fetch Session
        session = await Media.get_search_session(unique_id)
        if not session: return await query.answer("Expired.", show_alert=True)
        files = session['files']
        
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
        
        # Fetch Session
        session = await Media.get_search_session(unique_id)
        if not session: return await query.answer("Expired.", show_alert=True)
        files = session['files']
        
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
