import logging
import time
import re
import datetime
import asyncio 
import urllib.parse
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.errors import UserNotParticipant, UsernameInvalid, UsernameNotOccupied, PeerIdInvalid, FloodWait
from database.users_chats_db import db
from database.ia_filterdb import Media
import info 
from info import ADMINS, IS_VERIFY
from utils import temp, get_shortlink, check_fsub_4_status
from Script import script 

logger = logging.getLogger(__name__)
START_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg"

# Safely load Payment Variables from info.py (Fallback to default if missing)
MERCHANT_UPI_ID = getattr(info, 'MERCHANT_UPI_ID', "aapka_id@upi")
PAYMENT_SUPPORT_LINK = getattr(info, 'PAYMENT_SUPPORT_LINK', "https://t.me/AapkaSupportGroup")
CONTACT_OWNER_LINK = getattr(info, 'CONTACT_OWNER_LINK', "https://t.me/AapkaPersonalUsername")
CUSTOM_QR_URL = getattr(info, 'CUSTOM_QR_URL', "")

# ==============================================================================
# 💓 HEARTBEAT ENGINE (AUTO-FALLBACK SYSTEM)
# ==============================================================================

async def bot_b_heartbeat(client):
    """Har 10 minute me Bot B ko check karega. Ban hua toh Bot A par fallback karega."""
    while True:
        await asyncio.sleep(600)  # 10 minutes wait karega
        if info.FILE_STORE_BOT and info.FILE_STORE_BOT != temp.U_NAME:
            try:
                # Bot B ka status check karna
                await client.get_users(info.FILE_STORE_BOT)
            except (UsernameInvalid, UsernameNotOccupied, PeerIdInvalid, Exception):
                # Agar Bot B ban ho gaya ya username exist nahi karta
                old_bot = info.FILE_STORE_BOT
                info.FILE_STORE_BOT = temp.U_NAME  # 🔥 AUTO-FALLBACK TO BOT A
                
                alert_msg = (
                    f"🚨 **EMERGENCY ALERT** 🚨\n\n"
                    f"Aapka File Store Bot (`@{old_bot}`) ban ho gaya hai ya delete ho gaya hai!\n\n"
                    f"✅ **Auto-Fallback Activated:** Bot A (`@{temp.U_NAME}`) ne system apne haath me le liya hai. Ab saari files direct yahi bot dega. Links break nahi honge!"
                )
                # Admins ko alert bhejna
                for admin in ADMINS:
                    try:
                        await client.send_message(admin, alert_msg)
                    except:
                        pass
                break # Fallback ho gaya, ab loop band kar do

# ==============================================================================
# 🗑️ AUTO-DELETE HELPER FUNCTIONS
# ==============================================================================

# ✅ SCENARIO 1: Single File Auto-Delete
async def auto_delete_single(file_msg, warning_msg, command_data):
    await asyncio.sleep(60) # 1 Minute wait
    try:
        await file_msg.delete() # File delete
    except Exception:
        pass
    try:
        btn = [[InlineKeyboardButton("✅ ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ ✅", url=f"https://t.me/{temp.U_NAME}?start={command_data}")]]
        await warning_msg.edit_text(
            "<b>✅ ʏᴏᴜʀ ᴍᴇssᴀɢᴇ ɪs sᴜᴄssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ɪғ ʏᴏᴜ ᴡᴀɴᴛ ᴀɢᴀɪɴ ᴛʜᴇɴ ᴄʟɪᴄᴋ ᴏɴ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ</b>",
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except Exception:
        pass

# ✅ SCENARIO 2: Batch (Send All) Auto-Delete
async def auto_delete_batch(file_msgs_list, warning_msg):
    await asyncio.sleep(60) # 1 Minute wait
    for msg in file_msgs_list:
        try:
            await msg.delete() # Loop me saari files delete
        except Exception:
            pass
    try:
        await warning_msg.edit_text("<b>✅ ʏᴏᴜʀ ᴍᴇssᴀɢᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ</b>")
    except Exception:
        pass

# ==============================================================================
# --- 🛠️ HELPER FUNCTIONS ---
# ==============================================================================

async def send_shortener_alert(client, chat_id, site_domain):
    try:
        try:
            chat_id_int = int(str(chat_id))
            chat = await client.get_chat(chat_id_int)
            group_name = chat.title
            group_id = chat.id
        except:
            group_name = "Unknown Group"
            group_id = chat_id
            chat_id_int = int(chat_id)

        msg = (
            f"⚠️ **Shortener Alert** ⚠️\n\n"
            f"Group: **{group_name}** (`{group_id}`).\n"
            f"Shortener: **{site_domain}** failed or is down.\n"
            f"**Action:** Please Check your API Key or Website Status."
        )
        
        # 🔥 SMART ALERT ENGINE: Sirf Group ke Owner aur Admins ko msg jayega!
        try:
            async for member in client.get_chat_members(chat_id_int, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                if not member.user.is_bot:
                    try: 
                        await client.send_message(chat_id=member.user.id, text=msg)
                    except: 
                        pass
        except Exception as e:
            logger.error(f"Admin fetch error for shortener alert: {e}")
            
    except Exception as e: 
        pass

async def get_active_shorteners(chat_id):
    group_settings = await db.get_group_settings(chat_id)
    if group_settings:
        group_shorteners = group_settings.get('shorteners', {})
        active = {}
        if group_shorteners.get('1'): active['1'] = group_shorteners['1']
        if group_shorteners.get('2'): active['2'] = group_shorteners['2']
        if group_shorteners.get('3'): active['3'] = group_shorteners['3']
        if active: return active

    default_shorteners = {}
    if info.SHORTLINK_URL_1 and info.SHORTLINK_API_1: default_shorteners['1'] = {'site': info.SHORTLINK_URL_1, 'api': info.SHORTLINK_API_1}
    if info.SHORTLINK_URL_2 and info.SHORTLINK_API_2: default_shorteners['2'] = {'site': info.SHORTLINK_URL_2, 'api': info.SHORTLINK_API_2}
    if info.SHORTLINK_URL_3 and info.SHORTLINK_API_3: default_shorteners['3'] = {'site': info.SHORTLINK_URL_3, 'api': info.SHORTLINK_API_3}
    return default_shorteners

@Client.on_message(filters.group, group=-1)
async def auto_save_group_handler(client, message):
    try: 
        if message.chat and message.chat.title:
            await db.add_group(message.chat.id, message.chat.title)
    except: pass

# ==============================================================================
# --- 🔐 VERIFICATION LOGIC ---
# ==============================================================================

async def grant_full_access(user_id, chat_id):
    group_settings = await db.get_group_settings(chat_id)
    mode = group_settings.get('shortener_mode', 'dynamic') if group_settings else 'dynamic'
    
    if mode == 'smart': duration = group_settings.get('time_smart', 86400)
    elif mode == 'together': 
        active_slots = await get_active_shorteners(chat_id)
        if len(active_slots) >= 3: duration = group_settings.get('time_together_3', 86400)
        else: duration = group_settings.get('time_together', 604800)
    else: duration = group_settings.get('time_dynamic', 86400) 

    await db.update_verify_status(user_id, chat_id, 0, duration)
    await db.update_verify_status(user_id, chat_id, 1, is_reset=True)
    await db.update_verify_status(user_id, chat_id, 2, is_reset=True)
    await db.update_verify_status(user_id, chat_id, 3, is_reset=True)

async def check_verification(client, user_id, chat_id, link_id, message_obj):
    if not IS_VERIFY: return True 

    # 💎 Premium Check - Agar user VIP hai toh turant True return kar do (Shortener Skip)
    is_premium = await db.is_user_premium(user_id)
    if is_premium:
        return True 

    group_settings = await db.get_group_settings(chat_id)
    
    # 🔥 FIX: Agar Settings me Shortlink Disable hai, toh yahi se aage jane do (Bypass)
    if group_settings and group_settings.get('is_shortlink_active', True) == False:
        return True

    try:
        if group_settings and group_settings.get('admin_free_access', False):
            member = await client.get_chat_member(chat_id, user_id)
            if member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                return True
    except:
        pass

    if await db.get_verify_status(user_id, chat_id): return True 

    if not group_settings:
        group_settings = await db.get_group_settings(chat_id)

    mode = group_settings.get('shortener_mode', 'dynamic') if group_settings else 'dynamic'
    active_slots = await get_active_shorteners(chat_id)
    current_time = time.time()
    
    howto_url = group_settings.get('howto_url')

    if mode == 'together':
        buttons = []
        info_text = "⚠️ **Verification Required**\n\nComplete the steps below to access files:\n"
        wait_msg = await message_obj.reply_text("Generating Verification Links... ⏳")
        
        if active_slots.get('1') and await db.get_level_time(user_id, chat_id, 1) == 0:
            link = await generate_single_link(client, chat_id, user_id, link_id, 1, active_slots['1'])
            if link: 
                buttons.append([InlineKeyboardButton(f"🔗 Verify Link 1 ({active_slots['1']['site']})", url=link)])
                info_text += f"\n1️⃣ **Step 1:** Remaining ❌"
            else:
                await db.update_verify_status(user_id, chat_id, 1, is_reset=False) 

        if active_slots.get('2') and await db.get_level_time(user_id, chat_id, 2) == 0:
            link = await generate_single_link(client, chat_id, user_id, link_id, 2, active_slots['2'])
            if link:
                buttons.append([InlineKeyboardButton(f"🔗 Verify Link 2 ({active_slots['2']['site']})", url=link)])
                info_text += f"\n2️⃣ **Step 2:** Remaining ❌"
            else:
                await db.update_verify_status(user_id, chat_id, 2, is_reset=False)

        if active_slots.get('3') and await db.get_level_time(user_id, chat_id, 3) == 0:
            link = await generate_single_link(client, chat_id, user_id, link_id, 3, active_slots['3'])
            if link:
                buttons.append([InlineKeyboardButton(f"🔗 Verify Link 3 ({active_slots['3']['site']})", url=link)])
                info_text += f"\n3️⃣ **Step 3:** Remaining ❌"
            else:
                await db.update_verify_status(user_id, chat_id, 3, is_reset=False)

        await wait_msg.delete()

        if buttons:
            if howto_url:
                buttons.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
                
            await message_obj.reply_text(info_text, reply_markup=InlineKeyboardMarkup(buttons))
            return False
        else:
            await grant_full_access(user_id, chat_id)
            return True

    elif mode == 'smart':
        gap1 = group_settings.get('time_gap1', 300)
        gap2 = group_settings.get('time_gap2', 300)

        if active_slots.get('1'):
            v1_time = await db.get_level_time(user_id, chat_id, 1)
            if v1_time == 0:
                res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 1, active_slots['1'])
                if res == "SENT": return False
            elif active_slots.get('2') and (v1_time + gap1) > current_time: return True 

        if active_slots.get('2'):
            v2_time = await db.get_level_time(user_id, chat_id, 2)
            if v2_time == 0:
                res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 2, active_slots['2'])
                if res == "SENT": return False
            elif active_slots.get('3') and (v2_time + gap2) > current_time: return True 

        if active_slots.get('3'):
            v3_time = await db.get_level_time(user_id, chat_id, 3)
            if v3_time == 0:
                res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 3, active_slots['3'])
                if res == "SENT": return False

    else: 
        if active_slots.get('1') and await db.get_level_time(user_id, chat_id, 1) == 0:
            res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 1, active_slots['1'])
            if res == "SENT": return False 

        if active_slots.get('2') and await db.get_level_time(user_id, chat_id, 2) == 0:
            res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 2, active_slots['2'])
            if res == "SENT": return False 

        if active_slots.get('3') and await db.get_level_time(user_id, chat_id, 3) == 0:
            res = await attempt_send_link(client, user_id, chat_id, link_id, message_obj, 3, active_slots['3'])
            if res == "SENT": return False 

    await grant_full_access(user_id, chat_id)
    return True

