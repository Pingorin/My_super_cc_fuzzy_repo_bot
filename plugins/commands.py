import logging
import time
import re
import datetime
import asyncio 
import urllib.parse
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import UserNotParticipant
from database.users_chats_db import db
from database.ia_filterdb import Media
import info 
from info import ADMINS, IS_VERIFY
from utils import temp, get_shortlink, check_fsub_4_status
from Script import script 

logger = logging.getLogger(__name__)
START_IMG = "https://graph.org/file/4d61886e61dfa37a25945.jpg"

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
        # Button jo wapas same file mangwayega
        btn = [[InlineKeyboardButton("✅ ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ ✅", url=f"https://t.me/{temp.U_NAME}?start={command_data}")]]
        await warning_msg.edit_text(
            "<b>✅ ʏᴏᴜʀ ᴍᴇssᴀɢᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ɪғ ʏᴏᴜ ᴡᴀɴᴛ ᴀɢᴀɪɴ ᴛʜᴇɴ ᴄʟɪᴄᴋ ᴏɴ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ</b>",
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

        msg = (
            f"⚠️ **Shortener Alert** ⚠️\n\n"
            f"Group: **{group_name}** (`{group_id}`).\n"
            f"Shortener: **{site_domain}** failed or is slow.\n"
            f"**Action:** Check API Key or Website Status."
        )
        for admin_id in ADMINS:
            try: await client.send_message(chat_id=int(admin_id), text=msg)
            except: pass
    except: pass

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

    # 💎 PREMIUM CHECK
    is_premium = await db.is_user_premium(user_id)
    if is_premium:
        return True 

    # 👑 ADMIN FREE ACCESS CHECK
    try:
        group_settings = await db.get_group_settings(chat_id)
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
        await db.add_group(message.chat.id, message.chat.title)
        if len(message.command) == 1: return await message.reply("✅ Bot is Alive!")
        return 

    if message.chat.type == enums.ChatType.PRIVATE:
        user_id = message.from_user.id
        
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

            text = (
                "💰 **Get Free Premium Access!**\n\n"
                "Share the link below with a new user. If they start the bot through your link, you will get **10 referral points**.\n\n"
                f"**Reward:** {target * 10} Points = {reward_desc} Premium Access\n\n"
                "You can claim your points for direct file access with no shorteners!\n\n"
                f"`{ref_link}`"
            )
            
            buttons = [
                [InlineKeyboardButton("📤 Click to Share", url=share_url)],
                [InlineKeyboardButton("🎁 Claim Points", callback_data="claim_points"),
                 InlineKeyboardButton("❌ Close", callback_data="close_data")]
            ]
            await message.reply(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
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
            filesarr = [] # Sent messages ko save karne ke liye list
            
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
                    
                    # ✅ Streaming Buttons (Sirf Buttons, No Link in Text)
                    try:
                        bin_msg = await client.send_cached_media(chat_id=info.BIN_CHANNEL, file_id=file_details['file_id'])
                        base_url = info.SITE_URL.rstrip('/') if info.SITE_URL else "http://127.0.0.1:8080"
                        
                        watch_url = f"{base_url}/watch/{bin_msg.id}"
                        dl_url = f"{base_url}/{bin_msg.id}"
                        
                        btn_rows.append([
                            InlineKeyboardButton("🍿 Watch Online", url=watch_url),
                            InlineKeyboardButton("⚡ Fast Download", url=dl_url)
                        ])
                    except Exception as e:
                        print(f"Streaming Button Error: {e}")
                    
                    reply_markup = InlineKeyboardMarkup(btn_rows) if btn_rows else None

                    # File send aur save karna
                    sent_media = await client.send_cached_media(
                        chat_id=message.from_user.id,
                        file_id=file_details['file_id'],
                        caption=final_caption,
                        reply_markup=reply_markup,
                        parse_mode=enums.ParseMode.HTML
                    )
                    filesarr.append(sent_media)
                    
                    sent_count += 1
                    await asyncio.sleep(0.8) 
                    
                except Exception as e:
                    print(f"Send All Error: {e}")
                    continue
            
            await msg.delete()
            
            # End me sirf 1 warning message bhejenge (Send All ke case me)
            warning_msg = await message.reply(
                "⚠️ **DHYAN DEIN:**\n\nYe saari files theek **1 minute** baad yahan se automatically delete ho jayengi. Kripya isko jaldi se apne Saved Messages me forward kar lein!"
            )
            # Auto delete task start (Batch mode)
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
            src_chat_id = data[2] if len(data) > 2 else str(message.chat.id)
            
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
            search_data = await Media.search_col.find_one({'link_id': link_id})
            
            if not file_data: return await message.reply("❌ **File Not Found.**")
            
            file_name = search_data.get('file_name', 'Unknown File')
            raw_caption = search_data.get('caption')

            if not raw_caption:
                caption = f"{file_name}"
            else:
                caption = str(raw_caption)
                caption = re.sub(r"(https?://)?(t|telegram)[\.\s]?(me|dog)/[^\s]+", "", caption, flags=re.IGNORECASE)
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

            btn_rows.append([InlineKeyboardButton("💎 Free Premium", url=f"https://t.me/{temp.U_NAME}?start=free_premium_info")])

            # ✅ Streaming Buttons - No links in caption text
            try:
                bin_msg = await client.send_cached_media(chat_id=info.BIN_CHANNEL, file_id=file_data.get('file_id'))
                base_url = info.SITE_URL.rstrip('/') if info.SITE_URL else "http://127.0.0.1:8080"
                
                watch_url = f"{base_url}/watch/{bin_msg.id}"
                dl_url = f"{base_url}/{bin_msg.id}"
                
                btn_rows.append([
                    InlineKeyboardButton("🍿 Watch Online", url=watch_url),
                    InlineKeyboardButton("⚡ Fast Download", url=dl_url)
                ])
            except Exception as e:
                print(f"Streaming Button Error: {e}")

            if btn_rows:
                reply_markup = InlineKeyboardMarkup(btn_rows)

            try: 
                # File Send and save
                sent_media = await client.send_cached_media(
                    chat_id=message.from_user.id, 
                    file_id=file_data.get('file_id'), 
                    caption=final_caption, 
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML
                )
                
                # File ko reply karke warning message bhejna
                warning_msg = await sent_media.reply_text(
                    "⚠️ **DHYAN DEIN:**\n\nYe file theek **1 minute** baad yahan se automatically delete ho jayegi. Kripya isko jaldi se apne Saved Messages me forward kar lein!",
                    quote=True
                )
                
                # Auto delete task start (Single mode)
                asyncio.create_task(auto_delete_single(sent_media, warning_msg, message.command[1]))
                
            except Exception as e: 
                await message.reply(f"❌ Error sending file: `{e}`")
                
        except Exception as e: await message.reply(f"❌ Error: {e}")
        return

    # --- PRIVATE START MESSAGE UI (SETTINGS REDIRECT HANDLER ADDED) ---
    if message.chat.type == enums.ChatType.PRIVATE:
        # If user was redirected from group to use /settings
        if len(message.command) > 1 and message.command[1] == "settings":
            from plugins.settings_ui import settings_command
            return await settings_command(client, message)
            
        text = f"Hello {message.from_user.mention} 👋,\nI am a Powerul Auto Filter Bot."
        buttons = [
            [InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')],
            [InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'), 
             InlineKeyboardButton('💎 Free Premium', callback_data='open_prem_menu')],
            [InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛʜ ʙᴏᴛ 🚫', callback_data='earn'), InlineKeyboardButton('🤝 ʀᴇꜰᴇʀʀᴀʟ 🤝', callback_data='refer')]
        ]
        await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command("connect") & filters.group)
async def connect_handler(client, message):
    try:
        user_id = message.from_user.id
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]: 
            return await message.reply("❌ **Admin Only.** You cannot use this.")
        
        # Connect karte time Admins ko DB me save kar lo
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

@Client.on_message(filters.command("stats") & filters.user(ADMINS))
async def stats_handler(client, message):
    try:
        msg = await message.reply("Fetching stats...")
        users = await db.total_users_count()
        groups = await db.total_groups_count()
        files = await Media.total_files_count()
        await msg.edit(f"📊 **BOT STATISTICS**\n\n👤 **Users:** {users}\n👥 **Groups:** {groups}\n📂 **Files Indexed:** {files}")
    except Exception as e: 
        await message.reply(f"Error: {e}")

# ==============================================================================
# 💎 PREMIUM & REFERRAL UI CALLBACKS
# ==============================================================================

@Client.on_callback_query(filters.regex(r"^open_prem_menu"))
async def premium_main_menu(client, query):
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
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex(r"^free_prem_page"))
async def free_premium_page(client, query):
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
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

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
            await query.message.edit_text(
                f"🎉 **Congratulations!**\n\n"
                f"You have claimed **Premium Access**.\n"
                f"✅ No Shorteners\n"
                f"✅ Direct Files\n\n"
                f"📅 **Expiry:** {exp_date}",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="free_prem_page")]])
            )
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
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="free_prem_page")]]))

