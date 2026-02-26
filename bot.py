import logging
import logging.config
import os
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import API_ID, API_HASH, ADMINS, BOT_TOKEN, LOG_CHANNEL, PORT
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
from plugins.auto_mention import auto_mention_scheduler
from plugins.auto_post import auto_post_scheduler

# Logging Setup
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

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
        # 1. CONNECT DATABASE & TELEGRAM BOT FIRST
        # ==================================================================
        print("⏳ Connecting to Database & Telegram...", flush=True)
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats
        
        await super().start()
        
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        self.username = '@' + me.username
        
        print(f"🤖 {me.first_name} is started now ❤️", flush=True)

        # Ensure Indexes in Background
        asyncio.create_task(Media.ensure_indexes())   

        # ==================================================================
        # 🚀 2. START WEB SERVER (Fixing Deprecation Warning)
        # ==================================================================
        try:
            curr_web_app = await web_server()
            
            # Configure Jinja2 Template Loader
            aiohttp_jinja2.setup(curr_web_app, loader=jinja2.FileSystemLoader('templates'))
            
            # ✅ Set all variables BEFORE starting the Web Server
            curr_web_app['bot'] = self 
            curr_web_app['bot_username'] = me.username
            
            runner = web.AppRunner(curr_web_app)
            await runner.setup()
            bind_address = "0.0.0.0"
            await web.TCPSite(runner, bind_address, PORT).start()
            print(f"✅ Web Server Running smoothly on Port {PORT}", flush=True)
        except Exception as e:
            print(f"⚠️ Web Server Error: {e}", flush=True)

        # ==================================================================
        # 3. START BACKGROUND SCHEDULERS
        # ==================================================================
        asyncio.create_task(auto_mention_scheduler(self))
        print("⏳ Auto Mention Scheduler Started", flush=True)

        asyncio.create_task(auto_post_scheduler(self))
        print("📰 Auto Post Scheduler Started", flush=True)
        
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