async def generate_single_link(client, chat_id, user_id, link_id, level, slot_data):
    site = slot_data['site']
    api = slot_data['api']
    verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{level}_{user_id}_{chat_id}_{link_id}"
    short_url = await get_shortlink(site, api, verify_url)
    if not short_url:
        await send_shortener_alert(client, chat_id, site)
        return None
    
    try: await db.update_daily_stats(chat_id, 'gen', count=1, domain=site)
    except: pass
    
    return short_url

async def attempt_send_link(client, user_id, chat_id, link_id, message_obj, level, slot_data):
    site = slot_data['site']
    api = slot_data['api']
    verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{level}_{user_id}_{chat_id}_{link_id}"
    wait_msg = await message_obj.reply_text(f"Generating Verification Link {level}... ⏳")
    short_url = await get_shortlink(site, api, verify_url)
    await wait_msg.delete()
    
    if short_url:
        try: await db.update_daily_stats(chat_id, 'gen', count=1, domain=site)
        except: pass

        btn = [[InlineKeyboardButton(f"🚀 Verify Level {level}", url=short_url)]]
        
        try:
            grp = await db.get_group_settings(chat_id)
            howto_url = grp.get('howto_url')
            if howto_url:
                btn.append([InlineKeyboardButton("⁉️ How To Download", url=howto_url)])
        except: pass

        text = f"⚠️ **Verification Required ({level}/?)**\n\n**Shortener:** {site}\n_Click the button below to verify and continue._"
        if level == 3: text = f"⚠️ **Final Step (3/3)**\n\n**Shortener:** {site}\n_Almost there! Verify this to unlock files._"
        await message_obj.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))
        return "SENT"
    else:
        await send_shortener_alert(client, chat_id, site)
        await message_obj.reply_text(f"⚠️ **Alert:** Shortener {site} is down. Skipping Level {level}... ⏩")
        return "SKIP"

# ==============================================================================
# --- 🔥 PRE-VERIFY FSUB CHECK (Slots 1, 2, 3) ---
# ==============================================================================

async def check_fsub(client, user_id, message_obj):
    src_chat_id = None
    if len(message_obj.command) > 1:
        try:
            parts = message_obj.command[1].split("_")
            if len(parts) > 3: src_chat_id = int(parts[3]) 
            elif len(parts) > 2 and parts[0] == "get": src_chat_id = int(parts[2])
            elif len(parts) > 2 and parts[0] == "sendall": src_chat_id = int(parts[2]) 
        except: pass
    
    if not src_chat_id: return True 

    group_settings = await db.get_group_settings(src_chat_id)
    if not group_settings: return True
    
    fsub_channels = group_settings.get('fsub_channels')
    if not isinstance(fsub_channels, dict): return True 

    btn_row_1 = [] 
    btn_row_2 = [] 

    for slot in ['1', '2', '3']:
        channel_id = fsub_channels.get(slot)
        if not channel_id: continue 
        try: channel_id = int(channel_id)
        except: continue
        
        try:
            chat_obj = await client.get_chat(channel_id)
            channel_id = chat_obj.id
        except: pass

        is_member = False
        try:
            member = await client.get_chat_member(channel_id, user_id)
            if member.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]:
                is_member = True
        except UserNotParticipant: pass 
        except: continue 

        if is_member: continue

        if slot == '3':
            try:
                invite = await client.create_chat_invite_link(channel_id)
                btn_row_2.append(InlineKeyboardButton(f"📢 Join Channel {slot}", url=invite.invite_link))
            except: pass
        else:
            if await db.is_user_pending(user_id, channel_id): continue 
            try:
                invite = await client.create_chat_invite_link(channel_id, creates_join_request=True)
                btn_row_1.append(InlineKeyboardButton(f"📢 Request {slot}", url=invite.invite_link))
            except: pass

    final_markup = []
    if btn_row_1: final_markup.append(btn_row_1)
    if btn_row_2: final_markup.append(btn_row_2)

    if final_markup:
        original_param = message_obj.command[1] if len(message_obj.command) > 1 else "start"
        final_markup.append([InlineKeyboardButton("🔄 Try Again", url=f"https://t.me/{temp.U_NAME}?start={original_param}")])
        
        await message_obj.reply_text(
            f"⚠️ **Access Denied!**\n\n"
            f"Please complete the steps below to get the file.\n"
            f"Join/Request the channels and click **Try Again**.",
            reply_markup=InlineKeyboardMarkup(final_markup)
        )
        return False 

    return True

# ==============================================================================
# --- 🎮 COMMAND HANDLERS ---
# ==============================================================================

