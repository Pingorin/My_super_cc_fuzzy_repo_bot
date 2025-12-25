import pyromod.listen
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

# Logging Setup
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)

class Bot(Client):
    def __init__(self):
        super().__init__(
            name='my_bot',
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            sleep_threshold=5,
            workers=50,
            plugins={"root": "plugins"}
        )

    async def start(self):
        st = time.time()
        
        # 1. Banned Users Load
        await db.get_banned() 
        
        # 2. Start Client
        await super().start()
        
        me = await self.get_me()
        temp.ME = me.id
        temp.U_NAME = me.username 
        temp.B_NAME = me.first_name
        self.username = '@' + me.username
        
        print(f"{me.first_name} is started now ❤️")
        
        # 3. ✅ DATABASE CACHE WARMUP (Auto-Sync Fix)
        # This ensures DB connection is active immediately after restart
        try:
            # Just calling this initializes the cursor and connection
            await db.get_all_chats()
            print("✅ Database Connected & Groups Cached Successfully")
        except Exception as e:
            print(f"❌ DB Cache Error (Non-Critical): {e}")

        # 4. Web Server Start (For Uptime/Heroku)
        app = web.AppRunner(await web_server())
        await app.setup()
        bind_address = "0.0.0.0"
        await web.TCPSite(app, bind_address, PORT).start()
        
        # 5. Log Channel Notification
        if LOG_CHANNEL:
            try:
                await self.send_message(chat_id=LOG_CHANNEL, text=f"<b>{me.mention} ʀᴇsᴛᴀʀᴛᴇᴅ 🤖</b>")
            except:
                print("Log Channel ID galat hai ya bot admin nahi hai wahan.")

    async def stop(self, *args):
        await super().stop()
        print("Bot stopped.")

if __name__ == "__main__":
    app = Bot()
    app.run()
