from aiohttp import web
import logging
import math
from requests import get
from utils import temp 

logger = logging.getLogger(__name__)

# ✅ In-Memory Cache to store search results
RESULTS_CACHE = {}

# ✅ Helper to get Public IP or Domain
def get_site_url():
    try:
        # Agar aapne config me URL set kiya hai to wo use karein
        from info import URL 
        if URL: return URL.rstrip("/")
    except: pass
    
    try:
        ip = get('https://api.ipify.org').text
        return f"http://{ip}"
    except:
        return "http://127.0.0.1"

# Cache URL on startup
SITE_URL = get_site_url()

async def handle_home(request):
    return web.Response(text="Bot is Running!")

async def handle_search_results(request):
    try:
        search_id = request.match_info['key']
        
        if search_id not in RESULTS_CACHE:
            return web.Response(text="❌ Link Expired or Invalid.", status=404)
        
        data = RESULTS_CACHE[search_id]
        all_files = data['files']
        query = data['query']
        chat_id = data['chat_id']
        
        # --- 🔢 PAGINATION LOGIC ---
        try: page = int(request.query.get('page', 1))
        except: page = 1
            
        per_page = 10
        total_results = len(all_files)
        total_pages = math.ceil(total_results / per_page)
        
        if page < 1: page = 1
        if page > total_pages: page = total_pages
        
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        current_files = all_files[start_index:end_index]
        
        start_count = start_index + 1
        end_count = min(end_index, total_results)
        
        # --- 📝 GENERATE HTML LIST ---
        list_items = ""
        for file in current_files:
            f_name = file['file_name']
            f_size = str(file.get('file_size', 0))
            
            # Size Formatting
            try:
                raw_size = float(f_size)
                if raw_size < 1024: size_str = f"{raw_size:.0f} B"
                elif raw_size < 1024**2: size_str = f"{raw_size/1024:.2f} KB"
                elif raw_size < 1024**3: size_str = f"{raw_size/1024**2:.2f} MB"
                else: size_str = f"{raw_size/1024**3:.2f} GB"
            except: size_str = str(f_size)

            link_id = file['link_id']
            
            # Bot Username fetch karna (Live)
            bot_username = temp.U_NAME if temp.U_NAME else "Telegram"
            link = f"https://t.me/{bot_username}?start=get_{link_id}_{chat_id}"
            
            list_items += f"""
            <div class="card" onclick="window.open('{link}', '_blank')">
                <div class="card-left-border"></div>
                <div class="card-body">
                    <div class="badges">
                        <span class="badge size-badge">{size_str}</span>
                        <span class="badge type-badge">Video</span>
                    </div>
                    <h3 class="filename">{f_name}</h3>
                    <a href="{link}" class="get-btn">📂 Get File</a>
                </div>
            </div>
            """

        # --- ⏭️ PAGINATION BUTTONS ---
        prev_style = "disabled" if page <= 1 else ""
        next_style = "disabled" if page >= total_pages else ""
        prev_link = f"?page={page-1}" if page > 1 else "#"
        next_link = f"?page={page+1}" if page < total_pages else "#"

        # --- 🖥️ DARK APP UI HTML ---
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
            <title>Results for {query}</title>
            <style>
                :root {{
                    --bg-color: #0f0f0f;
                    --card-bg: #1c1c1e;
                    --primary: #2979ff;
                    --text-main: #ffffff;
                    --text-muted: #9e9e9e;
                    --badge-bg: #263238;
                    --badge-text: #80d8ff;
                }}
                
                * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; -webkit-tap-highlight-color: transparent; }}
                body {{ background-color: var(--bg-color); color: var(--text-main); padding: 15px; max-width: 600px; margin: 0 auto; padding-bottom: 40px; }}
                
                /* Search Bar Area */
                .search-area {{ position: sticky; top: 0; background: var(--bg-color); padding: 10px 0; z-index: 100; }}
                .search-box {{ 
                    width: 100%; background: #000; border: 1px solid #333; padding: 12px 15px; 
                    border-radius: 12px; color: #fff; font-size: 16px; outline: none; box-shadow: 0 4px 12px rgba(0,0,0,0.5);
                }}
                .search-box:focus {{ border-color: var(--primary); }}
                
                /* Results Info */
                .header-info {{ margin: 20px 0 15px 0; display: flex; justify-content: space-between; align-items: center; }}
                .query-text {{ font-size: 18px; font-weight: bold; }}
                .query-highlight {{ color: var(--primary); }}
                .count-text {{ font-size: 12px; color: var(--text-muted); }}

                /* Cards */
                .card {{ 
                    background: var(--card-bg); border-radius: 12px; margin-bottom: 12px; 
                    position: relative; overflow: hidden; display: flex; box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                    cursor: pointer; transition: transform 0.1s;
                }}
                .card:active {{ transform: scale(0.98); background: #2c2c2e; }}
                
                .card-left-border {{ width: 5px; background: var(--primary); }}
                .card-body {{ padding: 15px; width: 100%; }}
                
                .badges {{ display: flex; gap: 8px; margin-bottom: 8px; }}
                .badge {{ background: var(--badge-bg); color: var(--badge-text); font-size: 11px; padding: 3px 8px; border-radius: 4px; font-weight: 600; text-transform: uppercase; }}
                
                .filename {{ font-size: 15px; line-height: 1.4; font-weight: 500; margin-bottom: 12px; word-break: break-word; }}
                
                .get-btn {{ 
                    display: inline-block; background: rgba(41, 121, 255, 0.15); color: var(--primary); 
                    text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 13px; font-weight: 600; 
                }}

                /* Pagination */
                .pagination {{ display: flex; justify-content: space-between; align-items: center; margin-top: 25px; background: var(--card-bg); padding: 10px; border-radius: 12px; }}
                .page-btn {{ 
                    padding: 10px 18px; background: var(--primary); color: white; border-radius: 8px; 
                    text-decoration: none; font-weight: bold; font-size: 14px; 
                }}
                .page-btn.disabled {{ background: #333; color: #666; pointer-events: none; }}
                .page-info {{ font-size: 13px; color: var(--text-muted); }}

            </style>
        </head>
        <body>
            
            <div class="search-area">
                <input type="text" class="search-box" value="{query}" readonly>
            </div>

            <div class="header-info">
                <div class="query-text">Results for <span class="query-highlight">"{query}"</span></div>
                <div class="count-text">{start_count}-{end_count} of {total_results}</div>
            </div>

            <div class="results-list">
                {list_items}
            </div>

            <div class="pagination">
                <a href="{prev_link}" class="page-btn {prev_style}">Prev</a>
                <span class="page-info">Page {page} of {total_pages}</span>
                <a href="{next_link}" class="page-btn {next_style}">Next</a>
            </div>

        </body>
        </html>
        """
        return web.Response(text=html_content, content_type='text/html')

    except Exception as e:
        logger.error(f"Web Error: {e}")
        return web.Response(text="Server Error", status=500)

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes([
        web.get('/', handle_home),
        web.get('/results/{key}', handle_search_results),
        web.get('/favicon.ico', handle_home) # Error preventer
    ])
    return web_app