@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        asyncio.create_task(db.add_group(message.chat.id, message.chat.title))
        if len(message.command) == 1: return await message.reply("✅ Bot is Alive!")
        return 

    if message.chat.type == enums.ChatType.PRIVATE:
        user_id = message.from_user.id
        
        # 🚀 SUPER FAST START (No DB delay for base command)
        if len(message.command) == 1:
            text = f"Hello {message.from_user.mention} 👋,\nI am a Powerul Auto Filter Bot."
            buttons = [
                [InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜps ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')],
                [InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'), 
                 InlineKeyboardButton('💎 Free Premium', callback_data='open_prem_menu')],
                [InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛʜ ʙᴏᴛ 🚫', callback_data='earn'), InlineKeyboardButton('🤝 ʀᴇꜰᴇʀʀᴀʟ 🤝', callback_data='refer')]
            ]
            await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
            asyncio.create_task(db.add_user(user_id))
            return
            
        if len(message.command) > 1 and message.command[1] == "settings":
            from plugins.settings_ui import settings_command
            return await settings_command(client, message)

        old_user = await db.get_user_data(user_id)
        await db.add_user(user_id)

        if len(message.command) > 1 and message.command[1].startswith("ref_"):
            try:
                referrer_id = int(message.command[1].split("_")[1])
                if referrer_id != user_id:
                    if not old_user:
                        await db.update_referral_stats(referrer_id, points=10)
                        try:
                            await client.send_message(
                                referrer_id, 
                                f"🎉 **New Referral!**\n{message.from_user.mention} joined via your link.\n**+10 Points Added!**"
                            )
                        except: pass
                    else:
                        await message.reply(
                            "⚠️ **You have already started this bot.**\nReferral points are only for new users.",
                            quote=True
                        )
            except Exception as e: 
                pass
            
        # --- FREE PREMIUM DEEP LINK LOGIC ---
        if len(message.command) > 1 and message.command[1] == "free_premium_info":
            bot_username = temp.U_NAME
            ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
            
            share_text = "Join this awesome bot for movies and series!"
            try:
                async for group in db.groups.find({"group_link": {"$ne": None}}).limit(1):
                    if group.get('group_link'):
                        share_text += f"\nJoin our Group: {group['group_link']}"
                    break
            except: pass
            
            encoded_text = urllib.parse.quote(share_text)
            share_url = f"https://t.me/share/url?url={ref_link}&text={encoded_text}"
            
            target = 5
            reward_desc = "1 Month"
            async for group in db.groups.find({"referral_enabled": True}).limit(1):
                target = group.get('referral_target', 5)
                break

            user_points = await db.get_referral_points(user_id)

            text = (
                "💰 **Get Free Premium Access!**\n\n"
                "Share your unique link below. \n"
                "• **New User:** You get +10 Points\n"
                "• **Old User:** No Points\n\n"
                f"📊 **Your Points:** {user_points}\n"
                f"**Reward:** {target} Referrals = {reward_desc} Premium Access\n\n"
                "You can claim your points for direct file access with no shorteners!\n\n"
                f"**Your Link:**\n`{ref_link}`"
            )
            
            buttons = [
                [InlineKeyboardButton("📤 Click to Share", url=share_url)],
                [InlineKeyboardButton("🎁 Claim Points", callback_data="claim_points"),
                 InlineKeyboardButton("❌ Close", callback_data="close_data")],
                [InlineKeyboardButton("📊 Check Premium Status", callback_data="check_prem_status"),
                 InlineKeyboardButton("🔙 Back", callback_data="open_prem_menu")]
            ]
            await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
            return

        # --- BUY PREMIUM DEEP LINK LOGIC ---
        if len(message.command) > 1 and message.command[1] == "buy_premium_info":
            text = script.PREM_UPGRADE_TXT.format(mention=message.from_user.mention)
            buttons = [
                [InlineKeyboardButton("💳 Check Plans & Pricing 💰", callback_data="check_plans")],
                [InlineKeyboardButton("🔙 Back", callback_data="open_prem_menu"),
                 InlineKeyboardButton("❌ Close", callback_data="close_data")]
            ]
            await message.reply_photo(
                photo=START_IMG, 
                caption=text, 
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            return

        if len(message.command) > 1 and not (message.command[1].startswith("verify_") or message.command[1].startswith("get_") or message.command[1].startswith("sendall_") or message.command[1] == "settings"):
             if not await check_fsub(client, message.from_user.id, message): return

    # -------------------------------------------------------------------------
    # 🔁 VERIFICATION RETURN LOGIC (WITH STATS)
    # -------------------------------------------------------------------------
    if len(message.command) > 1 and message.command[1].startswith("verify_"):
        try:
            data = message.command[1].split("_")
            level = int(data[1])
            verify_chatid = int(data[3]) 
            raw_link_id = data[4] if len(data) > 4 else "0"
            
            await db.update_verify_status(message.from_user.id, verify_chatid, level)
            
            try:
                group_settings = await db.get_group_settings(verify_chatid)
                shorteners = group_settings.get('shorteners', {})
                site_domain = None
                
                if str(level) in shorteners:
                    site_domain = shorteners[str(level)]['site']
                
                if not site_domain:
                    if level == 1 and info.SHORTLINK_URL_1: site_domain = info.SHORTLINK_URL_1
                    elif level == 2 and info.SHORTLINK_URL_2: site_domain = info.SHORTLINK_URL_2
                    elif level == 3 and info.SHORTLINK_URL_3: site_domain = info.SHORTLINK_URL_3

                if site_domain:
                    await db.update_daily_stats(verify_chatid, 'ver', count=1, domain=site_domain)
            except Exception as e:
                pass

            if await check_verification(client, message.from_user.id, verify_chatid, raw_link_id, message):
                if str(raw_link_id).startswith("SA-"):
                    real_search_id = raw_link_id.replace("SA-", "")
                    btn = [[InlineKeyboardButton("📂 Send All Files Now", url=f"https://t.me/{temp.U_NAME}?start=sendall_{real_search_id}_{verify_chatid}")]]
                    await message.reply(f"✅ **Verification Successful!**\n\nClick below to get all your files.", reply_markup=InlineKeyboardMarkup(btn))
                else:
                    btn = [[InlineKeyboardButton("📂 Get Your File Now", url=f"https://t.me/{temp.U_NAME}?start=get_{raw_link_id}_{verify_chatid}")]]
                    await message.reply(f"✅ **Verification Successful!**\n\nAb niche button par click karke file lein.", reply_markup=InlineKeyboardMarkup(btn))
            return
        except Exception as e: return await message.reply(f"❌ Error: {e}")

    # -------------------------------------------------------------------------
    # 📂 SEND ALL HANDLER (FSub + Verify + Batch Send + Streaming)
    # -------------------------------------------------------------------------
    if len(message.command) > 1 and message.command[1].startswith("sendall_"):
        try:
            data = message.command[1].split("_")
            search_id = int(data[1])
            src_chat_id = int(data[2]) if len(data) > 2 else message.chat.id
            
            if not await check_fsub(client, message.from_user.id, message): return 
            if not await check_verification(client, message.from_user.id, src_chat_id, f"SA-{search_id}", message): return 

            group_settings = await db.get_group_settings(src_chat_id)
            fsub = group_settings.get('fsub_channels', {}) if group_settings else {}
            
            id_4 = fsub.get('4')
            id_5 = fsub.get('5')
            post_verify_buttons = []

            if id_4:
                try:
                    id_4 = int(id_4)
                    try: await client.get_chat(id_4)
                    except: pass
                    try:
                        m4 = await client.get_chat_member(id_4, message.from_user.id)
                        is_joined_4 = m4.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                    except: is_joined_4 = False
                    
                    if not is_joined_4 and not await db.is_user_pending(message.from_user.id, id_4):
                         invite4 = await client.create_chat_invite_link(id_4, creates_join_request=True)
                         post_verify_buttons.append(InlineKeyboardButton("📢 Request Final (Slot 4)", url=invite4.invite_link))
                except: pass

            if id_5:
                is_joined_5 = False
                slot5_btn_url = None
                str_id_5 = str(id_5)
                if isinstance(id_5, int) or str_id_5.lstrip('-').isdigit():
                    try:
                        cid5 = int(id_5)
                        try: await client.get_chat(cid5)
                        except: pass
                        try:
                            m5 = await client.get_chat_member(cid5, message.from_user.id)
                            is_joined_5 = m5.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                        except: is_joined_5 = False
                        
                        if not is_joined_5:
                            invite5 = await client.create_chat_invite_link(cid5)
                            slot5_btn_url = invite5.invite_link
                    except: pass
                else:
                    is_joined_5 = False 
                    slot5_btn_url = str_id_5

                if not is_joined_5 and slot5_btn_url:
                    post_verify_buttons.append(InlineKeyboardButton("📢 Join Final (Slot 5)", url=slot5_btn_url))

            if post_verify_buttons:
                wrapper = []
                if len(post_verify_buttons) == 2: wrapper.append(post_verify_buttons)
                else: wrapper.append([post_verify_buttons[0]])
                
                wrapper.append([InlineKeyboardButton("✅ I Have Joined - Send Files", url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}")])
                
                await message.reply_text(
                    text="🛑 **Almost There!**\n\nPlease join the Final Channels below to get your files.",
                    reply_markup=InlineKeyboardMarkup(wrapper)
                )
                return 

            cached_data = await Media.get_search_query(search_id)
            if not cached_data:
                return await message.reply("❌ **Search Expired.**\nPlease search again in the group.")
            
            files = cached_data.get('files', [])
            if not files:
                 return await message.reply("❌ **No files found.**")

            msg = await message.reply(f"⚡ **Sending {len(files)} files...**\n_Please wait, this might take a moment._")
            
            cap_url = group_settings.get('caption_url')
            cap_btn_text = group_settings.get('caption_btn_text')
            cap_btn_url = group_settings.get('caption_btn_url')
            
            sent_count = 0
            filesarr = [] 
            
            # 🔥 SMART FALLBACK ENGINE WITH ANTI-FLOOD TIMER 🔥
            for file in files:
                try:
                    link_id = file['link_id']
                    file_details = await Media.get_file_details(link_id)
                    if not file_details: continue

                    caption = file['caption'] or file['file_name']
                    caption = re.sub(r"(https?://)?(t|telegram)[\.\s]?(me|dog)/[^\s]+", "", str(caption), flags=re.IGNORECASE)
                    caption = re.sub(r"https?://[^\s]+", "", caption, flags=re.IGNORECASE)
                    caption = re.sub(r"\s+", " ", caption).strip()
                    
                    if not caption: caption = f"{file['file_name']}"

                    if cap_url: final_caption = f"<b><a href='{cap_url}'>{caption}</a></b>"
                    else: final_caption = f"<b>{caption}</b>"
                    
                    final_caption += f"\n\n{script.CUSTOM_FOOTER}"
                    
                    btn_rows = []
                    if cap_btn_text and cap_btn_url:
                        btn_rows.append([InlineKeyboardButton(cap_btn_text, url=cap_btn_url)])
                    
                    # 1️⃣ BIN CHANNEL STREAMING LINK (With Fallback)
                    try:
                        bin_msg = await client.send_cached_media(chat_id=info.BIN_CHANNEL, file_id=file_details['file_id'])
                    except Exception:
                        try:
                            bin_msg = await client.copy_message(chat_id=info.BIN_CHANNEL, from_chat_id=file_details['chat_id'], message_id=file_details['msg_id'])
                        except Exception:
                            bin_msg = None

                    if bin_msg:
                        base_url = info.SITE_URL.rstrip('/') if info.SITE_URL else "http://127.0.0.1:8080"
                        watch_url = f"{base_url}/watch/{bin_msg.id}"
                        dl_url = f"{base_url}/{bin_msg.id}"
                        btn_rows.append([
                            InlineKeyboardButton("🍿 Watch Online", url=watch_url),
                            InlineKeyboardButton("⚡ Fast Download", url=dl_url)
                        ])
                    
                    # ADD 2 BUTTONS HERE ALSO FOR BATCH
                    btn_rows.append([
                        InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info"),
                        InlineKeyboardButton("💸 Buy Premium", url=f"https://t.me/{temp.U_NAME}?start=buy_premium_info")
                    ])

                    reply_markup = InlineKeyboardMarkup(btn_rows) if btn_rows else None

                    # 2️⃣ USER FILE SENDING (With On-Demand Caching & Auto-Fallback)
                    used_fallback = False
                    try:
                        # Attempt 1: Fast Cache Method (Purani ID Try Karega)
                        sent_media = await client.send_cached_media(
                            chat_id=message.from_user.id,
                            file_id=file_details['file_id'],
                            caption=final_caption,
                            reply_markup=reply_markup,
                            parse_mode=enums.ParseMode.HTML
                        )
                    except Exception as cache_err:
                        # Attempt 2: 🔥 ON-DEMAND CACHING (Bot B nayi ID nikalega aur DB update karega)
                        try:
                            db_msg = await client.get_messages(file_details['chat_id'], file_details['msg_id'])
                            new_file_id = None
                            if db_msg.video: new_file_id = db_msg.video.file_id
                            elif db_msg.document: new_file_id = db_msg.document.file_id
                            
                            if new_file_id:
                                # Nayi ID mil gayi! Isko DB me permanent save karo
                                await Media.update_file_id(file_details['file_id'], new_file_id)
                                
                                # Aur super-fast send_cached_media se bhej do!
                                sent_media = await client.send_cached_media(
                                    chat_id=message.from_user.id,
                                    file_id=new_file_id,
                                    caption=final_caption,
                                    reply_markup=reply_markup,
                                    parse_mode=enums.ParseMode.HTML
                                )
                            else:
                                raise Exception("No media found in DB Message")
                                
                        except Exception as update_err:
                            # Attempt 3: 🐢 Final Fallback (Agar kuch bhi kaam na kare toh copy_message use karega)
                            try:
                                sent_media = await client.copy_message(
                                    chat_id=message.from_user.id,
                                    from_chat_id=file_details['chat_id'],
                                    message_id=file_details['msg_id'],
                                    caption=final_caption,
                                    reply_markup=reply_markup,
                                    parse_mode=enums.ParseMode.HTML
                                )
                                used_fallback = True
                            except Exception as copy_err:
                                continue

                    filesarr.append(sent_media)
                    sent_count += 1
                    
                    # ⏱️ THE ANTI-FLOOD MAGIC TIMER
                    if used_fallback:
                        # Agar copy_message use hua hai, toh API pe load jyada hai, isliye 0.8 second ka aaram dega
                        await asyncio.sleep(0.8)
                    else:
                        # Agar fast cache use hua hai, toh load kam hai, isliye sirf 0.3 second ka nano-gap dega
                        await asyncio.sleep(0.3)
                    
                except Exception as e:
                    print(f"Send All Error: {e}")
                    continue
            
            await msg.delete()
            
            warning_msg = await message.reply(
                "⚠️ **DHYAN DEIN:**\n\nYe saari files theek **1 minute** baad yahan se automatically delete ho jayengi. Kripya isko jaldi se apne Saved Messages me forward kar lein!"
            )
            asyncio.create_task(auto_delete_batch(filesarr, warning_msg))
            
            return

        except Exception as e:
            return await message.reply(f"❌ Error: {e}")

    # -------------------------------------------------------------------------
    # 🔥 MAIN FLOW (get_linkid_chatid) - Single File + Streaming
    # -------------------------------------------------------------------------
    if len(message.command) > 1 and message.command[1].startswith("get_"):

        try:

            data = message.command[1].split("_")

            link_id = int(data[1])

            # 🔥 BUG FIX: Group ID ko Number (Integer) me convert karna zaroori hai

            src_chat_id = int(data[2]) if len(data) > 2 else message.chat.id
            
            if not await check_fsub(client, message.from_user.id, message): return 
            if not await check_verification(client, message.from_user.id, src_chat_id, link_id, message): return 

            group_settings = await db.get_group_settings(src_chat_id)
            fsub = group_settings.get('fsub_channels', {}) if group_settings else {}
            
            id_4 = fsub.get('4')
            id_5 = fsub.get('5')
            
            post_verify_buttons = []

            if id_4:
                try:
                    id_4 = int(id_4)
                    try: await client.get_chat(id_4)
                    except: pass
                    
                    try:
                        m4 = await client.get_chat_member(id_4, message.from_user.id)
                        is_joined_4 = m4.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                    except UserNotParticipant: is_joined_4 = False
                    except: is_joined_4 = True 
                    
                    if not is_joined_4 and not await db.is_user_pending(message.from_user.id, id_4):
                         invite4 = await client.create_chat_invite_link(id_4, creates_join_request=True)
                         post_verify_buttons.append(InlineKeyboardButton("📢 Request Final (Slot 4)", url=invite4.invite_link))
                except: pass

            if id_5:
                is_joined_5 = False
                slot5_btn_url = None
                
                str_id_5 = str(id_5)
                if isinstance(id_5, int) or str_id_5.lstrip('-').isdigit():
                    try:
                        cid5 = int(id_5)
                        try: await client.get_chat(cid5)
                        except: pass
                        
                        try:
                            m5 = await client.get_chat_member(cid5, message.from_user.id)
                            is_joined_5 = m5.status in [enums.ChatMemberStatus.MEMBER, enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                        except UserNotParticipant: is_joined_5 = False
                        except: is_joined_5 = True 
                        
                        if not is_joined_5:
                            invite5 = await client.create_chat_invite_link(cid5)
                            slot5_btn_url = invite5.invite_link
                    except: pass
                else:
                    is_joined_5 = False 
                    slot5_btn_url = str_id_5

                if not is_joined_5 and slot5_btn_url:
                    post_verify_buttons.append(InlineKeyboardButton("📢 Join Final (Slot 5)", url=slot5_btn_url))

            if post_verify_buttons:
                wrapper = []
                if len(post_verify_buttons) == 2: wrapper.append(post_verify_buttons)
                else: wrapper.append([post_verify_buttons[0]])
                
                wrapper.append([InlineKeyboardButton("✅ I Have Joined - Get File", url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}")])
                
                await message.reply_text(
                    text="🛑 **Almost There!**\n\nPlease join the Final Channels below to get your file.",
                    reply_markup=InlineKeyboardMarkup(wrapper)
                )
                return 

            file_data = await Media.get_file_details(link_id)
            search_data = await Media.get_search_data(link_id)
            
            if not file_data: return await message.reply("❌ **File Not Found.**")
            
            file_name = search_data.get('file_name', 'Unknown File')
            raw_caption = search_data.get('caption')

            if not raw_caption:
                caption = f"{file_name}"
            else:
                caption = str(raw_caption)
                caption = re.sub(r"(https?://)?(t|telegram)[\.\s]?(me|dog)/[^\s]+", caption, flags=re.IGNORECASE)
                caption = re.sub(r"https?://[^\s]+", "", caption, flags=re.IGNORECASE)
                remove_patterns = [r"Join\s?(Now|Channel|Us|Here)", r"Aa\s?Jao", r"🤞", r"➜", r"\)⁠➜", r"👉", r"\[@\w+\]", r"@\w+"]
                for pattern in remove_patterns:
                    caption = re.sub(pattern, "", caption, flags=re.IGNORECASE)
                caption = re.sub(r"\s+", " ", caption).strip()
                
                if not caption:
                    caption = f"{file_name}"

            if not group_settings:
                group_settings = await db.get_group_settings(src_chat_id)
            
            cap_url = group_settings.get('caption_url')
            if cap_url:
                final_caption = f"<b><a href='{cap_url}'>{caption}</a></b>"
            else:
                final_caption = f"<b>{caption}</b>"

            final_caption += f"\n\n{script.CUSTOM_FOOTER}"

            reply_markup = None
            btn_rows = []

            cap_btn_text = group_settings.get('caption_btn_text')
            cap_btn_url = group_settings.get('caption_btn_url')
            if cap_btn_text and cap_btn_url:
                btn_rows.append([InlineKeyboardButton(cap_btn_text, url=cap_btn_url)])

            grp_link = group_settings.get('group_link')
            if grp_link:
                btn_rows.append([InlineKeyboardButton("Back to Group 🔙", url=grp_link)])

            # 🔥 SMART 2-BUTTON MENU FOR FILE CAPTIONS
            btn_rows.append([
                InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info"),
                InlineKeyboardButton("💸 Buy Premium", url=f"https://t.me/{temp.U_NAME}?start=buy_premium_info")
            ])

            # 1️⃣ BIN CHANNEL STREAMING LINK (With Fallback)
            try:
                bin_msg = await client.send_cached_media(chat_id=info.BIN_CHANNEL, file_id=file_data.get('file_id'))
            except Exception:
                try:
                    bin_msg = await client.copy_message(chat_id=info.BIN_CHANNEL, from_chat_id=file_data['chat_id'], message_id=file_data['msg_id'])
                except Exception as e:
                    print(f"Bin Channel Error: {e}")
                    bin_msg = None

            if bin_msg:
                base_url = info.SITE_URL.rstrip('/') if info.SITE_URL else "http://127.0.0.1:8080"
                watch_url = f"{base_url}/watch/{bin_msg.id}"
                dl_url = f"{base_url}/{bin_msg.id}"
                btn_rows.append([
                    InlineKeyboardButton("🍿 Watch Online", url=watch_url),
                    InlineKeyboardButton("⚡ Fast Download", url=dl_url)
                ])

            if btn_rows:
                reply_markup = InlineKeyboardMarkup(btn_rows)

            # 2️⃣ USER FILE SENDING (With On-Demand Caching & Auto-Fallback)
            try:
                # Attempt 1: Default Method
                sent_media = await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=file_data.get('file_id'),
                    caption=final_caption,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as cache_err:
                # Attempt 2: 🔥 ON-DEMAND CACHING (Nayi ID nikal kar DB update karna)
                try:
                    db_msg = await client.get_messages(file_data['chat_id'], file_data['msg_id'])
                    new_file_id = None
                    if db_msg.video: new_file_id = db_msg.video.file_id
                    elif db_msg.document: new_file_id = db_msg.document.file_id
                    
                    if new_file_id:
                        # Database Update
                        await Media.update_file_id(file_data['file_id'], new_file_id)
                        
                        # Nayi ID se file bhejna
                        sent_media = await client.send_cached_media(
                            chat_id=message.from_user.id,
                            file_id=new_file_id,
                            caption=final_caption,
                            reply_markup=reply_markup,
                            parse_mode=enums.ParseMode.HTML
                        )
                    else:
                        raise Exception("No media found in DB Message")
                        
                except Exception as update_err:
                    # Attempt 3: 🐢 Auto-Fallback to copy_message
                    try:
                        sent_media = await client.copy_message(
                            chat_id=message.from_user.id,
                            from_chat_id=file_data['chat_id'],
                            message_id=file_data['msg_id'],
                            caption=final_caption,
                            reply_markup=reply_markup,
                            parse_mode=enums.ParseMode.HTML
                        )
                    except Exception as copy_err:
                        return await message.reply(f"❌ **Dono Method Fail Ho Gaye!**\nCache Error: `{cache_err}`\nUpdate Error: `{update_err}`")

            warning_msg = await sent_media.reply_text(
                "⚠️ **DHYAN DEIN:**\n\nYe file theek **1 minute** baad yahan se automatically delete ho jayegi. Kripya isko jaldi se apne Saved Messages me forward kar lein!",
                quote=True
            )
            asyncio.create_task(auto_delete_single(sent_media, warning_msg, message.command[1]))
                
        except Exception as e: await message.reply(f"❌ Error: {e}")
        return

@Client.on_message(filters.command("connect") & filters.group)
async def connect_handler(client, message):
    try:
        user_id = message.from_user.id
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]: 
            return await message.reply("❌ **Admin Only.** You cannot use this.")
        
        try:
            admin_ids = []
            async for admin in client.get_chat_members(message.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
                admin_ids.append(admin.user.id)
            await db.groups.update_one({"id": message.chat.id}, {"$set": {"admins": admin_ids}}, upsert=True)
        except Exception:
            pass

        await db.add_group(message.chat.id, message.chat.title)
        
        await message.reply_text(f"✅ **Successfully Connected!**\nAb aap PM me `/settings` use karke is group ko manage kar sakte hain.")
    except Exception as e:
        await message.reply_text(f"❌ Error: {e}")

@Client.on_message(filters.new_chat_members)
async def new_chat(client, message):
    try:
        if (await client.get_me()).id in [u.id for u in message.new_chat_members]:
            await message.reply_text("Thanks for adding me! 👋\n\nPromote me to Admin and type /connect to setup.")
    except: pass

@Client.on_message(filters.command("set_shortner") & filters.user(ADMINS))
async def set_shortner_dynamic(client, message): 
    await message.reply("⚠️ This command is deprecated. Please use /settings in PM to configure shorteners.")

# ==============================================================================
# 🎛️ MANUAL DB ROUTING COMMAND (/setindex)
# ==============================================================================
@Client.on_message(filters.command("setindex") & filters.user(ADMINS))
async def set_index_db_command(client, message):
    if len(message.command) < 2:
        current = await Media.get_active_index_db()
        return await message.reply(f"⚠️ **Syntax:** `/setindex [1/2/3]`\n\n📌 **Current Active DB:** `DB {current}`")
    
    try:
        db_num = int(message.command[1])
        if db_num not in [1, 2, 3]:
            return await message.reply("❌ Please choose between 1, 2, or 3.")
            
        if db_num == 2 and not Media.has_db2:
            return await message.reply("❌ **DB 2 is not configured** in info.py!")
        if db_num == 3 and not Media.has_db3:
            return await message.reply("❌ **DB 3 is not configured** in info.py!")
            
        await Media.set_active_index_db(db_num)
        await message.reply(f"✅ **Indexing Switched Successfully!**\n\nAb saari nayi files **Database {db_num}** mein save hongi.")
    except ValueError:
        await message.reply("❌ Invalid number. Please use 1, 2, or 3.")

# ==============================================================================
# 📊 NEW DETAILED /STATS COMMAND (MULTI-DB DASHBOARD)
# ==============================================================================
@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_handler(client, message):
    try:
        msg = await message.reply("🔄 Fetching multi-database stats...")
        
        users = await db.total_users_count()
        groups = await db.total_groups_count()
        files = await Media.total_files_count()
        
        db_stats = await Media.get_detailed_stats()
        if not db_stats:
            return await msg.edit("❌ Error fetching database stats.")

        current_db = await Media.get_active_index_db()

        text = f"📊 **BOT STATISTICS**\n\n"
        text += f"👤 **Users:** `{users}`\n"
        text += f"👥 **Groups:** `{groups}`\n"
        text += f"📂 **Total Files:** `{files}`\n\n"
        text += f"🎯 **Active Indexing DB:** `DB {current_db}`\n\n"
        
        # 🎨 Helper function to design DB Box
        def format_db_block(name, stats, has_cache=False):
            t_mb = stats['total'] / (1024*1024)
            tx_mb = stats['text'] / (1024*1024)
            m_mb = stats['main'] / (1024*1024)
            
            pct = (t_mb / 512.0) * 100
            fill = int(pct / 10)
            fill = min(fill, 10)
            bar = "🟩" * fill + "⬜" * (10 - fill)
            
            blk = f"🗄 **{name}**\n"
            blk += f"💽 Used: `{t_mb:.2f} MB` / `512 MB` ({pct:.2f}%)\n"
            blk += f"[{bar}]\n"
            blk += f" ├ 🔍 Text Index: `{tx_mb:.2f} MB`\n"
            if has_cache:
                c_mb = stats['cache'] / (1024*1024)
                blk += f" ├ 🗑 Cache & Temp: `{c_mb:.2f} MB`\n"
            blk += f" └ 📁 Main Data: `{m_mb:.2f} MB`\n\n"
            return blk

        # 🖨️ Print Available Databases
        if db_stats.get('db1'): text += format_db_block("DATABASE 1 (Master)", db_stats['db1'], True)
        if db_stats.get('db2'): text += format_db_block("DATABASE 2", db_stats['db2'], False)
        if db_stats.get('db3'): text += format_db_block("DATABASE 3", db_stats['db3'], False)

        overall_mb = db_stats['total_overall'] / (1024*1024)
        text += f"🌐 **Total Cloud Storage Used:** `{overall_mb:.2f} MB`"
            
        await msg.edit(text)
        
    except Exception as e: 
        await message.reply(f"❌ Error: {e}")

# ==============================================================================
# 💎 PREMIUM MAIN MENU (SMOOTH TRANSITIONS)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^open_prem_menu$"))
async def premium_main_menu(client, query):
    await query.answer()
    text = (
        "💎 **Premium Access**\n\n"
        "Get premium access to enjoy direct files with no shorteners or ads.\n\n"
        "You can either purchase it directly or earn it for free by referring new users to our bot."
    )
    buttons = [
        [InlineKeyboardButton("💎 Free Premium", callback_data="free_prem_page")],
        [InlineKeyboardButton("💸 Buy Premium", callback_data="buy_premium")], 
        [InlineKeyboardButton("🔙 Back", callback_data="start_back")] 
    ]
    try:
        if query.message.photo:
            await query.message.edit_media(InputMediaPhoto(START_IMG, caption=text), reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.delete()
            await client.send_photo(query.message.chat.id, photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass

# ==============================================================================
# 💳 BUY PREMIUM PITCH & PLANS
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^buy_premium$"))
async def buy_premium_handler(client, query):
    await query.answer()
    text = script.PREM_UPGRADE_TXT.format(mention=query.from_user.mention)
    
    buttons = [
        [InlineKeyboardButton("💳 Check Plans & Pricing 💰", callback_data="check_plans")],
        [InlineKeyboardButton("🔙 Back", callback_data="open_prem_menu"),
         InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ]
    try:
        if query.message.photo:
            await query.message.edit_media(InputMediaPhoto(START_IMG, caption=text), reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.delete()
            await client.send_photo(query.message.chat.id, photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass

@Client.on_callback_query(filters.regex(r"^check_plans$"))
async def check_plans_handler(client, query):
    await query.answer("Fetching Plans...", show_alert=False)
    
    if CUSTOM_QR_URL: qr_link = CUSTOM_QR_URL
    else: qr_link = f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=upi://pay?pa={MERCHANT_UPI_ID}&pn=Premium"

    text = script.PREM_PLANS_TXT.format(upi_id=MERCHANT_UPI_ID)
    
    buttons = [
        [InlineKeyboardButton("👉 📸 Send Payment Screenshot", url=PAYMENT_SUPPORT_LINK)],
        [InlineKeyboardButton("💎 Custom Plan 💎", callback_data="custom_plan_ui")],
        [InlineKeyboardButton("🔙 Back", callback_data="buy_premium"),
         InlineKeyboardButton("❌ Close", callback_data="close_data")]
    ]
    try:
        if query.message.photo:
            await query.message.edit_media(InputMediaPhoto(qr_link, caption=text), reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.delete()
            await client.send_photo(chat_id=query.message.chat.id, photo=qr_link, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await client.send_message(query.message.chat.id, text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^custom_plan_ui$"))
async def custom_plan_handler(client, query):
    await query.answer()
    text = script.PREM_CUSTOM_TXT.format(mention=query.from_user.mention)
    
    buttons = [
        [InlineKeyboardButton("☎️ Contact Owner To Know More", url=CONTACT_OWNER_LINK)],
        [InlineKeyboardButton("🔙 Back", callback_data="check_plans")]
    ]
    try:
        if query.message.photo:
            await query.message.edit_media(InputMediaPhoto(START_IMG, caption=text), reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.delete()
            await client.send_photo(query.message.chat.id, photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass

@Client.on_callback_query(filters.regex(r"^free_prem_page"))
async def free_premium_page(client, query):
    await query.answer() 
    
    user_id = query.from_user.id
    bot_username = temp.U_NAME
    
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    
    share_text = "Join this awesome bot for movies and series!"
    try:
        async for group in db.groups.find({"group_link": {"$ne": None}}).limit(1):
            if group.get('group_link'):
                share_text += f"\nJoin our Group: {group['group_link']}"
            break
    except: pass
    
    encoded_text = urllib.parse.quote(share_text)
    share_url = f"https://t.me/share/url?url={ref_link}&text={encoded_text}"
    
    target = 5
    reward_desc = "1 Month"
    async for group in db.groups.find({"referral_enabled": True}).limit(1):
        target = group.get('referral_target', 5)
        break
        
    user_points = await db.get_referral_points(user_id)
    
    text = (
        "💰 **Get Free Premium Access!**\n\n"
        "Share your unique link below. \n"
        "• **New User:** You get +10 Points\n"
        "• **Old User:** No Points\n\n"
        f"📊 **Your Points:** {user_points}\n"
        f"**Reward:** {target} Referrals = {reward_desc} Premium Access\n\n"
        "You can claim your points for direct file access with no shorteners!\n\n"
        f"**Your Link:**\n`{ref_link}`"
    )
    
    buttons = [
        [InlineKeyboardButton("📤 Click to Share", url=share_url)],
        [InlineKeyboardButton("🎁 Claim Points", callback_data="claim_points"),
         InlineKeyboardButton("❌ Close", callback_data="close_data")],
        [InlineKeyboardButton("📊 Check Premium Status", callback_data="check_prem_status"),
         InlineKeyboardButton("🔙 Back", callback_data="open_prem_menu")]
    ]
    try:
        if query.message.photo:
            await query.message.edit_media(InputMediaPhoto(START_IMG, caption=text), reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.delete()
            await client.send_photo(query.message.chat.id, photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass

@Client.on_callback_query(filters.regex(r"^claim_points"))
async def claim_points_handler(client, query):
    user_id = query.from_user.id
    
    target = 5
    reward_time = 2592000 
    
    async for group in db.groups.find({"referral_enabled": True}).limit(1):
        target = group.get('referral_target', 5)
        reward_time = group.get('referral_reward_time', 2592000)
        break

    required_points = target * 10
    
    if await db.is_user_premium(user_id):
        return await query.answer("❌ You are already a Premium User!", show_alert=True)

    points = await db.get_referral_points(user_id)
    
    if points >= required_points:
        success, expiry = await db.claim_premium_reward(user_id, required_points, reward_time)
        if success:
            exp_date = datetime.datetime.fromtimestamp(expiry).strftime('%Y-%m-%d')
            await query.answer("🎉 Premium Claimed Successfully!", show_alert=True)
            text = (
                f"🎉 **Congratulations!**\n\n"
                f"You have claimed **Premium Access**.\n"
                f"✅ No Shorteners\n"
                f"✅ Direct Files\n\n"
                f"📅 **Expiry:** {exp_date}"
            )
            try:
                if query.message.photo:
                    await query.message.edit_media(InputMediaPhoto(START_IMG, caption=text), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="free_prem_page")]]))
                else:
                    await query.message.delete()
                    await client.send_photo(query.message.chat.id, photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="free_prem_page")]]))
            except: pass
        else:
            await query.answer("❌ Error claiming.", show_alert=True)
    else:
        needed = required_points - points
        text = (
            f"🏆 **Your Referral Stats**\n\n"
            f"You currently have **{points}** referral points.\n"
            f"You need **{needed}** more points to claim premium."
        )
        await query.answer("Not enough points!", show_alert=False)
        try:
            if query.message.photo:
                await query.message.edit_media(InputMediaPhoto(START_IMG, caption=text), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="free_prem_page")]]))
            else:
                await query.message.delete()
                await client.send_photo(query.message.chat.id, photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="free_prem_page")]]))
        except: pass

@Client.on_callback_query(filters.regex(r"^check_prem_status"))
async def check_status_handler(client, query):
    await query.answer() 
    
    user_id = query.from_user.id
    is_prem, msg = await db.get_premium_status(user_id)
    
    status_icon = "✅ Active" if is_prem else "❌ Inactive"
    
    text = (
        f"📊 **Premium Status**\n\n"
        f"**Status:** {status_icon}\n"
        f"**Validity:** {msg}"
    )
    try:
        if query.message.photo:
            await query.message.edit_media(InputMediaPhoto(START_IMG, caption=text), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="free_prem_page")]]))
        else:
            await query.message.delete()
            await client.send_photo(query.message.chat.id, photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="free_prem_page")]]))
    except: pass

