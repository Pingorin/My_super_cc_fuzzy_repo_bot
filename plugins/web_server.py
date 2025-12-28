import logging
import aiohttp_jinja2
import jinja2
from aiohttp import web
from database.ia_filterdb import Media

logger = logging.getLogger(__name__)

async def handle_home(request):
    return web.Response(text="Bot is Running Successfully!")

async def handle_search_results(request):
    # URL se Unique Key (UUID) nikalein
    search_id = request.match_info.get('key')
    
    # MongoDB se Data Fetch karein
    # (Make sure aapne database/ia_filterdb.py me get_cached_results function add kiya hai)
    data = await Media.get_cached_results(search_id)
    
    if not data:
        return web.Response(text="❌ Link Expired or Invalid.", status=404)
    
    # Data ko Template me bhejne ke liye Context ready karein
    context = {
        "query": data.get('query'),
        "files": data.get('files'),
        "total": len(data.get('files', [])),
        # Bot username bot.py se pass hoga, fallback 'Telegram'
        "bot_username": request.app.get('bot_username', 'Telegram') 
    }
    
    # results.html template render karein
    return aiohttp_jinja2.render_template('results.html', request, context)

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    
    # ✅ Jinja2 Template Setup
    # Ye 'templates' folder ko dhundega. Make sure root folder me 'templates' folder ho.
    aiohttp_jinja2.setup(web_app, loader=jinja2.FileSystemLoader('templates'))
    
    # Routes Add karein
    web_app.add_routes([
        web.get('/', handle_home),
        web.get('/results/{key}', handle_search_results),
    ])
    
    return web_app
