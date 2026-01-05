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
# ✅ Added get_qualities to imports
from utils import temp, btn_parser, format_text_results, format_detailed_results, format_card_result, get_pagination_row, get_qualities

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

        # ✅ 3. Auto-Reaction Logic
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

        # ==================================================================
        # 🌟 NEW: Quality Filter Buttons
        # ==================================================================
        # Initialize with "None" filter
        qual_btn = [InlineKeyboardButton("Select Qualities 🔽", callback_data=f"qual_menu#{query}#None")]

        # --- MODE A: BUTTON ---
        if mode == 'button':
            buttons = btn_parser(files, message.chat.id, query, offset, limit)
            
            # Add Extra Buttons
            if howto_btn: buttons.append(howto_btn[0])
            buttons.append(qual_btn) # ✅ Add Quality Button
            buttons.append(free_prem_btn)

            # Pagination (Note: We pass query + #None for default filter)
            page_btn = get_pagination_row(offset, limit, total_results, f"{query}#None")
            if page_btn: buttons.append(page_btn)

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
            if howto_btn: btn.append(howto_btn[0])
            btn.append(qual_btn) # ✅ Add Quality Button
            btn.append(free_prem_btn)

            pagination = get_pagination_row(offset, limit, total_results, f"{query}#None")
            if pagination: btn.append(pagination)
            
            sent_msg = await message.reply_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(btn) if btn else None)

        # --- MODE C: DETAILED LIST ---
        elif mode == 'detailed':
            page_files = files[offset : offset + limit]
            text = format_detailed_results(page_files, query, message.chat.id, time_taken)
            
            btn = []
            if howto_btn: btn.append(howto_btn[0])
            btn.append(qual_btn) # ✅ Add Quality Button
            btn.append(free_prem_btn)

            pagination = get_pagination_row(offset, limit, total_results, f"{query}#None")
            if pagination: btn.append(pagination)
            
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
            btn.append(qual_btn) # ✅ Add Quality Button
            btn.append(free_prem_btn) # Add Free Premium

            # Pagination usually not needed for Site button, but kept for consistency if results > 0
            pagination = get_pagination_row(offset, limit, total_results, f"{query}#None")
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

            if howto_btn: btn.append(howto_btn[0])
            btn.append(qual_btn) # ✅ Add Quality Button
            btn.append(free_prem_btn)

            if total_results > 1:
                short_q = query[:20] 
                # Note: Card mode handles pagination internally differently, usually not needing filter hash 
                # but we keep standard prev/next
                btn.append([
                    InlineKeyboardButton(f"1/{total_results}", callback_data="pages"),
                    InlineKeyboardButton("Next ➡️", callback_data=f"card_next_0_{short_q}")
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
# 🌟 QUALITY SELECTION HANDLERS
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^qual_menu#"))
async def quality_menu_handler(client, query):
    # Data format: qual_menu#{query}#{current_filter}
    _, req_query, current_filter = query.data.split("#")
    
    # 1. Fetch ALL files again to count qualities
    files = await Media.get_search_results(req_query)
    if not files: return await query.answer("Expired.", show_alert=True)
    
    # 2. Extract Qualities
    qual_data = get_qualities(files)
    
    if not qual_data:
        return await query.answer("No specific qualities detected.", show_alert=True)
    
    buttons = []
    temp_row = []
    
    # 3. Create Quality Buttons
    for qual, count in qual_data.items():
        # Text: "720p (6)"
        btn_txt = f"{qual.upper()} ({count})"
        # Data: qual_select#{query}#{quality}
        temp_row.append(InlineKeyboardButton(btn_txt, callback_data=f"qual_select#{req_query}#{qual}"))
        
        if len(temp_row) == 3: # 3 buttons per row
            buttons.append(temp_row)
            temp_row = []
            
    if temp_row: buttons.append(temp_row)
    
    # Back Button (Returns to 'None' filter)
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"qual_select#{req_query}#None")])
    
    await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^qual_select#"))
