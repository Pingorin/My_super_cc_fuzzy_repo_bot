import asyncio
import datetime
import pytz
from pyrogram import Client
from database.users_chats_db import db
from info import ADMINS

async def daily_report_scheduler(client: Client):
    while True:
        # Get Current Time in India (IST)
        tz = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(tz)
        
        # Calculate time until next 12:01 AM
        target_time = now.replace(hour=0, minute=1, second=0, microsecond=0)
        if now >= target_time:
            target_time += datetime.timedelta(days=1)
            
        wait_seconds = (target_time - now).total_seconds()
        
        # Wait...
        await asyncio.sleep(wait_seconds)
        
        # --- 🕛 12:01 AM TRIGGERED ---
        
        # 1. Get Yesterday's Date (The day that just finished)
        yesterday = (datetime.datetime.now(tz) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        
        # 2. Fetch All Stats
        all_stats = await db.get_all_groups_stats(yesterday)
        
        total_req = 0
        total_suc = 0
        
        # 3. Send Individual Group Reports (If Notify is ON)
        for stat in all_stats:
            chat_id = stat['id']
            # Check if notification is enabled for this group
            settings = await db.get_group_settings(chat_id)
            if settings.get('daily_stats_notify', True):
                try:
                    # Construct simple report for the group
                    req = stat.get('req', 0)
                    suc = stat.get('suc', 0)
                    ratio = round((suc / req * 100), 2) if req > 0 else 0.0
                    
                    msg = (
                        f"📊 **Daily Report Generated**\n\n"
                        f"📅 Date: {yesterday}\n"
                        f"Total Searches: {req}\n"
                        f"Total Successful: {suc} ({ratio}%)"
                    )
                    await client.send_message(chat_id, msg)
                except: pass
            
            # Aggregate Globals
            total_req += stat.get('req', 0)
            total_suc += stat.get('suc', 0)
            
        # 4. Send Global Report to Admin
        if all_stats:
            admin_text = (
                f"📊 **Daily Report Generated**\n\n"
                f"📅 Date: {yesterday}\n"
                f"Total Searches (All Groups): {total_req}\n"
                f"Total Successful: {total_suc}"
            )
            
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            btn = [[InlineKeyboardButton("See Full Report", callback_data=f"admin_report#{yesterday}#0")]]
            
            for admin_id in ADMINS:
                try:
                    await client.send_message(admin_id, admin_text, reply_markup=InlineKeyboardMarkup(btn))
                except: pass
        
        # Wait a bit to avoid double trigger
        await asyncio.sleep(60)

# Add this to Bot.py start()
# from plugins.daily_reporter import daily_report_scheduler
# asyncio.create_task(daily_report_scheduler(self))
