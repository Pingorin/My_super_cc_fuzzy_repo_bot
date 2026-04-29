import logging
import logging.config
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import API_ID, API_HASH, ADMINS, BOT_TOKEN, LOG_CHANNEL, PORT, SITE_URL
from utils import temp
from typing import Union, Optional, AsyncGenerator
from pyrogram import types
import datetime
import pytz
from aiohttp import web
from plugins.web_server import web_server
import asyncio
import time
import aiohttp_jinja2
import jinja2
import warnings

# ✅ Aapke purane background tasks
from plugins.auto_mention import auto_mention_scheduler
from plugins.auto_post import auto_post_scheduler

# ✅ Naya TMDB Channel Auto Poster
from plugins.auto_poster import start_auto_poster

# Logging Setup
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

# ==============================================================================
# 🔥 TELEGRAM LOG CATCHER ENGINE 🔥
# ==============================================================================
class TelegramLogHandler(logging.Handler):
    def __init__(self, client):
        super().__init__()
        self.client = client

    def emit(self, record):
        # Sirf ERROR aur CRITICAL logs ko Telegram par bhejenge
        # Taaki normal INFO logs se aapka channel spam na ho
        if record.levelno >= logging.ERROR:
            log_entry = self.format(record)
            if LOG_CHANNEL and LOG_CHANNEL != 0:
                try:
                    # Async task ko synchronous logging ke andar chalane ka tarika
                    loop = asyncio.get_event_loop()
                    loop.create_task(self.send_async_log(log_entry))
                except Exception:
                    pass

    async def send_async_log(self, text):
        try:
            # Telegram ek baar me max 4096 characters allow karta hai
            safe_text = text[-4000:] 
            await self.client.send_message(
                chat_id=LOG_CHANNEL, 
                text=f"🚨 **SERVER ERROR ALERT** 🚨\n\n```python\n{safe_text}\n```"
            )
        except Exception:
            pass

class Bot(Client):
    def __init__(self):
        super().__init__(
            name='aks', 
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            sleep_threshold=5,
            workers=50,
            plugins={"root": "plugins"}
        )

    async def start(self):
        st = time.time()
        temp.START_TIME = st 
        
        # ==================================================================
        # 🚀 1. START WEB SERVER FIRST (Render Timeout Fix)
        # ==================================================================
        print("🌐 Starting Web Server...", flush=True)
        try:
            curr_web_app = await web_server()
            aiohttp_jinja2.setup(curr_web_app, loader=jinja2.FileSystemLoader('templates'))
            
            # Inject bot early for Streaming
            curr_web_app['bot'] = self 
            
            runner = web.AppRunner(curr_web_app)
            await runner.setup()
            bind_address = "0.0.0.0"
            await web.TCPSite(runner, bind_address, PORT).start()
            print(f"✅ Web Server is LIVE on Port {PORT}", flush=True)
        except Exception as e:
            print(f"⚠️ Web Server Error: {e}", flush=True)

        # ✅ FIX 5: Check SITE_URL for Streaming Safety
        if not SITE_URL or "127.0.0.1" in SITE_URL:
            print("⚠️ WARNING: SITE_URL set nahi hai! Streaming links localhost par banengi jo cloud par kaam nahi karengi. Kripya info.py ya Env Vars me SITE_URL dalein.", flush=True)

        # ==================================================================
        # 2. CONNECT TO DATABASE & TELEGRAM
        # ==================================================================
        print("⏳ Connecting to Database...", flush=True)
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats
        
        print("⏳ Connecting to Telegram...", flush=True)
        await super().start()
        
        # 🔥 ACTIVATE TELEGRAM LOG CATCHER 🔥
        tg_handler = TelegramLogHandler(self)
        tg_handler.setFormatter(logging.Formatter('%(name)s - %(message)s'))
        logging.getLogger().addHandler(tg_handler)
        
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        self.username = '@' + me.username
        
        # ✅ FIX: Warning hide kar di gayi hai
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            curr_web_app['bot_username'] = me.username
        
        print(f"🤖 {me.first_name} is started now ❤️", flush=True)

        # ==================================================================
        # 3. START BACKGROUND TASKS
        # ==================================================================
        asyncio.create_task(Media.ensure_indexes())   
        
        # Aapka purana Group Mention Scheduler
        asyncio.create_task(auto_mention_scheduler(self))
        print("⏳ Auto Mention Scheduler Started", flush=True)

        # Aapka purana Group Post Scheduler
        asyncio.create_task(auto_post_scheduler(self))
        print("📰 Group Auto Post Scheduler Started", flush=True)
        
        # 🔥 TMDB Channel Poster Scheduler
        asyncio.create_task(start_auto_poster(self))
        print("🎬 TMDB Channel Auto Poster Started", flush=True)
        
        # ✅ FIX 2: START HEARTBEAT ENGINE HERE
        from plugins.commands import bot_b_heartbeat
        asyncio.create_task(bot_b_heartbeat(self))
        print("💓 Auto-Fallback Heartbeat Engine Started", flush=True)
        
        # Restart Log
        if LOG_CHANNEL:
            try:
                tz = pytz.timezone('Asia/Kolkata')
                today = datetime.date.today()
                now = datetime.datetime.now(tz)
                timee = now.strftime("%H:%M:%S %p")
                await self.send_message(chat_id=LOG_CHANNEL, text=f"<b>{me.mention} ʀᴇsᴛᴀʀᴛᴇᴅ 🤖\n\n📆 ᴅᴀᴛᴇ - <code>{today}</code>\n🕙 ᴛɪᴍᴇ - <code>{timee}</code></b>")
            except Exception as e:
                print(f"Log Channel Error: {e}", flush=True)

    async def stop(self, *args):
        await super().stop()
        print("Bot stopped.", flush=True)

    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        current = offset
        while True:
            new_diff = min(200, limit - current)
            if new_diff <= 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current+new_diff+1)))
            for message in messages:
                yield message
                current += 1

if __name__ == "__main__":
    app = Bot()
    app.run()
