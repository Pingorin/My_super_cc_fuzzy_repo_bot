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
    filter_by_type, 
    get_dynamic_filter_buttons # ✅ New Helper
)

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
        
        # 1. Dynamic Filter Buttons (Default: All)
        filter_row = get_dynamic_filter_buttons(unique_id, "all", 0)
        
        # 2. How To Download URL
        howto_url = group_settings.get('howto_url')
        howto_btn = []
        if howto_url:
            howto_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
            
        # 3. Free Premium Button
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # --- MODE A: BUTTON ---
        if mode == 'button':
            # Explicitly pass arguments to prevent errors
            buttons = btn_parser(files, message.chat.id, unique_id, query=query, offset=offset, limit=limit)
            
            # ✅ Add Filters (Swapping Logic)
            if filter_row: buttons.append(filter_row)
            
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
# 🎬 FILTER BUTTON HANDLER (Videos / Docs)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^filter_"))
async def filter_media_handler(client, query):
    # Regex structure: filter_{search_id}_mode_{type}_{page}
    try:
        data = query.data.split("_")
        # index 0=filter, 1=search_id, 2=mode, 3=type, 4=page
        search_id = data[1]
        target_type = data[3]  # 'video' or 'document'
        page = int(data[4])
        
        # 1. Fetch the Session (Original Query Results)
        session = await Media.get_search_session(search_id)
        if not session:
            return await query.answer("❌ Search expired. Please search again.", show_alert=True)
            
        original_files = session['files']
        original_query = session['query']
        
        # 2. Filter the files using helper
        filtered_files = filter_by_type(original_files, target_type)
        total_results = len(filtered_files)

        if total_results == 0:
            return await query.answer(f"⚠️ No {target_type}s found in this search!", show_alert=True)

        # 3. Get User Settings
        settings = await db.get_group_settings(query.message.chat.id)
        limit = settings.get('result_page_limit', 10) if settings else 10
        offset = page * limit
        mode = settings.get('result_mode', 'hybrid') if settings else 'hybrid'
        if mode == 'hybrid': mode = 'button' if len(filtered_files) <= limit else 'text'

        # 4. Prepare Extras
        howto_url = settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]
        
        # 5. Get Filter Buttons (Swapped)
        filter_row = get_dynamic_filter_buttons(search_id, target_type, page)

        # --- RENDER ---
        if mode == 'button':
            buttons = btn_parser(filtered_files, query.message.chat.id, search_id, offset=offset, limit=limit)
            
            if filter_row: buttons.append(filter_row)
            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)
            
            # Pagination (Pass target_type)
            pagination = get_pagination_row(offset, limit, total_results, search_id, target_type)
            if pagination: buttons.append(pagination)

            text = f"⚡ **Results for:** `{original_query}`\n📂 **Filter:** {target_type.capitalize()} Only ✅"
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode == 'text':
            page_files = filtered_files[offset : offset + limit]
            text = format_text_results(page_files, original_query, query.message.chat.id)
            text = f"📂 **Filter:** {target_type.capitalize()} Only ✅\n\n" + text
            
            btn = []
            if filter_row: btn.append(filter_row)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, search_id, target_type)
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Filter Error: {e}")
        await query.answer("Error applying filter.", show_alert=True)


