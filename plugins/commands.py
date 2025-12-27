import logging
import time
import re
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

# --- 🛠️ HELPER FUNCTIONS ---

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

# --- 🔐 VERIFICATION LOGIC ---

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
    if await db.get_verify_status(user_id, chat_id): return True 

    group_settings = await db.get_group_settings(chat_id)
    mode = group_settings.get('shortener_mode', 'dynamic') if group_settings else 'dynamic'
    active_slots = await get_active_shorteners(chat_id)
    current_time = time.time()

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
    return short_url

async def attempt_send_link(client, user_id, chat_id, link_id, message_obj, level, slot_data):
    site = slot_data['site']
    api = slot_data['api']
    verify_url = f"https://t.me/{temp.U_NAME}?start=verify_{level}_{user_id}_{chat_id}_{link_id}"
    wait_msg = await message_obj.reply_text(f"Generating Verification Link {level}... ⏳")
    short_url = await get_shortlink(site, api, verify_url)
    await wait_msg.delete()
    
    if short_url:
        btn = [[InlineKeyboardButton(f"🚀 Verify Level {level}", url=short_url)]]
        text = f"⚠️ **Verification Required ({level}/?)**\n\n**Shortener:** {site}\n_Click the button below to verify and continue._"
        if level == 3: text = f"⚠️ **Final Step (3/3)**\n\n**Shortener:** {site}\n_Almost there! Verify this to unlock files._"
        await message_obj.reply_text(text, reply_markup=InlineKeyboardMarkup(btn))
        return "SENT"
    else:
        await send_shortener_alert(client, chat_id, site)
        await message_obj.reply_text(f"⚠️ **Alert:** Shortener {site} is down. Skipping Level {level}... ⏩")
        return "SKIP"

# --- 🔥 PRE-VERIFY FSUB CHECK (Slots 1, 2, 3) ---

async def check_fsub(client, user_id, message_obj):
    src_chat_id = None
    if len(message_obj.command) > 1:
        try:
            parts = message_obj.command[1].split("_")
            if len(parts) > 3: src_chat_id = int(parts[3]) 
            elif len(parts) > 2 and parts[0] == "get": src_chat_id = int(parts[2])
        except: pass
    
    if not src_chat_id: return True 

    group_settings = await db.get_group_settings(src_chat_id)
    if not group_settings: return True
    
    fsub_channels = group_settings.get('fsub_channels')
    if not isinstance(fsub_channels, dict): return True 

    btn_row_1 = [] # For Slot 1 & Slot 2
    btn_row_2 = [] # For Slot 3

    for slot in ['1', '2', '3']:
        channel_id = fsub_channels.get(slot)
        if not channel_id: continue 
        try: channel_id = int(channel_id)
        except: continue
        
        # 🛠️ RESTART FIX: Force Refresh
        # This prevents "Invalid ID" error after bot restarts
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

        # Slot 3 (Normal Join)
        if slot == '3':
            try:
                invite = await client.create_chat_invite_link(channel_id)
                btn_row_2.append(InlineKeyboardButton(f"📢 Join Channel {slot}", url=invite.invite_link))
            except: pass
        # Slot 1 & 2 (Force Request)
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

# --- 🎮 COMMAND HANDLERS ---

