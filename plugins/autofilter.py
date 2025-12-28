import logging
import time
import re
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.ia_filterdb import Media
from database.users_chats_db import db
# ✅ Import helpers from utils
from utils import btn_parser, format_text_results, format_detailed_results, post_to_telegraph, format_card_result

logger = logging.getLogger(__name__)

@Client.on_message(filters.text & filters.incoming & ~filters.command(["start", "index", "stats", "delete_all", "fix_index", "set_shortner", "settings", "connect", "delreq"]))
async def auto_filter(client, message):
    
    raw_query = message.text
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
        # ✅ 1. Get Group Settings (Default to Hybrid)
        group_settings = await db.get_group_settings(message.chat.id)
        mode = group_settings.get('result_mode', 'hybrid') if group_settings else 'hybrid'

        # ✅ 2. Fetch Results
        files = await Media.get_search_results(query)
        
        end_time = time.time()
        time_taken = round(end_time - start_time, 2)

        if not files:
            # Optional: Uncomment to send "No Results" message
            # await message.reply_text(f"❌ **No results found for:** `{query}`")
            return

        # ==================================================================
        # 🔀 MODE DISPATCHER (Dynamic Display Logic)
        # ==================================================================

        # --- HYBRID MODE LOGIC ---
        if mode == 'hybrid':
            if len(files) <= 5: mode = 'button'
            else: mode = 'text'

        # --- MODE A: BUTTON (Classic) ---
        if mode == 'button':
            buttons = btn_parser(files, message.chat.id, query)
            msg_text = (
                f"⚡ **Hey {message.from_user.mention}!**\n"
                f"👻 **Here are your results for:** `{query}`\n"
                f"⏳ **Time Taken:** {time_taken} seconds"
            )
            await message.reply_text(
                text=msg_text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # --- MODE B: TEXT LIST ---
        elif mode == 'text':
            # Slice for max 20 results
            display_files = files[:20]
            # ✅ Passed message.chat.id for link generation
            text = format_text_results(display_files, query, message.chat.id)
            await message.reply_text(text, disable_web_page_preview=True)

        # --- MODE C: DETAILED LIST ---
        elif mode == 'detailed':
            # Slice for max 10 results
            display_files = files[:10]
            # ✅ Passed message.chat.id AND time_taken
            text = format_detailed_results(display_files, query, message.chat.id, time_taken)
            await message.reply_text(text, disable_web_page_preview=True)

        # --- MODE D: SITE (TELEGRAPH) ---
        elif mode == 'site':
            if len(files) > 20:
                # ✅ Passed message.chat.id
                url = await post_to_telegraph(files, query, message.chat.id)
                if url:
                    btn = [[InlineKeyboardButton(f"🔎 View All {len(files)} Results", url=url)]]
                    await message.reply_text(
                        f"👻 **Found {len(files)} results for:** `{query}`\n"
                        f"⏳ **Time Taken:** {time_taken} seconds\n\n"
                        "Results are too long, view them on the site page.",
                        reply_markup=InlineKeyboardMarkup(btn)
                    )
                else:
                    # Fallback to buttons if telegraph fails
                    buttons = btn_parser(files, message.chat.id, query)
                    await message.reply_text(f"👻 Results: `{query}`", reply_markup=InlineKeyboardMarkup(buttons))
            else:
                # If few results, revert to standard text mode
                text = format_text_results(files, query, message.chat.id)
                await message.reply_text(text, disable_web_page_preview=True)

        # --- MODE E: CARD (Single Result View with Navigation) ---
        elif mode == 'card':
            # Show 1st result initially
            file = files[0]
            total = len(files)
            text = format_card_result(file, 0, total)
            
            # Navigation Buttons
            btn = []
            if total > 1:
                # Truncate query to avoid callback data limit (64 bytes)
                short_q = query[:20] 
                # Handler expects: card_next_CURRENTINDEX_QUERY
                btn.append([
                    InlineKeyboardButton("Next ➡️", callback_data=f"card_next_0_{short_q}")
                ])
            
            # Add Get Button
            link_id = file['link_id']
            chat_id = message.chat.id
            btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{client.username}?start=get_{link_id}_{chat_id}")])

            await message.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))

    except Exception as e:
        logger.error(f"Search Error: {e}")

# ==============================================================================
# ⏭️ CARD NAVIGATION HANDLERS (Next/Prev Logic)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^card_next_"))
async def card_next_nav(client, query):
    try:
        # Split max 3 times: card, next, index, query_string
        _, _, index, q_text = query.data.split("_", 3) 
        current_index = int(index)
        
        # Re-fetch files (Stateless pagination)
        files = await Media.get_search_results(q_text)
        if not files: return await query.answer("Results expired or not found.", show_alert=True)
        
        total = len(files)
        # Calculate Next Index
        next_index = current_index + 1
        if next_index >= total: next_index = 0 # Loop back to start
        
        file = files[next_index]
        text = format_card_result(file, next_index, total)
        
        btn = []
        btn.append([
            InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{next_index}_{q_text}"),
            InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{next_index}_{q_text}")
        ])
        
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{client.username}?start=get_{link_id}_{chat_id}")])
        
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)

@Client.on_callback_query(filters.regex(r"^card_prev_"))
async def card_prev_nav(client, query):
    try:
        _, _, index, q_text = query.data.split("_", 3)
        current_index = int(index)
        
        files = await Media.get_search_results(q_text)
        if not files: return await query.answer("Results expired.", show_alert=True)
        
        total = len(files)
        # Calculate Previous Index
        prev_index = current_index - 1
        if prev_index < 0: prev_index = total - 1 # Loop to end
        
        file = files[prev_index]
        text = format_card_result(file, prev_index, total)
        
        btn = [[
            InlineKeyboardButton("⬅️ Prev", callback_data=f"card_prev_{prev_index}_{q_text}"),
            InlineKeyboardButton("Next ➡️", callback_data=f"card_next_{prev_index}_{q_text}")
        ]]
        link_id = file['link_id']
        chat_id = query.message.chat.id
        btn.append([InlineKeyboardButton("📂 Get File", url=f"https://t.me/{client.username}?start=get_{link_id}_{chat_id}")])
        
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(btn))
    except Exception as e:
        await query.answer(f"Error: {e}", show_alert=True)