@Client.on_callback_query(filters.regex(r"^close_data"))
async def close_data(client, query):
    await query.answer()
    await query.message.delete()

# ==============================================================================
# 🎁 MYPLAN & 5-MIN FREE TRIAL LOGIC
# ==============================================================================

@Client.on_message(filters.command(["myplan", "plan"]) & filters.private)
async def myplan_command(client, message):
    user_id = message.from_user.id
    is_prem, expiry_msg = await db.get_premium_status(user_id)
    
    if is_prem:
        text = script.MYPLAN_ACTIVE_TXT.format(mention=message.from_user.mention, expiry_date=expiry_msg)
        buttons = [
            [InlineKeyboardButton("💳 Check Plans & Purchase", callback_data="buy_premium")],
            [InlineKeyboardButton("🔙 Back", callback_data="start_back"),
             InlineKeyboardButton("❌ Close", callback_data="close_data")]
        ]
        await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        text = script.NO_PREM_TXT
        buttons = [
            [InlineKeyboardButton("🎁 Claim 5-Min Free Trial 🎁", callback_data="claim_5min_trial")],
            [InlineKeyboardButton("💳 Check Plan & Purchase", callback_data="buy_premium")],
            [InlineKeyboardButton("🔙 Back", callback_data="start_back"),
             InlineKeyboardButton("❌ Close", callback_data="close_data")]
        ]
        await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^claim_5min_trial$"))
