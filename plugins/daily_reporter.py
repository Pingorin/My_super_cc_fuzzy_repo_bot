import asyncio
import datetime
import pytz
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from database.users_chats_db import db
from info import ADMINS

logger = logging.getLogger(__name__)

# ==============================================================================
# 📊 SMART REPORT FORMATTER (Common for Scheduler & Buttons)
# ==============================================================================
async def get_formatted_report(chat_id, date_str):
    """Database se data nikaal kar sundar report aur buttons banata hai."""
    # Specific date ka stats nikalna
    stat = await db.get_group_stats_by_date(chat_id, date_str) 
    group_doc = await db.groups.find_one({"id": chat_id})
    group_name = group_doc.get("title", "Unknown Group") if group_doc else "Unknown Group"

    if not stat:
        # Agar data nahi milta (jaise bohot purana din)
        msg = f"📊 **Daily Analytics Report**\n\n🏘 **Group:** {group_name}\n📅 **Date:** {date_str}\n\n⚠️ _Is tareekh ka koi data maujood nahi hai._"
    else:
        # Search Stats Calculations
        req = stat.get('req', 0)
        suc = stat.get('suc', 0)
        failed_search = req - suc if req > suc else 0
        suc_ratio = round((suc / req * 100), 2) if req > 0 else 0.0
        fail_ratio = round((failed_search / req * 100), 2) if req > 0 else 0.0

        # Shortener Stats Breakdown
        shortener_data = stat.get('shorteners', {})
        shortener_text = ""
        if shortener_data:
            shortener_text = f"\n🔗 **Shortener Statistics ({len(shortener_data)}):**\n"
            for safe_domain, data in shortener_data.items():
                real_domain = safe_domain.replace('_', '.').capitalize()
                gen = data.get('gen', 0)
                ver = data.get('ver', 0)
                failed_link = gen - ver if gen > ver else 0
                v_ratio = round((ver / gen * 100), 2) if gen > 0 else 0.0
                f_ratio = round((failed_link / gen * 100), 2) if gen > 0 else 0.0
                shortener_text += (
                    f"  🌐 **{real_domain}**\n"
                    f"    ├ Gen: `{gen}` | Ver: `{ver}` ({v_ratio}%)\n"
                    f"    └ Fail: `{failed_link}` ({f_ratio}%)\n\n"
                )

        msg = (
            f"📊 **Daily Analytics Report**\n\n"
            f"🏘 **Group:** {group_name}\n"
            f"📅 **Date:** {date_str}\n\n"
            f"🔍 **Search Statistics:**\n"
            f"  ├ Total Searches: `{req}`\n"
            f"  ├ Successful: `{suc}` ({suc_ratio}%)\n"
            f"  └ Failed: `{failed_search}` ({fail_ratio}%)\n"
            f"{shortener_text}"
        )

    # --- 🔘 BUTTON LOGIC (Prev/Next) ---
    current_dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    prev_date = (current_dt - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    next_date = (current_dt + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Aaj ki date check karne ke liye (IST)
    ist = pytz.timezone('Asia/Kolkata')
    today_str = datetime.datetime.now(ist).strftime("%Y-%m-%d")

    btn_row = []
    # Hamesha Prev button dikhayenge
    btn_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"grpstats#{chat_id}#{prev_date}"))
    
    # Next button sirf tabhi dikhega agar date aaj ki nahi hai
    if date_str != today_str:
        btn_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"grpstats#{chat_id}#{next_date}"))

    return msg, InlineKeyboardMarkup([btn_row])

# ==============================================================================
# 🕛 DAILY SCHEDULER (12:01 AM Trigger)
# ==============================================================================
async def daily_report_scheduler(client: Client):
    while True:
        try:
            tz = pytz.timezone('Asia/Kolkata')
            now = datetime.datetime.now(tz)
            target_time = now.replace(hour=0, minute=1, second=0, microsecond=0)
            if now >= target_time:
                target_time += datetime.timedelta(days=1)
            
            await asyncio.sleep((target_time - now).total_seconds())
            
            yesterday = (datetime.datetime.now(tz) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            all_stats = await db.get_all_groups_stats(yesterday)
            
            if not all_stats:
                await asyncio.sleep(60)
                continue

            for stat in all_stats:
                try:
                    chat_id = stat.get('id') or stat.get('_id')
                    settings = await db.get_group_settings(chat_id)
                    if not settings.get('daily_stats_notify', True): continue

                    group_doc = await db.groups.find_one({"id": chat_id})
                    group_admins = group_doc.get("admins", []) if group_doc else []
                    
                    # Formatting the report with interactive buttons
                    report_text, markup = await get_formatted_report(chat_id, yesterday)
                    
                    pm_sent = False
                    for admin_id in group_admins:
                        try:
                            await client.send_message(admin_id, report_text, reply_markup=markup)
                            pm_sent = True
                            await asyncio.sleep(1)
                        except: pass
                    
                    if not pm_sent:
                        try:
                            await client.send_message(chat_id, report_text + "\n\n⚠️ _Admins, please PM me /start for private reports._", reply_markup=markup)
                        except: pass

                except FloodWait as e: await asyncio.sleep(e.value + 2)
                except: continue
                    
        except Exception as e: logger.error(f"Scheduler Error: {e}")
        await asyncio.sleep(60)

# ==============================================================================
# 🔘 CALLBACK HANDLER (Navigation ke liye)
# ==============================================================================
@Client.on_callback_query(filters.regex(r"^grpstats#"))
async def grp_stats_callback(client, query):
    data = query.data.split("#")
    chat_id = int(data[1])
    target_date = data[2]

    # Loading popup
    await query.answer("Record dhoond raha hu... ⏳")
    
    # Nayi date ka data nikalna
    report_text, markup = await get_formatted_report(chat_id, target_date)
    
    try:
        # Message edit karke purana stats dikhana
        await query.message.edit_text(report_text, reply_markup=markup)
    except Exception as e:
        logger.error(f"Callback Edit Error: {e}")
