import re
import logging
import asyncio
from aiohttp import web
from info import BIN_CHANNEL

logger = logging.getLogger(__name__)

async def media_streamer(request: web.Request, is_watch: bool = False):
    bot = request.app['bot'] # Pyrogram Client
    
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

        # 3. Stream File without downloading to server RAM
        try:
            async for chunk in bot.stream_media(media, offset=offset, limit=limit):
                await response.write(chunk)
        except (ConnectionResetError, asyncio.CancelledError):
            pass # User closed video player
        except Exception as e:
            logger.error(f"Streaming Error: {e}")
            
        return response

    except Exception as e:
        logger.error(f"Internal Server Error: {e}")
        return web.Response(status=500, text="Server Error")

async def stream_download(request): return await media_streamer(request, is_watch=False)
async def stream_watch(request): return await media_streamer(request, is_watch=True)