@Client.on_callback_query(filters.regex(r"^check_prem_status"))
async def check_status_handler(client, query):
    user_id = query.from_user.id
    is_prem, msg = await db.get_premium_status(user_id)
    
    status_icon = "✅ Active" if is_prem else "❌ Inactive"
    
    text = (
        f"📊 **Premium Status**\n\n"
        f"**Status:** {status_icon}\n"
        f"**Validity:** {msg}"
    )
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="free_prem_page")]]))

@Client.on_callback_query(filters.regex(r"^close_data"))
async def close_data(client, query):
    await query.message.delete()

# ==============================================================================
# 🕵️ ADMIN COMMAND: ALL GROUPS LIST (/other_group)
# ==============================================================================

# 🛑 YAHAN APNI TELEGRAM ID DAALEIN (Bina quotes ke, sirf number)
SUDO_ADMIN_ID = 7245547751 # <--- Isko apni ID se replace karein

async def show_groups_page(client, request_obj, page):
    all_groups = []
    
    # Ji haan, ye seedha MONGODB se saare groups nikal raha hai
    async for group in db.groups.find({}):
        title = group.get('title', 'Unknown Group')
        chat_id = group.get('id')
        if chat_id:
            all_groups.append((title, chat_id))

    if not all_groups:
        text = "❌ **Database me koi group nahi mila.**"
        if hasattr(request_obj, "edit_text"):
            return await request_obj.edit_text(text)
        else:
            return await request_obj.reply(text)

    LIMIT = 10  # Ek page par 10 groups
    total_groups = len(all_groups)
    max_pages = (total_groups + LIMIT - 1) // LIMIT
    
    if page >= max_pages: page = max_pages - 1
    if page < 0: page = 0
    
    start = page * LIMIT
    end = start + LIMIT
    current_groups = all_groups[start:end]
    
    buttons = []
    # Har group ke liye ek button banana
    for title, chat_id in current_groups:
        short_title = title[:30] + "..." if len(title) > 30 else title
        buttons.append([InlineKeyboardButton(f"📂 {short_title}", callback_data=f"get_grp_link#{chat_id}#{page}")])
        
    # Pagination Row
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
    
    if hasattr(request_obj, "edit_text"):
        await request_obj.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await request_obj.reply(text, reply_markup=InlineKeyboardMarkup(buttons))