async def claim_trial_handler(client, query):
    user_id = query.from_user.id
    
    user_data = await db.users.find_one({'id': user_id})
    if user_data and user_data.get('trial_claimed', False):
        await query.answer("❌ Aap ye Free Trial pehle hi use kar chuke hain!", show_alert=True)
        return
        
    await query.answer("🚀 Premium Features Unlocked!", show_alert=False)
    
    duration_seconds = 300
    current_time = time.time()
    new_expiry = current_time + duration_seconds
    
    await db.users.update_one({'id': user_id}, {'$set': {'premium_expiry': new_expiry, 'trial_claimed': True}}, upsert=True)
    
    buttons = [
        [InlineKeyboardButton("💎 Buy Premium (Direct Files)", callback_data="buy_premium")],
        [InlineKeyboardButton("🔙 Back", callback_data="start_back")]
    ]
    try:
        if query.message.photo:
            await query.message.edit_media(InputMediaPhoto(START_IMG, caption=script.TRIAL_ACTIVE_TXT), reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.delete()
            await client.send_photo(query.message.chat.id, photo=START_IMG, caption=script.TRIAL_ACTIVE_TXT, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass

# ==============================================================================
# 🕵️ ADMIN COMMAND: ALL GROUPS LIST (/groups)
# ==============================================================================

async def show_groups_page(client, request_obj, page):
    LIMIT = 10 
    
    total_groups = await db.groups.count_documents({})

    if total_groups == 0:
        text = "❌ **Database me koi group nahi mila.**"
        if hasattr(request_obj, "edit_text"):
            return await request_obj.edit_text(text)
        else:
            return await request_obj.reply(text)

    max_pages = (total_groups + LIMIT - 1) // LIMIT
    
    if page >= max_pages: page = max_pages - 1
    if page < 0: page = 0
    
    skip_count = page * LIMIT
    cursor = db.groups.find({}).skip(skip_count).limit(LIMIT)
    
    current_groups = []
    async for group in cursor:
        title = group.get('title', 'Unknown Group')
        chat_id = group.get('id')
        if chat_id:
            current_groups.append((title, chat_id))
    
    buttons = []
    for title, chat_id in current_groups:
        short_title = title[:30] + "..." if len(title) > 30 else title
        buttons.append([InlineKeyboardButton(f"📂 {short_title}", callback_data=f"get_grp_link#{chat_id}#{page}")])
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin_grp_page#{page-1}"))
    nav_row.append(InlineKeyboardButton(f"{page+1}/{max_pages}", callback_data="ignore"))
    if page < max_pages - 1:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_grp_page#{page+1}"))
        
    if nav_row:
        buttons.append(nav_row)
        
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
    
    text = f"📊 **Bot's Connected Groups**\n\nTotal Groups: `{total_groups}`\n\nKisi bhi group me join hone ya open karne ke liye uspar click karein:"
    
    try:
        if hasattr(request_obj, "edit_text"):
            await request_obj.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await request_obj.reply(text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        pass 

@Client.on_message(filters.command("groups") & filters.private, group=-2)
async def groups_list_command(client, message):
    user_id = message.from_user.id
    
    if user_id not in ADMINS:
        return await message.reply("❌ **Access Denied:** Ye command sirf Bot Owner aur Admins ke liye hai.")
        
    wait_msg = await message.reply("🔄 **Loading Groups...**")
    await show_groups_page(client, wait_msg, 0)

@Client.on_callback_query(filters.regex(r"^admin_grp_page#"))
async def admin_grp_page_handler(client, query):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Not Allowed", show_alert=True)
        
    await query.answer() 
    
    page = int(query.data.split("#")[1])
    await show_groups_page(client, query.message, page)

@Client.on_callback_query(filters.regex(r"^get_grp_link#"))
async def get_grp_link_handler(client, query):
    if query.from_user.id not in ADMINS:
        return await query.answer("❌ Not Allowed", show_alert=True)
        
    data = query.data.split("#")
    chat_id = int(data[1])
    page = int(data[2])
    
    await query.answer("Fetching Invite Link... ⏳", show_alert=False)
    
    try:
        chat = await client.get_chat(chat_id)
        
        if chat.invite_link:
            invite_link = chat.invite_link
        else:
            invite_link = await client.export_chat_invite_link(chat_id)
            
        btn = [
            [InlineKeyboardButton("🚪 Open / Join Group", url=invite_link)],
            [InlineKeyboardButton("🔙 Back to List", callback_data=f"admin_grp_page#{page}")]
        ]
        
        await query.message.edit_text(
            f"✅ **Group Name:** {chat.title}\n"
            f"🆔 **Group ID:** `{chat_id}`\n"
            f"👥 **Members:** `{chat.members_count}`\n\n"
            f"Niche diye gaye button par click karke group open karein:",
            reply_markup=InlineKeyboardMarkup(btn)
        )
        
    except Exception as e:
        btn = [[InlineKeyboardButton("🔙 Back to List", callback_data=f"admin_grp_page#{page}")]]
        error_msg = str(e)
        
        await query.message.edit_text(
            f"❌ **Link Generate Nahi Hua!**\n\n"
            f"🆔 ID: `{chat_id}`\n"
            f"**Reason:** Bot ko is group se nikal diya gaya hai ya uske paas invite link banane ki Admin Permission nahi hai.\n\n"
            f"*(Error: {error_msg})*",
            reply_markup=InlineKeyboardMarkup(btn)
        )

# ==============================================================================
# 🚀 SMART ID REFRESH COMMAND & UI (Multi-Bot Setup)
# ==============================================================================

async def get_refresh_ui_components(client):
    """DB se indexed channels fetch karta hai aur valid/invalid dono dikhata hai"""
    channels = await Media.data_col1.distinct("chat_id")
    if Media.has_db2:
        channels.extend(await Media.data_col2.distinct("chat_id"))
    if Media.has_db3:
        channels.extend(await Media.data_col3.distinct("chat_id"))
        
    channels = list(set(channels))
    channels = [c for c in channels if str(c).startswith("-100")]
    
    valid_channels = []
    buttons = []
    for ch in channels:
        try:
            chat = await client.get_chat(ch)
            if chat.type == enums.ChatType.CHANNEL:
                name = chat.title[:20] + "..." if len(chat.title) > 20 else chat.title
                buttons.append([InlineKeyboardButton(f"📢 {name}", callback_data=f"ref_ch_do#{ch}")])
                valid_channels.append(ch)
        except Exception:
            # 🔥 FIX: Agar Bot channel me nahi hai (Kicked/Not Admin), toh uski ID dikhayega!
            buttons.append([InlineKeyboardButton(f"🔒 ID: {ch}", callback_data=f"ref_ch_do#{ch}")])
            valid_channels.append(ch) 
            
    if valid_channels:
        buttons.append([InlineKeyboardButton("♻️ Refresh All Channels", callback_data="ref_all_ch")])
        
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_data")])
    return valid_channels, InlineKeyboardMarkup(buttons)

async def run_refresh_for_channel(client, channel_id, status_msg=None, context=None):
    """Resume Feature + Stop Button + DB Checkpoints"""
    updated_count = 0
    msg_count = 0
    
    # 1. MongoDB se purani progress check karein (Agar pehle kabhi roka tha)
    progress_data = await db.bot_settings.find_one({"_id": f"progress_{channel_id}"})
    last_index = progress_data.get("last_index", 0) if progress_data else 0
    
    try:
        chat = await client.get_chat(channel_id)
        ch_name = chat.title[:20] + "..." if chat.title else str(channel_id)

        # 🚀 IMMEDIATE UI UPDATE (Taaki pata chale bot zinda hai)
        if status_msg:
            try:
                if context and context.get("is_all"):
                    await status_msg.edit(f"🔄 **Step 1: Reading Database ({context['current_ch']}/{context['total_chs']})**\n📢 `{ch_name}`\n_Loading files from MongoDB... please wait..._")
                else:
                    await status_msg.edit(f"🔄 **Step 1: Reading Database...**\n📢 `{ch_name}`\n_Loading files from MongoDB..._")
            except Exception: pass

        # 2. MongoDB se Message IDs ki list
        docs = []
        async for doc in Media.data_col1.find({"chat_id": channel_id}): docs.append(doc)
        if Media.has_db2:
            async for doc in Media.data_col2.find({"chat_id": channel_id}): docs.append(doc)
        if Media.has_db3:
            async for doc in Media.data_col3.find({"chat_id": channel_id}): docs.append(doc)
        
        total_msgs = len(docs)
        if total_msgs == 0: return 0

        # 🚀 UI UPDATE (DB Reading Complete)
        if status_msg:
            try:
                await status_msg.edit(f"✅ **Step 2: Database Loaded!**\n📂 Found `{total_msgs}` files for `{ch_name}`.\n_Starting Telegram API Sync..._")
            except Exception: pass

        # 🚀 STARTING FROM LAST CHECKPOINT
        msg_count = last_index
        chunk_size = 100 

        # Button row for UI
        stop_btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛑 Stop & Save Progress", callback_data=f"stop_refresh#{channel_id}")]])

        for i in range(last_index, total_msgs, chunk_size):
            # 🔥 PAUSE/STOP CHECK: Har chunk ke baad check karega ki aapne Stop toh nahi kiya
            if getattr(temp, "STOP_REFRESH", False):
                await db.bot_settings.update_one({"_id": f"progress_{channel_id}"}, {"$set": {"last_index": i}}, upsert=True)
                if status_msg: 
                    try: await status_msg.edit(f"⏸ **Refresh Paused!**\n\n📢 Channel: `{ch_name}`\n📍 Saved at: `{i}/{total_msgs}`\n\nJab aap dubara chalayenge, ye yahin se shuru hoga.")
                    except: pass
                return updated_count

            chunk = docs[i : i + chunk_size]
            msg_ids = [doc['msg_id'] for doc in chunk]
            
            try:
                messages = await client.get_messages(channel_id, message_ids=msg_ids)
                for msg in messages:
                    msg_count += 1
                    if not msg or getattr(msg, "empty", False): continue
                    media = msg.video or msg.document
                    if media:
                        strict_filter = {'file_unique_id': media.file_unique_id, 'chat_id': channel_id}
                        update_data = {'$set': {'file_id': media.file_id}}
                        
                        res1 = await Media.data_col1.update_one(strict_filter, update_data)
                        if res1.modified_count > 0: updated_count += 1
                        else:
                            if Media.has_db2:
                                res2 = await Media.data_col2.update_one(strict_filter, update_data)
                                if res2.modified_count > 0: updated_count += 1
                            elif Media.has_db3:
                                res3 = await Media.data_col3.update_one(strict_filter, update_data)
                                if res3.modified_count > 0: updated_count += 1
            except FloodWait as e:
                if status_msg:
                    try: await status_msg.edit(f"⏳ **Telegram Rate Limit Hit!**\n_Sleeping safely for {e.value} seconds... DO NOT CLOSE_")
                    except: pass
                await asyncio.sleep(e.value + 2)
            except Exception: pass

            # ⏱ API Safety Sleep
            await asyncio.sleep(2)

            # 🚀 CHECKPOINT SAVE: Har 1000 files ke baad DB me progress save karo
            if msg_count % 1000 == 0:
                await db.bot_settings.update_one({"_id": f"progress_{channel_id}"}, {"$set": {"last_index": i}}, upsert=True)

            # 🚀 LIVE DASHBOARD UPDATE
            if status_msg and (msg_count % 200 == 0 or msg_count == total_msgs):
                pct = (msg_count / total_msgs) * 100 if total_msgs > 0 else 0
                if context and context.get("is_all"):
                    cur_ch = context['current_ch']
                    tot_chs = context['total_chs']
                    glb_upd = context['global_updated'] + updated_count
                    text = (
                        f"🔄 **Step 3: Refreshing Channels ({cur_ch}/{tot_chs}) {'[Resumed]' if last_index > 0 else ''}**\n\n"
                        f"📢 **Channel:** `{ch_name}`\n"
                        f"📁 **Files in Queue:** `{total_msgs}`\n"
                        f"📊 **Processing:** `{msg_count} / {total_msgs}` ({pct:.1f}%)\n"
                        f"✅ **Global Synced:** `{glb_upd}`\n\n"
                        f"⚠️ _Dhyan dein: Stop button dabane par progress save ho jayegi._"
                    )
                else:
                    text = (
                        f"🔄 **Step 3: Refreshing Index {'[Resumed]' if last_index > 0 else ''}**\n\n"
                        f"📢 **Channel:** `{ch_name}`\n"
                        f"📁 **Files in Queue:** `{total_msgs}`\n"
                        f"📊 **Processing:** `{msg_count} / {total_msgs}` ({pct:.1f}%)\n"
                        f"✅ **IDs Synced:** `{updated_count}`\n\n"
                        f"⚠️ _Dhyan dein: Stop button dabane par progress save ho jayegi._"
                    )
                try: await status_msg.edit(text, reply_markup=stop_btn)
                except: pass

        # ✅ TASK COMPLETE: Finish hone par progress mita do
        await db.bot_settings.delete_one({"_id": f"progress_{channel_id}"})
                
    except Exception as e:
        logger.error(f"Error: {e}")
            
    return updated_count

@Client.on_message(filters.command("refresh_index") & filters.user(ADMINS))
async def refresh_index_command(client, message):
    temp.STOP_REFRESH = False # 🚀 Har baar command chalne par purana stop hatayein
    msg = await message.reply("🔄 **Fetching indexed channels from Database...**\n_Please wait..._")
    try:
        channels, reply_markup = await get_refresh_ui_components(client)
        if not channels:
            return await msg.edit("❌ **Koi Indexed Channel Nahi Mila!**\nPehle files save karein.")
            
        await msg.edit(
            "👇 **Select a channel to refresh its File IDs:**\n\n"
            "_Ye command aapke database ki files ko naye bot ki ID se sync karegi._",
            reply_markup=reply_markup
        )
    except Exception as e:
        await msg.edit(f"❌ **Command Error:** `{str(e)}`")

@Client.on_callback_query(filters.regex(r"^ref_ch_do#(-?\d+)$") & filters.user(ADMINS))
async def ref_ch_single(client, query):
    channel_id = int(query.matches[0].group(1))
    status_msg = query.message
    temp.STOP_REFRESH = False
    
    # Simplified Admin Check
    try:
        chat = await client.get_chat(channel_id)
        ch_name = chat.title[:20] + "..." if chat.title else str(channel_id)
    except Exception:
        # Agar bot admin nahi hai ya usko nikal diya gaya hai
        ch_name = "Unknown Private Channel"
        short_id = str(channel_id).replace("-100", "")
        ch_link = f"https://t.me/c/{short_id}/1" 

        text = (
            f"❌ **Admin Permission Missing!**\n\n"
            f"Bot channel me admin nahi hai ya isko nikal diya gaya hai.\n"
            f"🆔 ID: `{channel_id}`\n\n"
            f"⚠️ **Action:** Niche 'Open Channel' par click karein aur bot ko add karke 'Post Messages' ki permission dein."
        )
        
        btn = [[InlineKeyboardButton("📢 Open Channel", url=ch_link)]]
        btn.append([InlineKeyboardButton("🔙 Back to List", callback_data="ref_ids_back")])
        return await status_msg.edit(text, reply_markup=InlineKeyboardMarkup(btn))

    await status_msg.edit(f"🔄 **Strict ID Refresh Started...**\n🆔 Channel: `{channel_id}`\n_Calculating total files, please wait..._")
    
    updated_count = await run_refresh_for_channel(client, channel_id, status_msg=status_msg, context=None)
    
    if getattr(temp, "STOP_REFRESH", False):
        return # Paused message already sent by run_refresh_for_channel
        
    btn = [[InlineKeyboardButton("🔙 Back to Channels", callback_data="ref_ids_back")]]
    await status_msg.edit(
        f"✅ **Refresh Complete!**\n\n"
        f"📢 **Channel:** `{ch_name}`\n"
        f"📂 **Total IDs Updated:** `{updated_count}`",
        reply_markup=InlineKeyboardMarkup(btn)
    )

@Client.on_callback_query(filters.regex(r"^ref_all_ch$") & filters.user(ADMINS))
async def ref_ch_all(client, query):
    status_msg = query.message
    temp.STOP_REFRESH = False
    await status_msg.edit("🔄 **Initializing ALL Channels Refresh...**\n_Scanning MongoDB for connected channels..._")
    
    channels = await Media.data_col1.distinct("chat_id")
    if Media.has_db2: channels.extend(await Media.data_col2.distinct("chat_id"))
    if Media.has_db3: channels.extend(await Media.data_col3.distinct("chat_id"))
    
    valid_channels = list(set([c for c in channels if str(c).startswith("-100")]))
    total_channels = len(valid_channels)
    
    total_updated = 0
    failed_channels = []
    
    for i, ch in enumerate(valid_channels, 1):
        if getattr(temp, "STOP_REFRESH", False):
            break
            
        try:
            ch_int = int(ch) # 🔥 ID ko properly number banaya
            # Bot agar admin hoga tabhi get_chat chalega
            chat = await client.get_chat(ch_int)
            
            context = {
                "is_all": True,
                "current_ch": i,
                "total_chs": total_channels,
                "global_updated": total_updated
            }
            
            count = await run_refresh_for_channel(client, ch_int, status_msg=status_msg, context=context)
            total_updated += count
            
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 2)
            failed_channels.append(str(ch))
        except Exception:
            failed_channels.append(str(ch))
            
        await asyncio.sleep(1.5) 
        
    if getattr(temp, "STOP_REFRESH", False):
        return # UI already updated in the loop
        
    # Kitne channel successfully scan hue
    success_scanned = total_channels - len(failed_channels)
    
    msg_text = (
        f"✅ **ALL Channels Refresh Complete!**\n\n"
        f"📢 **Channels Scanned:** `{success_scanned}`\n"
        f"📂 **Total Final IDs Updated:** `{total_updated}`\n"
    )
    
    btn = []
    
    # 🔥 THE MASTER HACK: Skipped channels ke direct buttons
    if failed_channels:
        failed_str = "`, `".join(failed_channels[:5])
        if len(failed_channels) > 5: failed_str += "` ...aur bhi hain"
        msg_text += f"\n⚠️ **Skipped (Not Admin/Removed):**\n`{failed_str}`\n_(Niche diye gaye buttons se open karein)_"
        
        # Har ek failed channel ke liye button banayega
        for ch_id in failed_channels[:5]:
            short_id = str(ch_id).replace("-100", "")
            ch_link = f"https://t.me/c/{short_id}/1"
            btn.append([InlineKeyboardButton(f"📢 Open & Fix {ch_id}", url=ch_link)])
            
    btn.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="ref_ids_back")])
        
    await status_msg.edit(msg_text, reply_markup=InlineKeyboardMarkup(btn))

