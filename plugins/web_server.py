from aiohttp import web
import logging
import math
from requests import get
# ✅ Fix: Import temp instead of static U_NAME
from utils import temp

logger = logging.getLogger(__name__)

# ✅ In-Memory Cache to store search results
RESULTS_CACHE = {}

# ✅ Helper to get Public IP
def get_public_ip():
    try:
        ip = get('https://api.ipify.org').text
        return ip
    except:
        return "127.0.0.1"

# Cache IP on startup
PUBLIC_IP = get_public_ip()

async def handle_home(request):
    return web.Response(text="Bot is Running!")

async def handle_search_results(request):
    try:
        search_id = request.match_info['key']
        
        # Check if ID exists in cache
        if search_id not in RESULTS_CACHE:
            return web.Response(text="❌ Link Expired or Invalid.", status=404)
        
        data = RESULTS_CACHE[search_id]
        all_files = data['files']
        query = data['query']
        chat_id = data['chat_id']
        
        # --- 🔢 PAGINATION LOGIC ---
        try:
            page = int(request.query.get('page', 1))
        except ValueError:
            page = 1
            
        per_page = 10
        total_results = len(all_files)
        total_pages = math.ceil(total_results / per_page)
        
        # Adjust page bounds
        if page < 1: page = 1
        if page > total_pages: page = total_pages
        
        start_index = (page - 1) * per_page
        end_index = start_index + per_page
        
        current_files = all_files[start_index:end_index]
        
        # UI Helpers
        start_count = start_index + 1
        end_count = min(end_index, total_results)
        
        # --- 📝 GENERATE LIST HTML ---
        list_items = ""
        for file in current_files:
            f_name = file['file_name']
            f_size = str(file.get('file_size', 0))
            
            try:
                raw_size = float(f_size)
                if raw_size < 1024: size_str = f"{raw_size:.0f} B"
                elif raw_size < 1024**2: size_str = f"{raw_size/1024:.2f} KB"
                elif raw_size < 1024**3: size_str = f"{raw_size/1024**2:.2f} MB"
                else: size_str = f"{raw_size/1024**3:.2f} GB"
            except:
                size_str = str(f_size)

            link_id = file['link_id']
            
            # ✅ FIX: Use temp.U_NAME (Live Username)
            # Agar temp.U_NAME available nahi hai to fallback handle karein
            bot_username = temp.U_NAME if temp.U_NAME else "YourBotName"
            link = f"https://t.me/{bot_username}?start=get_{link_id}_{chat_id}"
            
            list_items += f"""
            <a href="{link}" class="card-link" target="_blank">
                <div class="card">
                    <div class="card-border"></div>
                    <div class="card-content">
                        <div class="file-badges">
                            <span class="badge size-badge">[{size_str}]</span>
                        </div>
                        <h3 class="file-name">{f_name}</h3>
                        <p class="file-type">Video</p>
                    </div>
                </div>
            </a>
            """

        # --- ⏭️ PAGINATION BUTTONS ---
        prev_btn_class = "nav-btn" if page > 1 else "nav-btn disabled"
        prev_link = f"?page={page-1}" if page > 1 else "#"
        
        next_btn_class = "nav-btn next" if page < total_pages else "nav-btn disabled"
        next_link = f"?page={page+1}" if page < total_pages else "#"

        prev_html = f'<a href="{prev_link}" class="{prev_btn_class}">◀ Prev</a>'
        next_html = f'<a href="{next_link}" class="{next_btn_class}">Next ▶</a>'

        # --- 🖥️ HTML UI (Dark Theme) ---
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Results for "{query}"</title>
            <style>
                :root {{
                    --bg-color: #121212;
                    --card-bg: #1e1e1e;
                    --text-primary: #ffffff;
                    --text-secondary: #aaaaaa;
                    --accent-blue: #2196f3;
                    --badge-bg: #2c3e50;
                    --badge-text: #81d4fa;
                }}
                
                * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}
                body {{ background-color: var(--bg-color); color: var(--text-primary); padding: 20px; max-width: 800px; margin: 0 auto; }}
                
                .search-container {{ margin-bottom: 30px; }}
                .search-box {{ 
                    width: 100%; padding: 15px; background: #000; border: 2px solid #333; 
                    border-radius: 10px; color: white; font-size: 16px; outline: none;
                }}
                .search-box:focus {{ border-color: var(--accent-blue); box-shadow: 0 0 10px rgba(33, 150, 243, 0.3); }}
                
                .search-btn {{
                    width: 100%; margin-top: 10px; padding: 12px; background: #0066ff;
                    color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: bold; cursor: pointer;
                }}
                
                .results-header {{ text-align: center; margin-bottom: 20px; }}
                .results-title {{ font-size: 24px; margin-bottom: 5px; }}
                .highlight {{ color: #00aaff; }}
                .results-count {{ color: var(--text-secondary); font-size: 14px; }}
                
                .card-link {{ text-decoration: none; color: inherit; display: block; margin-bottom: 15px; }}
                .card {{ 
                    background-color: var(--card-bg); border-radius: 8px; overflow: hidden; 
                    position: relative; display: flex; transition: transform 0.2s;
                }}
                .card:active {{ transform: scale(0.98); }}
                .card-border {{ width: 6px; background-color: var(--accent-blue); }}
                .card-content {{ padding: 15px; width: 100%; }}
                
                .file-badges {{ margin-bottom: 8px; }}
                .badge {{ 
                    background-color: var(--badge-bg); color: var(--badge-text); 
                    padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;
                }}
                
                .file-name {{ font-size: 16px; line-height: 1.4; margin-bottom: 5px; color: #fff; }}
                .file-type {{ color: #666; font-size: 13px; font-weight: 500; }}
                
                .pagination {{ 
                    display: flex; justify-content: space-between; align-items: center; 
                    margin-top: 30px; background: #1a1a1a; padding: 10px; border-radius: 10px;
                }}
                
                .nav-btn {{
                    padding: 10px 20px; background-color: #333; color: white; text-decoration: none;
                    border-radius: 6px; font-weight: bold; display: flex; align-items: center;
                }}
                .nav-btn:hover:not(.disabled) {{ background-color: #444; }}
                .nav-btn.disabled {{ opacity: 0.5; cursor: default; pointer-events: none; }}
                .page-info {{ color: #888; font-size: 14px; }}
                
            </style>
        </head>
        <body>
        
            <div class="search-container">
                <input type="text" class="search-box" value="{query}" readonly>
                <button class="search-btn">Search</button>
            </div>

            <div class="results-header">
                <h1 class="results-title">Results for: <span class="highlight">"{query}"</span></h1>
                <p class="results-count">Showing {start_count}-{end_count} of {total_results} results</p>
            </div>

            <div class="file-list">
                {list_items}
            </div>

            <div class="pagination">
                {prev_html}
                <span class="page-info">Page {page} of {total_pages}</span>
                {next_html}
            </div>

        </body>
        </html>
        """
        
        return web.Response(text=html_content, content_type='text/html')

    except Exception as e:
        logger.error(f"Web Page Error: {e}")
        return web.Response(text="Internal Server Error", status=500)

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes([
        web.get('/', handle_home),
        web.get('/results/{key}', handle_search_results)
    ])
    return web_app