# 1️⃣ THE MAIN COMMAND (group=-2 Lagaya hai taaki sabse pehle ye chale)
@Client.on_message(filters.command("other_group") & filters.private, group=-2)
async def other_group_command(client, message):
    user_id = message.from_user.id
    
    # ID Verification via Direct Variable or info.py ADMINS
    if user_id != SUDO_ADMIN_ID and user_id not in ADMINS:
        return await message.reply("❌ **Access Denied:** Ye command sirf Bot Owner ke liye hai.")
        
    # Command trigger hote hi ek loading message dega (Taaki aapko pata chale command chal rahi hai)
    wait_msg = await message.reply("🔄 **Database se groups nikal raha hu...**")
    
    await show_groups_page(client, wait_msg, 0)


# 2️⃣ PAGINATION CALLBACK
@Client.on_callback_query(filters.regex(r"^admin_grp_page#"))
async def admin_grp_page_handler(client, query):
    if query.from_user.id != SUDO_ADMIN_ID and query.from_user.id not in ADMINS:
        return await query.answer("❌ Not Allowed", show_alert=True)
        
    page = int(query.data.split("#")[1])
    await show_groups_page(client, query, page)


# 3️⃣ GENERATE LINK ON CLICK
@Client.on_callback_query(filters.regex(r"^get_grp_link#"))
async def get_grp_link_handler(client, query):
    if query.from_user.id != SUDO_ADMIN_ID and query.from_user.id not in ADMINS:
        return await query.answer("❌ Not Allowed", show_alert=True)
        
    data = query.data.split("#")
    chat_id = int(data[1])
    page = int(data[2])
    
    await query.answer("Fetching Invite Link... ⏳", show_alert=False)
    
    try:
        chat = await client.get_chat(chat_id)
        
        # Link nikalna (Agar pehle se link hai toh wo use karo, nahi toh naya banao)
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