@Client.on_callback_query(filters.regex(r"^ref_ids_back$") & filters.user(ADMINS))
async def ref_ids_back(client, query):
    await query.answer("Fetching Channels...", show_alert=False)
    channels, reply_markup = await get_refresh_ui_components(client)
    await query.message.edit(
        "👇 **Select a channel to refresh its File IDs:**\n\n"
        "_Ye command aapke database ki files ko naye bot ki ID se sync karegi._",
        reply_markup=reply_markup
    )

@Client.on_callback_query(filters.regex(r"^stop_refresh#") & filters.user(ADMINS))
async def stop_refresh_handler(client, query):
    temp.STOP_REFRESH = True
    await query.answer("🛑 Stopping process and saving progress... Please wait 2 seconds.", show_alert=True)

# ==============================================================================
# 👑 ADMIN PREMIUM COMMANDS
# ==============================================================================

@Client.on_message(filters.command("addpremium") & filters.user(ADMINS))
async def add_premium_cmd(client, message):
    if len(message.command) != 3:
        return await message.reply("⚠️ **Sahi syntax:** `/addpremium [User_ID] [Days]`\n\nExample: `/addpremium 1729007340 365`")

    try:
        target_id = int(message.command[1])
        days = int(message.command[2])
    except ValueError:
        return await message.reply("❌ **Error:** User ID aur Days dono numbers hone chahiye.")

    duration_seconds = days * 86400
    current_time = time.time()

    # 1. Database mein user check karna
    user = await db.users.find_one({'id': target_id})
    
    if user:
        current_expiry = user.get('premium_expiry', 0)
        # Agar pehle se premium hai, toh usme aur din add kar do
        if current_expiry > current_time:
            new_expiry = current_expiry + duration_seconds
        else:
            new_expiry = current_time + duration_seconds
    else:
        # Agar naya user hai, toh DB me add karke premium do
        await db.add_user(target_id)
        new_expiry = current_time + duration_seconds

    # 2. Database Update karna
    await db.users.update_one(
        {'id': target_id},
        {'$set': {'premium_expiry': new_expiry}},
        upsert=True
    )

    # 3. Expiry Date ko readable format me banana
    expiry_date = datetime.datetime.fromtimestamp(new_expiry).strftime('%Y-%m-%d %H:%M:%S')

    # 4. Admin ko Success Message bhejna
    await message.reply(
        f"✅ **Premium Successfully Added!**\n\n"
        f"👤 **User ID:** `{target_id}`\n"
        f"⏳ **Added Days:** `{days} Days`\n"
        f"📅 **New Expiry:** `{expiry_date}`"
    )

    # 5. User ko PM bhejna
    try:
        await client.send_message(
            target_id,
            f"🎉 **Congratulations!** 🎉\n\n"
            f"Aapke account mein **{days} Days** ka Premium Access add kar diya gaya hai.\n"
            f"Ab aap bina kisi shortener ke direct files download kar sakte hain!\n\n"
            f"📅 **Expiry Date:** `{expiry_date}`"
        )
    except Exception as e:
        # Agar user ne bot start nahi kiya hai ya block kar diya hai
        await message.reply(f"⚠️ **Note:** User ka premium DB me add ho gaya hai, lekin user ne bot block kar rakha hai ya kabhi start nahi kiya isliye usko PM nahi gaya.\n*(Error: {e})*")