# ==============================================================================
# 🔄 UNFILTER HANDLER (Reset to All)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^unfilter_"))
async def unfilter_media_handler(client, query):
    # Regex structure: unfilter_{search_id}_mode_
    try:
        data = query.data.split("_")
        search_id = data[1]
        
        # 1. Fetch Session
        session = await Media.get_search_session(search_id)
        if not session:
            return await query.answer("❌ Search expired.", show_alert=True)

        # 2. Get ORIGINAL files (No Filtering)
        all_files = session['files']
        original_query = session['query']
        total_results = len(all_files)

        # 3. Settings
        settings = await db.get_group_settings(query.message.chat.id)
        limit = settings.get('result_page_limit', 10) if settings else 10
        offset = 0 # Reset to first page
        mode = settings.get('result_mode', 'hybrid') if settings else 'hybrid'
        if mode == 'hybrid': mode = 'button' if len(all_files) <= limit else 'text'

        # 4. Prepare Extras
        howto_url = settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # 5. Get Filter Buttons (Mode = 'all')
        filter_row = get_dynamic_filter_buttons(search_id, "all", 0)

        # --- RENDER ---
        if mode == 'button':
            buttons = btn_parser(all_files, query.message.chat.id, search_id, offset=offset, limit=limit)
            
            if filter_row: buttons.append(filter_row)
            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)
            
            # Pagination (Pass 'all')
            pagination = get_pagination_row(offset, limit, total_results, search_id, "all")
            if pagination: buttons.append(pagination)
            
            text = f"⚡ **Results for:** `{original_query}`\n📂 **Filter:** All Media Types"
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode == 'text':
            page_files = all_files[offset : offset + limit]
            text = format_text_results(page_files, original_query, query.message.chat.id)
            
            btn = []
            if filter_row: btn.append(filter_row)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, search_id, "all")
            if pagination: btn.append(pagination)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Unfilter Error: {e}")
        await query.answer("Error resetting filter.", show_alert=True)


# ==============================================================================
# ⏭️ PAGINATION CALLBACK HANDLER (Next/Back Logic)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        # ✅ Separator is '_' because that's what we used in get_pagination_row
        # Format: next_{unique_id}_{offset}_{active_filter}
        data_parts = query.data.split("_")
        unique_id = data_parts[1]
        offset = int(data_parts[2])
        
        # Check if filter param exists
        active_filter = data_parts[3] if len(data_parts) > 3 else "all"
        
        # 1. Fetch Saved Data using Unique ID
        session = await Media.get_search_session(unique_id)
        
        if not session:
            return await query.answer("❌ Search expired or no files found.", show_alert=True)
            
        original_files = session['files']
        req = session['query']
        
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

        howto_url = group_settings.get('howto_url')
        howto_btn = [InlineKeyboardButton("⁉️ How To Download", url=howto_url)] if howto_url else []
        free_prem_btn = [InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")]

        # ✅ Generate Filter Row (Keep current state)
        filter_row = get_dynamic_filter_buttons(unique_id, active_filter, int(offset/limit))

        # 3. Generate New Content
        
        # --- BUTTON MODE ---
        if mode == 'button':
            buttons = btn_parser(filtered_files, query.message.chat.id, unique_id, query=None, offset=offset, limit=limit)
            
            if filter_row: buttons.append(filter_row)
            if howto_btn: buttons.append(howto_btn)
            buttons.append(free_prem_btn)
            
            # Pagination with active_filter
            pagination = get_pagination_row(offset, limit, total_results, unique_id, active_filter)
            if pagination: buttons.append(pagination)
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        # --- TEXT MODE ---
        elif mode == 'text':
            page_files = filtered_files[offset : offset + limit]
            text = format_text_results(page_files, req, query.message.chat.id)
            if active_filter != "all": text = f"📂 **Filter:** {active_filter.capitalize()} Only ✅\n\n" + text
            
            btn = []
            if filter_row: btn.append(filter_row)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn) 
            
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
            text = format_detailed_results(page_files, req, query.message.chat.id, time_taken=0)
            if active_filter != "all": text = f"📂 **Filter:** {active_filter.capitalize()} Only ✅\n\n" + text
            
            btn = []
            if filter_row: btn.append(filter_row)
            if howto_btn: btn.append(howto_btn)
            btn.append(free_prem_btn)
            
            pagination = get_pagination_row(offset, limit, total_results, unique_id, active_filter)
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
            
            pagination = get_pagination_row(offset, limit, total_results, unique_id, "all")
            if pagination: btn.append(pagination)
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Pagination Error: {e}")
        await query.answer("⚠️ Error switching page.", show_alert=True)