async def quality_selection_handler(client, query):
    # Data format: qual_select#{query}#{selected_quality}
    _, req_query, selected_qual = query.data.split("#")
    
    # 1. Fetch Results
    files = await Media.get_search_results(req_query)
    if not files: return await query.answer("Expired.", show_alert=True)

    # 2. FILTER LOGIC
    filtered_files = []
    if selected_qual == "None":
        filtered_files = files # Show All
    else:
        # Filter list based on quality string in file name
        key = selected_qual.lower()
        if key == "4k":
             filtered_files = [f for f in files if "4k" in f['file_name'].lower() or "2160p" in f['file_name'].lower()]
        else:
             filtered_files = [f for f in files if key in f['file_name'].lower()]
             
    if not filtered_files:
        return await query.answer("No files found for this quality.", show_alert=True)

    # 3. Re-Generate Response (Like auto_filter but with filtered list)
    total_results = len(filtered_files)
    limit = 10 
    offset = 0
    
    # Re-fetch Settings for Consistency
    group_settings = await db.get_group_settings(query.message.chat.id)
    mode = group_settings.get('result_mode', 'hybrid')
    limit = group_settings.get('result_page_limit', 10)
    howto_url = group_settings.get('howto_url')
    
    if mode == 'hybrid':
        if len(filtered_files) <= limit: mode = 'button'
        else: mode = 'text'

    # 4. Define Buttons
    extra_btn = []
    if howto_url: extra_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])

    # 🌟 DYNAMIC QUALITY BUTTON UPDATE
    if selected_qual == "None":
        # Show standard "Select Qualities"
        extra_btn.append([InlineKeyboardButton("Select Qualities 🔽", callback_data=f"qual_menu#{req_query}#None")])
    else:
        # Show "720p ✅" and "All Qualities"
        extra_btn.append([
            InlineKeyboardButton(f"{selected_qual.upper()} ✅", callback_data=f"qual_menu#{req_query}#{selected_qual}"),
            InlineKeyboardButton("All Qualities 🔄", callback_data=f"qual_select#{req_query}#None")
        ])
    
    extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
    
    # Pagination (Pass the selected_qual in the callback!)
    page_btn = get_pagination_row(offset, limit, total_results, f"{req_query}#{selected_qual}")

    final_markup = []
    text = ""

    if mode == 'button':
        final_markup = btn_parser(filtered_files, query.message.chat.id, req_query, offset, limit)
        text = f"⚡ Results for `{req_query}`"
        if selected_qual != "None": text += f"\n🎯 **Filter:** {selected_qual.upper()}"

    elif mode in ['text', 'detailed']:
        page_files = filtered_files[offset : offset + limit]
        if mode == 'text': text = format_text_results(page_files, req_query, query.message.chat.id)
        else: text = format_detailed_results(page_files, req_query, query.message.chat.id)
        
    elif mode == 'site':
        search_id = await Media.save_search_results(req_query, filtered_files, query.message.chat.id)
        final_site_url = f"{SITE_URL}/results/{search_id}"
        text = f"⚡ Results for: `{req_query}`"
        if selected_qual != "None": text += f"\n🎯 **Filter:** {selected_qual.upper()}"
        final_markup = [[InlineKeyboardButton("🔎 View Results Online", url=final_site_url)]]

    # Assemble
    if mode == 'button':
        final_markup.extend(extra_btn)
        if page_btn: final_markup.append(page_btn)
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(final_markup))
    else:
        buttons = []
        if mode == 'site': buttons.extend(final_markup)
        buttons.extend(extra_btn)
        if page_btn: buttons.append(page_btn)
        
        await query.message.edit_text(
            text, 
            disable_web_page_preview=True, 
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None
        )

# ==============================================================================
# ⏭️ UPDATED PAGINATION HANDLER (Supports Filters)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^next_"))
async def handle_next_back(client, query):
    try:
        # Old Format: next_{offset}_{req}
        # New Format: next_{offset}_{req}#{filter}
        
        raw_data = query.data.split("_", 2)
        offset = int(raw_data[1])
        remainder = raw_data[2]
        
        # Parse Query and Filter
        if "#" in remainder:
            req_query, current_filter = remainder.split("#", 1)
        else:
            req_query = remainder
            current_filter = "None"
            
        # 1. Fetch Files
        files = await Media.get_search_results(req_query)
        if not files: return await query.answer("Expired.", show_alert=True)
        
        # 2. Apply Filter (Same logic as above)
        filtered_files = []
        if current_filter == "None":
            filtered_files = files
        else:
            key = current_filter.lower()
            if key == "4k":
                 filtered_files = [f for f in files if "4k" in f['file_name'].lower() or "2160p" in f['file_name'].lower()]
            else:
                 filtered_files = [f for f in files if key in f['file_name'].lower()]
                 
        total_results = len(filtered_files)
        
        # 3. Get Settings
        group_settings = await db.get_group_settings(query.message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid')
        limit = group_settings.get('result_page_limit', 10)
        howto_url = group_settings.get('howto_url')
        
        if mode == 'hybrid':
            mode = 'button' if len(filtered_files) <= limit else 'text'

        # 4. Buttons (With Filter State)
        extra_btn = []
        if howto_url: extra_btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        
        # Quality Button State
        if current_filter == "None":
            extra_btn.append([InlineKeyboardButton("Select Qualities 🔽", callback_data=f"qual_menu#{req_query}#None")])
        else:
            extra_btn.append([
                InlineKeyboardButton(f"{current_filter.upper()} ✅", callback_data=f"qual_menu#{req_query}#{current_filter}"),
                InlineKeyboardButton("All Qualities 🔄", callback_data=f"qual_select#{req_query}#None")
            ])
            
        extra_btn.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])
        
        # Generate Output
        if mode == 'button':
            buttons = btn_parser(filtered_files, query.message.chat.id, req_query, offset, limit)
            buttons.extend(extra_btn)
            # Pass Filter to Pagination
            page_btn = get_pagination_row(offset, limit, total_results, f"{req_query}#{current_filter}")
            if page_btn: buttons.append(page_btn)
            
            await query.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
            
        elif mode in ['text', 'detailed']:
            page_files = filtered_files[offset : offset + limit]
            if mode == 'text': text = format_text_results(page_files, req_query, query.message.chat.id)
            else: text = format_detailed_results(page_files, req_query, query.message.chat.id)
            
            buttons = []
            buttons.extend(extra_btn)
            page_btn = get_pagination_row(offset, limit, total_results, f"{req_query}#{current_filter}")
            if page_btn: buttons.append(page_btn)
            
            await query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup(buttons))
            
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
        if prev_index > 0: nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{prev_index}_{q_text}"))
        nav_row.append(InlineKeyboardButton(f"{prev_index + 1}/{total}", callback_data="pages"))
        if prev_index < total - 1: nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{prev_index}_{q_text}"))
        btn.append(nav_row)
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e: await query.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^pages$"))
async def page_counter_callback(client, query):
    await query.answer(f"Current Page Indicator", show_alert=False)
