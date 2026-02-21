import logging
import logging.config
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
# ✅ New Imports for Site Mode
import aiohttp_jinja2
import jinja2
# ✅ New Import for Auto Mention
from plugins.auto_mention import auto_mention_scheduler
# ✅ New Import for Auto Post
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
        
        # Database Connect & Banned Data Load
        b_users, b_chats = await db.get_banned()
        temp.BANNED_USERS = b_users
        temp.BANNED_CHATS = b_chats
        
        await super().start()
        
        # Indexes Ensure Karna (Background mein taaki Render Time Out na ho)
        asyncio.create_task(Media.ensure_indexes())   
        
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username
        temp.B_NAME = me.first_name
        self.username = '@' + me.username
        
        print(f"{me.first_name} is started now ❤️")

        # ==================================================================
        # 📣 START BACKGROUND SCHEDULERS
        # ==================================================================
        
        # 1. Auto Mention Task
        asyncio.create_task(auto_mention_scheduler(self))
        print("Auto Mention Scheduler Started ⏳")

        # 2. Auto Post Task (Ads)
        asyncio.create_task(auto_post_scheduler(self))
        print("Auto Post Scheduler Started 📰")
        
        # ==================================================================
        # 🌐 WEB SERVER & JINJA2 SETUP (For Site Mode)
        # ==================================================================
        
        # 1. Get the Web App instance
        curr_web_app = await web_server()
        
        # 2. Configure Jinja2 Template Loader (Looks in 'templates' folder)
        aiohttp_jinja2.setup(curr_web_app, loader=jinja2.FileSystemLoader('templates'))
        
        # 3. Inject Bot Username into Web App Context (For HTML Deep Links)
        curr_web_app['bot_username'] = me.username
        
        # 4. Run the App Runner
        runner = web.AppRunner(curr_web_app)
        await runner.setup()
        bind_address = "0.0.0.0"
        await web.TCPSite(runner, bind_address, PORT).start()
        
        print(f"Web Server Running on Port {PORT} with Jinja2 Templates")
        
        # ==================================================================

        # Restart Log
        if LOG_CHANNEL:
            try:
                tz = pytz.timezone('Asia/Kolkata')
                today = datetime.date.today()
                now = datetime.datetime.now(tz)
                timee = now.strftime("%H:%M:%S %p")
                await self.send_message(chat_id=LOG_CHANNEL, text=f"<b>{me.mention} ʀᴇsᴛᴀʀᴛᴇᴅ 🤖\n\n📆 ᴅᴀᴛᴇ - <code>{today}</code>\n🕙 ᴛɪᴍᴇ - <code>{timee}</code></b>")
            except Exception as e:
                print(f"Log Channel Error: {e}")

    async def stop(self, *args):
        await super().stop()
        print("Bot stopped.")

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
