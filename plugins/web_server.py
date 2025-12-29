from aiohttp import web
import logging
import aiohttp_jinja2
import jinja2
from database.ia_filterdb import Media

logger = logging.getLogger(__name__)

async def handle_home(request):
    return web.Response(text="Bot is Running Successfully! Site Mode Active.")

async def handle_search_results(request):
    search_id = request.match_info.get('key')
    
    # 1. Fetch Data from MongoDB
    data = await Media.get_cached_results(search_id)
    
    if not data:
        return web.Response(text="❌ Link Expired or Invalid.", status=404)
    
    # 2. Get User/Group ID associated with this search
    # This was saved in ia_filterdb.py during the search
    user_chat_id = data.get('chat_id')
    
    # 3. Process Files to ensure Chat ID exists for deep linking
    files_list = []
    raw_files = data.get('files', [])
    
    for file in raw_files:
        # Determine the Chat ID to use in the link
        # Priority: File's specific Source Chat ID > The Searcher's Chat ID
        # 'file_chat_id' is retrieved from the DB save structure we made earlier
        target_chat_id = file.get('file_chat_id')
        
        # Fallback: If file source ID is missing, use the user's chat ID
        # This prevents the "None" error
        if not target_chat_id:
            target_chat_id = user_chat_id
            
        # Inject this ID into the file dictionary so Jinja can use it
        file['target_chat_id'] = target_chat_id
        
        files_list.append(file)
    
    # 4. Prepare Context for Template
    context = {
        "query": data.get('query'),
        "files": files_list,
        "total": len(files_list),
        # Bot username is passed from bot.py app context
        "bot_username": request.app.get('bot_username', 'Telegram') 
    }
    
    # 5. Render Template
    return aiohttp_jinja2.render_template('results.html', request, context)

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    
    # ✅ Setup Jinja2 Template Loader
    # Looks for 'templates' folder in your root directory
    aiohttp_jinja2.setup(web_app, loader=jinja2.FileSystemLoader('templates'))
    
    # Routes
    web_app.add_routes([
        web.get('/', handle_home),
        web.get('/results/{key}', handle_search_results),
    ])
    
    return web_app