@Client.on_message(filters.command("start") & filters.incoming)
async def start_handler(client, message):
    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await db.add_group(message.chat.id, message.chat.title)
        if len(message.command) == 1: return await message.reply("✅ Bot is Alive!")
        return 

    if message.chat.type == enums.ChatType.PRIVATE:
        await db.add_user(message.from_user.id)
        # Normal FSub Check (if not verification/get flow)
        if len(message.command) > 1 and not (message.command[1].startswith("verify_") or message.command[1].startswith("get_")):
             if not await check_fsub(client, message.from_user.id, message): return

    # -------------------------------------------------------------------------
    # 🔁 VERIFICATION RETURN LOGIC
    # -------------------------------------------------------------------------
    if len(message.command) > 1 and message.command[1].startswith("verify_"):
        try:
            data = message.command[1].split("_")
            level = int(data[1])
            verify_chatid = data[3]
            link_id = int(data[4]) if len(data) > 4 else 0
            
            await db.update_verify_status(message.from_user.id, verify_chatid, level)
            
            if await check_verification(client, message.from_user.id, verify_chatid, link_id, message):
                btn = [[InlineKeyboardButton("📂 Get Your File Now", url=f"https://t.me/{temp.U_NAME}?start=get_{link_id}_{verify_chatid}")]]
                await message.reply(f"✅ **Verification Successful!**\n\nAb niche button par click karke file lein.", reply_markup=InlineKeyboardMarkup(btn))
            return
        except Exception as e: return await message.reply(f"❌ Error: {e}")

    # -------------------------------------------------------------------------
    # 🔥 MAIN FLOW (get_linkid_chatid)
    # -------------------------------------------------------------------------
    if len(message.command) > 1 and message.command[1].startswith("get_"):
        try:
            data = message.command[1].split("_")
            link_id = int(data[1])
            src_chat_id = data[2] if len(data) > 2 else str(message.chat.id)
            
            # 1. Pre-Verify Slots (1,2,3)
            if not await check_fsub(client, message.from_user.id, message): return 

            # 2. Shortener Verification
            if not await check_verification(client, message.from_user.id, src_chat_id, link_id, message): return 

            # ==================================================================
            # 🛑 STEP 3: SLOT 4 (Request) & SLOT 5 (Normal/Link) - POST VERIFY
            # ==================================================================
            
            group_settings = await db.get_group_settings(src_chat_id)
            fsub = group_settings.get('fsub_channels', {}) if group_settings else {}
            
            id_4 = fsub.get('4')
            id_5 = fsub.get('5')
            
            post_verify_buttons = []

            # --- CHECK SLOT 4 (Request Mode) ---
            if id_4:
                try:
                    id_4 = int(id_4)
                    # 🛠️ RESTART FIX: Force Refresh
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

            # --- CHECK SLOT 5 (Hybrid: ID or Link) ---
            if id_5:
                is_joined_5 = False
                slot5_btn_url = None
                
                # Check: Is it ID (digits) or Link (string)?
                str_id_5 = str(id_5)
                if isinstance(id_5, int) or str_id_5.lstrip('-').isdigit():
                    # CASE A: Real ID (Verification Active)
                    try:
                        cid5 = int(id_5)
                        # 🛠️ RESTART FIX: Force Refresh
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
                    # CASE B: Custom Link (Verification OFF - Show Button Only)
                    is_joined_5 = False 
                    slot5_btn_url = str_id_5

                if not is_joined_5 and slot5_btn_url:
                    post_verify_buttons.append(InlineKeyboardButton("📢 Join Final (Slot 5)", url=slot5_btn_url))

            # --- DISPLAY & BLOCK IF BUTTONS EXIST ---
            if post_verify_buttons:
                wrapper = []
                # Side-by-side if 2 exist, else Stacked
                if len(post_verify_buttons) == 2: wrapper.append(post_verify_buttons)
                else: wrapper.append([post_verify_buttons[0]])
                
                # Footer
                wrapper.append([InlineKeyboardButton("✅ I Have Joined - Get File", url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}")])
                
                await message.reply_text(
                    text="🛑 **Almost There!**\n\nPlease join the Final Channels below to get your file.",
                    reply_markup=InlineKeyboardMarkup(wrapper)
                )
                return # ⛔ STOP

            # ==================================================================
            # ✅ STEP 4: SEND FILE + CLEAN CAPTION
            # ==================================================================

            file_data = await Media.get_file_details(link_id)
            search_data = await Media.search_col.find_one({'link_id': link_id})
            
            if not file_data: return await message.reply("❌ **File Not Found.**")
            
            # Original Caption
            caption = search_data.get('caption', f"📂 <b>{search_data.get('file_name')}</b>")
            
            # 🧹🧹 CAPTION CLEANING LOGIC 🧹🧹
            
            # 1. Remove "https://t.me/..." or "https://t me/..."
            caption = re.sub(r"(https?://)?(t|telegram)[\.\s]?(me|dog)/[^\s]+", "", caption, flags=re.IGNORECASE)
            
            # 2. Remove other HTTP links
            caption = re.sub(r"https?://[^\s]+", "", caption, flags=re.IGNORECASE)
            
            # 3. Remove Spam Text (Join Now, Aa Jao, Arrows, Emojis)
            remove_patterns = [
                r"Join\s?(Now|Channel|Us|Here)", 
                r"Aa\s?Jao", 
                r"🤞", r"➜", r"\)⁠➜", r"👉", 
                r"\[@\w+\]", r"@\w+"
            ]
            
            for pattern in remove_patterns:
                caption = re.sub(pattern, "", caption, flags=re.IGNORECASE)

            # 4. Final Trim
            caption = re.sub(r"\s+", " ", caption).strip()

            try: 
                await client.send_cached_media(
                    chat_id=message.from_user.id, 
                    file_id=file_data.get('file_id'), 
                    caption=f"{caption}\n\n{script.CUSTOM_FOOTER}", 
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e: await message.reply(f"❌ Error sending file: `{e}`")
                
        except Exception as e: await message.reply(f"❌ Error: {e}")
        return

    if message.chat.type == enums.ChatType.PRIVATE:
        text = f"Hello {message.from_user.mention} 👋,\nI am a Powerul Auto Filter Bot."
        buttons = [
            [InlineKeyboardButton('⇆ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘs ⇆', url=f'http://t.me/{temp.U_NAME}?startgroup=start')],
            [InlineKeyboardButton('⚙ ꜰᴇᴀᴛᴜʀᴇs', callback_data='features'), InlineKeyboardButton('💸 ᴘʀᴇᴍɪᴜᴍ', callback_data='buy_premium')],
            [InlineKeyboardButton('🚫 ᴇᴀʀɴ ᴍᴏɴᴇʏ ᴡɪᴛʜ ʙᴏᴛ 🚫', callback_data='earn'), InlineKeyboardButton('🤝 ʀᴇꜰᴇʀʀᴀʟ 🤝', callback_data='refer')]
        ]
        await message.reply_photo(photo=START_IMG, caption=text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_message(filters.command("connect") & filters.group)
async def connect_handler(client, message):
    try:
        user_id = message.from_user.id
        member = await client.get_chat_member(message.chat.id, user_id)
        if member.status not in [enums.ChatMemberStatus.OWNER, enums.ChatMemberStatus.ADMINISTRATOR]: return await message.reply("❌ **Admin Only.** You cannot use this.")
        
        await db.add_group(message.chat.id, message.chat.title)
        
        await message.reply_text(f"✅ **Successfully Connected!**\nGroup: `{message.chat.title}`\nID: `{message.chat.id}` saved.")
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
