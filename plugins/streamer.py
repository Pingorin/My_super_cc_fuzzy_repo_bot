import re
import logging
import asyncio
from aiohttp import web
from info import BIN_CHANNEL

logger = logging.getLogger(__name__)

async def media_streamer(request: web.Request, is_watch: bool = False):
    bot = request.app['bot'] 
    
    try:
        message_id = int(request.match_info.get('message_id'))
        
        # 1. Fetch file from Bin Channel
        msg = await bot.get_messages(BIN_CHANNEL, message_id)
        if not msg or msg.empty:
            return web.Response(status=404, text="File Not Found")
            
        media = msg.document or msg.video or msg.audio
        if not media:
            return web.Response(status=404, text="No valid media found.")
            
        file_size = media.file_size
        file_name = getattr(media, 'file_name', 'video.mp4')
        mime_type = getattr(media, 'mime_type', 'video/mp4')

        # 2. HTTP Range Request (MX Player/VLC seek karne ke liye)
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
        
        # Streaming ke liye hamesha inline rakhein taaki browser me play ho
        disposition = "inline" if is_watch else "attachment"
        
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

        # 3. Stream File
        try:
            async for chunk in bot.stream_media(media, offset=offset, limit=limit):
                await response.write(chunk)
        except (ConnectionResetError, asyncio.CancelledError):
            pass 
        except Exception as e:
            logger.error(f"Streaming Error: {e}")
            
        return response

    except Exception as e:
        logger.error(f"Internal Server Error: {e}")
        return web.Response(status=500, text="Server Error")

async def stream_download(request): 
    return await media_streamer(request, is_watch=False)

# ✅ NAYA: Redirect Landing Page (Shorteners jaisa)
async def stream_watch(request):
    msg_id = request.match_info.get('message_id')
    base_url = f"{request.scheme}://{request.host}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Redirecting to Chrome...</title>
        <style>
            body {{ background-color: #0f0f0f; color: #fff; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; font-family: sans-serif; text-align: center; margin: 0; }}
            .box {{ background: #1e1e1e; padding: 40px 30px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.8); border: 1px solid #333; }}
            .btn {{ background-color: #0088cc; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 18px; margin-top: 20px; display: inline-block; transition: 0.3s; }}
            .btn:hover {{ background-color: #005f8f; transform: scale(1.05); }}
            p {{ color: #bbb; font-size: 14px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="box">
            <h2>🎥 Loading Your Video...</h2>
            <p>If you are not redirected automatically, click the button below to open in Google Chrome or VLC.</p>
            <a href="{base_url}/{msg_id}" class="btn" target="_blank">🍿 Watch / Download Now</a>
        </div>

        <script>
            // ✅ Yahi wo jadoo hai jo shorteners use karte hain (Android Chrome Intent)
            var isAndroid = /android/i.test(navigator.userAgent);
            var scheme = window.location.protocol.replace(':', '');
            var hostAndPath = window.location.host + "/{msg_id}";
            
            if (isAndroid) {{
                // Ye script Telegram ko bypass karke direct Chrome khol degi
                window.location.href = "intent://" + hostAndPath + "#Intent;scheme=" + scheme + ";package=com.android.chrome;end";
            }}
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html")
