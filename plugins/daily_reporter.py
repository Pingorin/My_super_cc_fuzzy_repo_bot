import asyncio
import datetime
import pytz
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
        
        # Wait until 12:01 AM
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
            settings = await db.get_group_settings(chat_id)
            
            # Check if notification is enabled for this group
            if settings.get('daily_stats_notify', True):
                try:
                    # --- A. Search Stats ---
                    req = stat.get('req', 0)
                    suc = stat.get('suc', 0)
                    ratio = round((suc / req * 100), 2) if req > 0 else 0.0
                    
                    # --- B. Shortener Stats Breakdown ---
                    shortener_data = stat.get('shorteners', {})
                    shortener_text = ""
                    
                    if shortener_data:
                        shortener_text = "\n🔗 **Shortener Statistics:**\n"
                        for safe_domain, data in shortener_data.items():
                            # Restore domain name (underscore to dot)
                            real_domain = safe_domain.replace('_', '.').capitalize()
                            
                            gen = data.get('gen', 0)
                            ver = data.get('ver', 0)
                            s_ratio = round((ver / gen * 100), 2) if gen > 0 else 0.0
                            
                            shortener_text += (
                                f"  - {real_domain}\n"
                                f"    - Gen: {gen} | Ver: {ver} | Ratio: {s_ratio}%\n"
                            )
                    
                    # --- C. Construct Message ---
                    msg = (
                        f"📊 **Daily Report Generated**\n\n"
                        f"📅 Date: {yesterday}\n"
                        f"Total Searches: {req}\n"
                        f"Total Successful: {suc} ({ratio}%)\n"
                        f"{shortener_text}"
                    )
                    await client.send_message(chat_id, msg)
                except Exception as e:
                    pass # Ignore if bot was kicked or perm error
            
            # Aggregate Globals for Admin Report
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
            
            # Button to view detailed pagination
            btn = [[InlineKeyboardButton("See Full Report", callback_data=f"admin_report#{yesterday}#0")]]
            
            for admin_id in ADMINS:
                try:
                    await client.send_message(admin_id, admin_text, reply_markup=InlineKeyboardMarkup(btn))
                except: pass
        
        # Wait a bit to avoid double trigger
        await asyncio.sleep(60)