@Client.on_message(filters.command("removepremium") & filters.user(ADMINS))
async def remove_premium_cmd(client, message):
    if len(message.command) != 2:
        return await message.reply("⚠️ **Sahi syntax:** `/removepremium [User_ID]`\n\nExample: `/removepremium 1729007340`")

    try:
        target_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ **Error:** User ID number hona chahiye.")

    # Database me expiry 0 set karna
    await db.users.update_one(
        {'id': target_id},
        {'$set': {'premium_expiry': 0}}
    )

    await message.reply(f"✅ **Done!** User `{target_id}` ka premium successully hata diya gaya hai.")

    # User ko alert bhejna
    try:
        await client.send_message(
            target_id,
            "⚠️ **Premium Expired / Removed** ⚠️\n\nAapka premium access khatam ho gaya hai. Ab file download karne ke liye aapko wapas shortener links use karne honge."
        )
    except Exception:
        pass # Agar block kiya hoga toh ignore ho jayega

@Client.on_message(filters.command("checkpremium") & filters.user(ADMINS))
async def check_premium_cmd(client, message):
    if len(message.command) != 2:
        return await message.reply("⚠️ **Sahi syntax:** `/checkpremium [User_ID]`\n\nExample: `/checkpremium 1729007340`")

    try:
        target_id = int(message.command[1])
    except ValueError:
        return await message.reply("❌ **Error:** User ID number hona chahiye.")

    user = await db.users.find_one({'id': target_id})
    
    if not user:
        return await message.reply("❌ **Database Error:** Ye user database mein maujood nahi hai.")

    expiry = user.get('premium_expiry', 0)
    current_time = time.time()

    if expiry > current_time:
        # Agar premium hai toh exact date aur time nikalna
        expiry_date = datetime.datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M:%S')
        remaining_days = int((expiry - current_time) / 86400)
        
        await message.reply(
            f"🌟 **User Premium Status: ACTIVE** 🌟\n\n"
            f"👤 **User ID:** `{target_id}`\n"
            f"⏳ **Remaining:** `{remaining_days} Days`\n"
            f"📅 **Expiry Date:** `{expiry_date}`"
        )
    else:
        await message.reply(
            f"❌ **User Premium Status: INACTIVE** ❌\n\n"
            f"👤 **User ID:** `{target_id}`\n"
            f"ℹ️ Is user ke paas koi active premium nahi hai."
        )


