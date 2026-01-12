from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup
from database.ia_filterdb import Media
from utils import btn_parser, get_pagination_row, get_filter_buttons # Import the new function

@Client.on_callback_query(filters.regex(r"^(filter|unfilter)_"))
async def filter_media_handler(client, query):
    try:
        # Data Format: filter_{search_id}_{mode}_{offset}
        # Example: filter_uuid123_video_0
        _, search_id, mode, offset = query.data.split("_")
        offset = int(offset)
        
        # Determine strict Filter Type for DB
        # If 'unfilter' was clicked, we set filter_type to None
        filter_type = mode if query.data.startswith("filter") else None
        
        # 1. Fetch the Search Session
        session = await Media.get_search_session(search_id)
        if not session:
            return await query.answer("❌ Search expired. Please search again.", show_alert=True)
            
        original_query = session['query']
        chat_id = query.message.chat.id
        
        # 2. Get Settings (Page Limit)
        # Assuming you have a DB function for this
        limit = 10 
        
        # 3. DB Query with FILTER LOGIC
        # We perform a fresh search with the specific file_type restriction
        if filter_type:
            # Filtered Search: query + file_type
            files = await Media.get_search_results(original_query, file_type=filter_type)
        else:
            # Normal Search: query only
            files = await Media.get_search_results(original_query)
            
        if not files:
            return await query.answer(f"No {mode} files found for this search.", show_alert=True)

        # 4. Generate Results (Buttons)
        # Using your existing btn_parser
        files_page = files[offset : offset + limit]
        
        # Create Result Buttons
        # Note: You might need to update btn_parser to handle the 'files' list directly
        # or slice it here manually as done above.
        result_buttons = btn_parser(files, chat_id, search_id, offset, limit)
        
        # 5. Inject Filter Buttons (The UI Requirement)
        filter_buttons = get_filter_buttons(search_id, active_mode=filter_type)
        for row in reversed(filter_buttons):
            result_buttons.append(row)

        # 6. Add Pagination (Must pass the active filter mode!)
        # You will need to update get_pagination_row to accept 'mode'
        # or handle pagination callbacks to include the current mode.
        total_results = len(files)
        
        # Simple Pagination Row Construction for this example:
        nav_buttons = []
        if offset >= limit:
            nav_cmd = "filter" if filter_type else "unfilter"
            nav_mode = filter_type if filter_type else "all"
            nav_buttons.append(InlineKeyboardButton("⬅️ Back", callback_data=f"{nav_cmd}_{search_id}_{nav_mode}_{offset-limit}"))
            
        nav_buttons.append(InlineKeyboardButton(f"{int(offset/limit)+1}/{int(total_results/limit)+1}", callback_data="pages"))
        
        if offset + limit < total_results:
            nav_cmd = "filter" if filter_type else "unfilter"
            nav_mode = filter_type if filter_type else "all"
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"{nav_cmd}_{search_id}_{nav_mode}_{offset+limit}"))
            
        if nav_buttons:
            result_buttons.append(nav_buttons)

        # 7. Add Standard Footer Buttons (How To, Language, etc.)
        # Assuming you have these defined
        result_buttons.append([InlineKeyboardButton("⁉️ How to Download", url="https://t.me/example")])

        # 8. Update Message
        txt = f"⚡ **Filtered Results ({mode.capitalize()})**\nFound {total_results} files for `{original_query}`"
        
        await query.message.edit_text(
            text=txt,
            reply_markup=InlineKeyboardMarkup(result_buttons)
        )
        
    except Exception as e:
        print(f"Filter Error: {e}")
        await query.answer("Error filtering results.", show_alert=True)
