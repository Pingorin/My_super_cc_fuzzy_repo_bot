import re
import logging
import asyncio
from aiohttp import web
from info import BIN_CHANNEL

logger = logging.getLogger(__name__)

# ✅ Main function jo raw file ko Telegram se stream karta hai
async def get_media_response(request: web.Request, is_download: bool):
    bot = request.app['bot']
    try:
        message_id = int(request.match_info.get('message_id'))
        
        msg = await bot.get_messages(BIN_CHANNEL, message_id)
        if not msg or msg.empty:
            return web.Response(status=404, text="File Not Found")
            
        media = msg.document or msg.video or msg.audio
        if not media:
            return web.Response(status=404, text="No valid media found.")
            
        file_size = media.file_size
        file_name = getattr(media, 'file_name', 'video.mp4')
        mime_type = getattr(media, 'mime_type', 'video/mp4')

        offset = 0
        limit = file_size
        range_header = request.headers.get('Range')
        
        if range_header:
            match = re.match(r'bytes=(\d+)-(\d*)', range_header)
            if match:
                offset = int(match.group(1))
                if match.group(2):
                    end = int(match.group(2))
                    limit = end - offset + 1
                else:
                    limit = file_size - offset

        status_code = 206 if range_header else 200
        
        # is_download True hoga toh download hoga, warna browser me play hoga
        disposition = "attachment" if is_download else "inline"
        
        response = web.StreamResponse(
            status=status_code,
            headers={
                'Content-Type': mime_type,
                'Accept-Ranges': 'bytes',
                'Content-Range': f'bytes {offset}-{offset + limit - 1}/{file_size}',
                'Content-Length': str(limit),
                'Content-Disposition': f'{disposition}; filename="{file_name}"'
            }
        )
        
        await response.prepare(request)

        try:
            async for chunk in bot.stream_media(media, offset=offset, limit=limit):
                await response.write(chunk)
        except (ConnectionResetError, asyncio.CancelledError):
            pass 
            
        return response

    except Exception as e:
        logger.error(f"Internal Server Error: {e}")
        return web.Response(status=500, text="Server Error")


# ==========================================
# ⚡ FAST DOWNLOAD ROUTE (Redirect to Chrome)
# ==========================================
async def stream_download(request):
    # Agar action=download param hai, matlab Chrome khul chuka hai, ab actual file de do
    if request.query.get('action') == 'download':
        return await get_media_response(request, is_download=True)
        
    # Warna Telegram browser me intent page dikhao
    msg_id = request.match_info.get('message_id')
    base_url = f"{request.scheme}://{request.host}"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Fast Download</title></head>
    <body style="background:#0f0f0f; color:#fff; text-align:center; padding-top:100px; font-family:sans-serif;">
        <h2>⚡ Redirecting to Chrome for Download...</h2>
        <p>If not redirected automatically, <a href="{base_url}/{msg_id}?action=download" style="color:#0088cc;">Click Here</a></p>
        <script>
            var isAndroid = /android/i.test(navigator.userAgent);
            var scheme = window.location.protocol.replace(':', '');
            var hostAndPath = window.location.host + "/{msg_id}?action=download";
            if (isAndroid) {{
                window.location.href = "intent://" + hostAndPath + "#Intent;scheme=" + scheme + ";package=com.android.chrome;end";
            }} else {{
                window.location.href = "{base_url}/{msg_id}?action=download";
            }}
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")


# ==========================================
# 🍿 WATCH ONLINE ROUTE (HTML Player in Chrome)
# ==========================================
async def stream_watch(request):
    # Agar action=stream hai, toh Video tag ko raw file inline serve karo
    if request.query.get('action') == 'stream':
        return await get_media_response(request, is_download=False)
        
    # Agar opened=1 hai, iska matlab Chrome khul gaya hai. Ab HTML Player dikhao!
    if request.query.get('opened') == '1':
        msg_id = request.match_info.get('message_id')
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Watch Online</title>
            <style>
                body {{ background: #000; margin: 0; padding: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }}
                video {{ width: 100%; max-width: 900px; max-height: 80vh; outline: none; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }}
            </style>
        </head>
        <body>
            <video controls autoplay controlsList="nodownload">
                <source src="/watch/{msg_id}?action=stream" type="video/mp4">
            </video>
        </body>
        </html>
        """
        return web.Response(text=html, content_type="text/html")

    # Telegram browser open hote hi pehle ye Intent Page aayega, jo Chrome ko khol dega
    msg_id = request.match_info.get('message_id')
    base_url = f"{request.scheme}://{request.host}"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><title>Opening Video Player...</title></head>
    <body style="background:#0f0f0f; color:#fff; text-align:center; padding-top:100px; font-family:sans-serif;">
        <h2>🍿 Opening Web Player in Chrome...</h2>
        <p>If not redirected automatically, <a href="{base_url}/watch/{msg_id}?opened=1" style="color:#0088cc;">Click Here</a></p>
        <script>
            var isAndroid = /android/i.test(navigator.userAgent);
            var scheme = window.location.protocol.replace(':', '');
            var hostAndPath = window.location.host + "/watch/{msg_id}?opened=1";
            if (isAndroid) {{
                window.location.href = "intent://" + hostAndPath + "#Intent;scheme=" + scheme + ";package=com.android.chrome;end";
            }} else {{
                window.location.href = "{base_url}/watch/{msg_id}?opened=1";
            }}
        </script>
    </body>
    </html>
    """
    return web.Response(text=html, content_type="text/html")