# ==============================================================================
# 🌟 MULTI-STICKER SYSTEM (WITH UID & FID)
# ==============================================================================

@Client.on_message(filters.command("addsticker") & filters.group)
async def add_sticker_cmd(client, message):
    user_id = message.from_user.id
    
    # 1. Admin Check
    try:
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR] and user_id not in ADMINS:
            return await message.reply("❌ **Access Denied:** Ye command sirf Admins ke liye hai.")
    except:
        return

    # 2. Reply Check
    if not message.reply_to_message or not message.reply_to_message.sticker:
        return await message.reply("⚠️ **Sahi Tarika:** Group mein koi Sticker bhejiye, fir us par Reply karke `/addsticker` likhiye.")

    # 3. Save to Database using dict (fid and uid)
    sticker = message.reply_to_message.sticker
    sticker_data = {
        'fid': sticker.file_id,
        'uid': sticker.file_unique_id
    }
    
    group_data = await db.get_group_settings(message.chat.id)
    current_stickers = group_data.get('result_stickers', [])
    if not isinstance(current_stickers, list):
        current_stickers = []

    # Convert old string-based IDs to dicts to prevent crashes (Backward Compatibility)
    clean_stickers = []
    for s in current_stickers:
        if isinstance(s, str):
            clean_stickers.append({'fid': s, 'uid': s}) # Fallback
        else:
            clean_stickers.append(s)
    current_stickers = clean_stickers

    # Check if already exists using 'uid'
    if any(s['uid'] == sticker.file_unique_id for s in current_stickers):
        return await message.reply("⚠️ Ye sticker pehle se add hai.")

    # Max 5 stickers ki limit
    if len(current_stickers) >= 5:
        return await message.reply("⚠️ **Limit Reached!** Aap pehle se 5 stickers add kar chuke hain. Naye add karne ke liye pehle `/clearstickers` dabayein.")

    current_stickers.append(sticker_data)
    await db.update_group_settings(message.chat.id, {'result_stickers': current_stickers})
    await message.reply(f"✅ **Sticker Added! ({len(current_stickers)}/5)**\nAb bot in stickers ko badal-badal kar bhejega.")


@Client.on_message(filters.command("clearstickers") & filters.group)
async def clear_stickers_cmd(client, message):
    user_id = message.from_user.id
    
    # Admin Check
    try:
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR] and user_id not in ADMINS:
            return await message.reply("❌ **Access Denied!**")
    except:
        return

    # Clear Database
    await db.update_group_settings(message.chat.id, {'result_stickers': []})
    await message.reply("🗑️ **All Stickers Cleared!** Ab search results ke sath koi sticker nahi aayega. Aap chahein toh naye add kar sakte hain.")


@Client.on_message(filters.command("removesticker") & filters.group)
async def remove_specific_sticker_cmd(client, message):
    user_id = message.from_user.id
    
    # 1. Admin Check
    try:
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR] and user_id not in ADMINS:
            return await message.reply("❌ **Access Denied:** Ye command sirf Admins ke liye hai.")
    except:
        return

    # 2. Reply Check
    if not message.reply_to_message or not message.reply_to_message.sticker:
        return await message.reply("⚠️ **Sahi Tarika:** Jis sticker ko list se hatana hai, group mein us par Reply karke `/removesticker` likhiye.")

    # 3. Remove from Database using uid
    uid = message.reply_to_message.sticker.file_unique_id
    group_data = await db.get_group_settings(message.chat.id)
    
    current_stickers = group_data.get('result_stickers', [])
    if not isinstance(current_stickers, list):
        current_stickers = []

    # Convert old format if needed for safe filtering
    clean_stickers = []
    for s in current_stickers:
        if isinstance(s, str):
            clean_stickers.append({'fid': s, 'uid': s})
        else:
            clean_stickers.append(s)
    
    # Filter out the sticker with matching 'uid'
    new_list = [s for s in clean_stickers if s['uid'] != uid]

    # 4. Check & Remove Logic
    if len(new_list) < len(clean_stickers):
        await db.update_group_settings(message.chat.id, {'result_stickers': new_list})
        await message.reply(f"🗑️ **Sticker Removed!**\nAb ye sticker search results mein nahi aayega.\n(Bache hue stickers: {len(new_list)}/5)")
    else:
        await message.reply("⚠️ Ye sticker aapki bot ki list mein add hi nahi hai.")

# ==============================================================================
# 🚀 SUPER FAST START MENU BUTTONS (Features, Earn, Referral, Back)
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^features$"))
async def features_callback(client, query):
    await query.answer() 
    text = (
        "⚙️ **Bot Features:**\n\n"
        "✓ Auto Filter in Groups\n"
        "✓ Super Fast Search Engine\n"
        "✓ Multi-Database Architecture\n"
        "✓ Watch Online & Fast Download\n"
        "✓ Auto Post & Auto Mentions\n"
        "✓ Smart FSub & Verification"
    )
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data="start_back")]]
    try:
        if query.message.photo:
            await query.message.edit_media(InputMediaPhoto(START_IMG, caption=text), reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.delete()
            await client.send_photo(query.message.chat.id, photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass

@Client.on_callback_query(filters.regex(r"^earn$"))
async def earn_callback(client, query):
    await query.answer() 
    text = (
        "🚫 **Earn Money with Bot** 🚫\n\n"
        "Aap is bot ka use karke apne group ke traffic se paise kama sakte hain!\n\n"
        "1️⃣ Bot ko apne group me add karein.\n"
        "2️⃣ Bot ko Admin banayein.\n"
        "3️⃣ Mere PM me `/settings` type karein.\n"
        "4️⃣ Apna URL Shortener API set karein aur earning shuru karein!"
    )
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data="start_back")]]
    try:
        if query.message.photo:
            await query.message.edit_media(InputMediaPhoto(START_IMG, caption=text), reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.delete()
            await client.send_photo(query.message.chat.id, photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass

@Client.on_callback_query(filters.regex(r"^refer$"))
async def refer_callback(client, query):
    await query.answer() 
    await free_premium_page(client, query)

@Client.on_callback_query(filters.regex(r"^start_back$"))
async def start_back_callback(client, query):
    await query.answer() 
    text = f"Hello {query.from_user.mention} 👋,\nI am a Powerul Auto Filter Bot."
    buttons = [
        [InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜps ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')],
        [InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'), 
         InlineKeyboardButton('💎 Free Premium', callback_data='open_prem_menu')],
        [InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛʜ ʙᴏᴛ 🚫', callback_data='earn'), InlineKeyboardButton('🤝 ʀᴇꜰᴇʀʀᴀʟ 🤝', callback_data='refer')]
    ]
    try:
        if query.message.photo:
            await query.message.edit_media(InputMediaPhoto(START_IMG, caption=text), reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await query.message.delete()
            await client.send_photo(chat_id=query.message.chat.id, photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        pass
