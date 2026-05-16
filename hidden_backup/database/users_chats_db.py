import motor.motor_asyncio
import time
import datetime
from info import USER_DB_URI, DATABASE_NAME

# ✅ Simple Cache Dictionary for RAM Caching
SETTINGS_CACHE = {}

class UserChatDB:
    def __init__(self, uri, database_name):
        # ✅ Connection Pooling Optimization
        if "minPoolSize" not in uri:
            if "?" in uri:
                uri += "&minPoolSize=10&maxPoolSize=100"
            else:
                uri += "?minPoolSize=10&maxPoolSize=100"

        # Connects to the User Database Cluster
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.groups = self.db.groups
        self.banned = self.db.banned 
        self.fsub_pending = self.db.fsub_pending
        self.warnings = self.db.warnings 

    async def add_user(self, id):
        user = await self.users.find_one({'id': int(id)})
        if not user:
            await self.users.insert_one({'id': int(id)})

    # ==================================================================
    # 💎 REFERRAL & PREMIUM SYSTEM METHODS
    # ==================================================================

    async def get_user_data(self, user_id):
        return await self.users.find_one({'id': int(user_id)})

    async def update_referral_stats(self, referrer_id, points=10):
        await self.users.update_one(
            {'id': int(referrer_id)},
            {'$inc': {'referral_points': points}},
            upsert=True
        )

    async def get_referral_points(self, user_id):
        user = await self.users.find_one({'id': int(user_id)})
        return user.get('referral_points', 0) if user else 0

    async def claim_premium_reward(self, user_id, cost_points, duration_seconds):
        user = await self.users.find_one({'id': int(user_id)})
        current_points = user.get('referral_points', 0) if user else 0
        
        if current_points < cost_points:
            return False, 0
            
        current_time = time.time()
        
        current_expiry = user.get('premium_expiry', 0)
        if current_expiry > current_time:
            new_expiry = current_expiry + duration_seconds
        else:
            new_expiry = current_time + duration_seconds
            
        await self.users.update_one(
            {'id': int(user_id)},
            {
                '$set': {'premium_expiry': new_expiry},
                '$inc': {'referral_points': -cost_points}
            }
        )
        return True, new_expiry

    async def is_user_premium(self, user_id):
        user = await self.users.find_one({'id': int(user_id)})
        if not user: return False
        
        expiry = user.get('premium_expiry', 0)
        if expiry > time.time():
            return True
        return False
        
    async def get_premium_status(self, user_id):
        user = await self.users.find_one({'id': int(user_id)})
        if not user: return False, "No Subscription"
        
        expiry = user.get('premium_expiry', 0)
        if expiry > time.time():
            remaining = int(expiry - time.time())
            days = remaining // 86400
            return True, f"{days} Days remaining"
        return False, "Expired"

    # ==================================================================
    # 👑 MANUAL ADMIN PREMIUM SYSTEM
    # ==================================================================
    async def add_premium_time(self, user_id, duration_seconds):
        user = await self.users.find_one({'id': int(user_id)})
        current_time = time.time()
        current_expiry = user.get('premium_expiry', 0) if user else 0

        if current_expiry > current_time:
            new_expiry = current_expiry + duration_seconds
        else:
            new_expiry = current_time + duration_seconds

        await self.users.update_one(
            {'id': int(user_id)},
            {'$set': {'premium_expiry': new_expiry}},
            upsert=True
        )
        return new_expiry

    async def remove_premium(self, user_id):
        await self.users.update_one(
            {'id': int(user_id)},
            {'$set': {'premium_expiry': 0}}
        )

    # ==================================================================
    # ⚙️ GROUP MANAGEMENT
    # ==================================================================

    async def add_group(self, id, title):
        default_settings = {
            'id': int(id),
            'earning_method': 'shortlink', 
            'shortener_mode': 'dynamic',   
            'shorteners': {},              
            'fsub_channels': {},           
            'is_shortlink_active': True,
            'result_mode': 'hybrid',        
            'result_page_limit': 10,        
            'auto_reaction': False,         
            'auto_delete_time': 300,        
            'auto_delete_user_msg': False,  
            'delete_thanks_msg': True,      
            'welcome_enabled': True,       
            'welcome_mode': 'default',     
            'custom_welcome_text': None,   
            'custom_welcome_photo': None,  
            'antispam_enabled': False,      
            'antispam_action': 'mute',      
            'mute_duration': 600,           
            'automention_enabled': True,     
            'mention_interval': 300,         
            'last_mention_time': 0,          
            'pending_mentions': [],          
            'autopost_enabled': False,      
            'autopost_interval': 1800,      
            'last_autopost_time': 0,        
            'autopost_text': None,          
            'autopost_image': None,         
            'autopost_media_id': None,      
            'autopost_media_type': None,    
            'autopost_del_time': 60,       
            'autopost_buttons': {},         
            'admin_free_access': False,     
            'daily_stats_notify': True,     
            'stats': {},                    
            'caption_url': None,
            'caption_btn_text': None,
            'caption_btn_url': None,
            'howto_url': None,
            'group_link': None,
            'referral_enabled': True,       
            'referral_target': 5,           
            'referral_reward_time': 2592000, 
            'time_dynamic': 86400,
            'time_smart': 86400,
            'time_together': 604800,       
            'time_together_3': 86400,      
            'time_gap1': 300,
            'time_gap2': 300,
            # 🔥 NAYA: MOVIE UPDATE SETTINGS DEFAULTS 🔥
            'movie_update': {
                'is_active': True,
                'slots': {'1': None, '2': None, '3': None},
                'group_link': None,
                'footer': [] 
            }
        }
        
        await self.groups.update_one(
            {'id': int(id)}, 
            {
                '$setOnInsert': default_settings,
                '$set': {'title': title}
            }, 
            upsert=True
        )

    # --- ⚙️ GROUP SETTINGS HELPERS (WITH CACHING) ---
    
    async def get_group_settings(self, id):
        chat_id = int(id)
        
        if chat_id in SETTINGS_CACHE:
            return SETTINGS_CACHE[chat_id]
            
        settings = await self.groups.find_one({'id': chat_id})
        
        if settings:
            SETTINGS_CACHE[chat_id] = settings
            
        return settings

    async def update_group_settings(self, id, settings):
        chat_id = int(id)
        
        await self.groups.update_one({'id': chat_id}, {'$set': settings})
        
        if chat_id in SETTINGS_CACHE:
            SETTINGS_CACHE[chat_id].update(settings)
        else:
            SETTINGS_CACHE[chat_id] = await self.groups.find_one({'id': chat_id})

    # --- 📊 DAILY STATS HELPERS ---

    def get_today_date(self):
        return datetime.datetime.now().strftime("%Y-%m-%d")

    async def update_daily_stats(self, chat_id, field, count=1, domain=None):
        today = self.get_today_date()
        
        if domain:
            safe_domain = domain.replace('.', '_')
            key = f"stats.{today}.shorteners.{safe_domain}.{field}"
            await self.groups.update_one(
                {'id': int(chat_id)},
                {'$inc': {key: count}},
                upsert=True
            )
        else:
            key = f"stats.{today}.{field}"
            await self.groups.update_one(
                {'id': int(chat_id)},
                {'$inc': {key: count}},
                upsert=True
            )

    async def get_daily_stats(self, chat_id, date_str):
        group = await self.groups.find_one({'id': int(chat_id)})
        if group and 'stats' in group:
            return group['stats'].get(date_str, {})
        return {}

    async def get_all_groups_stats(self, date_str):
        cursor = self.groups.find({f"stats.{date_str}": {"$exists": True}})
        results = []
        async for group in cursor:
            stats = group['stats'][date_str]
            stats['title'] = group.get('title', 'Unknown')
            stats['id'] = group['id']
            results.append(stats)
        return results

    async def get_group_stats_by_date(self, chat_id, date_str):
        group = await self.groups.find_one({'id': int(chat_id)})
        if group and 'stats' in group:
            return group['stats'].get(date_str, None)
        return None

    # --- 📰 AUTO POST HELPERS ---

    async def set_autopost_button(self, chat_id, slot, text, url):
        key = f"autopost_buttons.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': {key: {'text': text, 'url': url}}}
        )
        if int(chat_id) in SETTINGS_CACHE:
             del SETTINGS_CACHE[int(chat_id)]


    async def remove_autopost_button(self, chat_id, slot):
        key = f"autopost_buttons.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {key: ""}}
        )
        if int(chat_id) in SETTINGS_CACHE: del SETTINGS_CACHE[int(chat_id)]

    async def reset_autopost_content(self, chat_id):
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': {
                'autopost_text': None, 
                'autopost_image': None, 
                'autopost_media_id': None,    
                'autopost_media_type': None,  
                'autopost_buttons': {}
            }}
        )
        if int(chat_id) in SETTINGS_CACHE: del SETTINGS_CACHE[int(chat_id)]

    # --- 📣 AUTO MENTION HELPERS ---

    async def add_pending_mention(self, chat_id, user_id):
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$addToSet': {'pending_mentions': int(user_id)}}
        )

    async def get_pending_mentions(self, chat_id):
        group = await self.groups.find_one({'id': int(chat_id)})
        return group.get('pending_mentions', []) if group else []

    async def remove_pending_mentions(self, chat_id, user_ids):
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$pull': {'pending_mentions': {'$in': user_ids}}}
        )
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': {'last_mention_time': time.time()}}
        )

    # --- 🛡️ ANTI-SPAM WARNING MANAGEMENT ---

    async def get_spam_warnings(self, chat_id, user_id):
        doc = await self.warnings.find_one({"chat_id": int(chat_id), "user_id": int(user_id)})
        return doc['count'] if doc else 0

    async def add_spam_warning(self, chat_id, user_id):
        await self.warnings.update_one(
            {"chat_id": int(chat_id), "user_id": int(user_id)},
            {"$inc": {"count": 1}},
            upsert=True
        )
        return await self.get_spam_warnings(chat_id, user_id)

    async def reset_spam_warnings(self, chat_id, user_id):
        await self.warnings.delete_one({"chat_id": int(chat_id), "user_id": int(user_id)})

    # --- SHORTENER MANAGEMENT ---
    async def add_shortener(self, chat_id, slot, site, api):
        key = f"shorteners.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': {key: {'site': site, 'api': api}}}
        )
        if int(chat_id) in SETTINGS_CACHE: del SETTINGS_CACHE[int(chat_id)]

    async def remove_shortener(self, chat_id, slot):
        key = f"shorteners.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {key: ""}}
        )
        if int(chat_id) in SETTINGS_CACHE: del SETTINGS_CACHE[int(chat_id)]

    # --- 🔒 FSUB CHANNEL MANAGEMENT ---
    
    async def update_fsub_channel(self, chat_id, slot, channel_id):
        try:
            group = await self.groups.find_one({'id': int(chat_id)})
            if group:
                raw_data = group.get('fsub_channels')
                if isinstance(raw_data, list):
                    await self.groups.update_one(
                        {'id': int(chat_id)}, 
                        {'$set': {'fsub_channels': {}}}
                    )
        except Exception as e:
            pass

        val_to_save = channel_id
        if slot != '5':
            try: val_to_save = int(channel_id)
            except: pass

        key = f"fsub_channels.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': {key: val_to_save}},
            upsert=True
        )
        if int(chat_id) in SETTINGS_CACHE: del SETTINGS_CACHE[int(chat_id)]

    async def remove_fsub_channel(self, chat_id, slot):
        key = f"fsub_channels.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {key: ""}}
        )
        if int(chat_id) in SETTINGS_CACHE: del SETTINGS_CACHE[int(chat_id)]

    async def remove_all_fsub_channels(self, chat_id):
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {'fsub_channels': ""}} 
        )
        if int(chat_id) in SETTINGS_CACHE: del SETTINGS_CACHE[int(chat_id)]

    # --- 📊 STATS & BAN LOGIC ---

    async def total_users_count(self):
        return await self.users.count_documents({})

    async def total_groups_count(self):
        return await self.groups.count_documents({})

    async def get_banned(self):
        users = []
        chats = []
        async for banned_user in self.banned.find({"type": "user"}):
            users.append(banned_user["id"])
        async for banned_chat in self.banned.find({"type": "chat"}):
            chats.append(banned_chat["id"])
        return users, chats

    async def add_ban(self, id, type="user"):
        is_exist = await self.banned.find_one({"id": int(id), "type": type})
        if not is_exist:
            await self.banned.insert_one({"id": int(id), "type": type})

    async def remove_ban(self, id, type="user"):
        await self.banned.delete_one({"id": int(id), "type": type})

    # --- 🔒 ADVANCED VERIFICATION SYSTEM ---
    
    async def get_verify_status(self, user_id, chat_id):
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})
            if isinstance(all_verifications, (int, float)): return False

            chat_data = all_verifications.get(str(chat_id), {})
            if isinstance(chat_data, (int, float)): return False

            return chat_data.get('0', 0) > time.time()
            
        return False

    async def get_level_time(self, user_id, chat_id, level):
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})
            if isinstance(all_verifications, (int, float)): return 0
            
            chat_data = all_verifications.get(str(chat_id), {})
            if isinstance(chat_data, (int, float)): return 0
            
            return chat_data.get(str(level), 0)
        return 0

    async def update_verify_status(self, user_id, chat_id, level, duration=0, is_reset=False):
        current_time = time.time()
        
        if is_reset:
            value = 0 
        elif duration > 0:
            value = current_time + duration 
        else:
            value = current_time 

        user = await self.users.find_one({'id': int(user_id)})
        if user:
            current_status = user.get('verify_status')
            if isinstance(current_status, (int, float)):
                await self.users.update_one({'id': int(user_id)}, {'$set': {'verify_status': {}}})
            elif isinstance(current_status, dict):
                chat_status = current_status.get(str(chat_id))
                if isinstance(chat_status, (int, float)):
                    await self.users.update_one({'id': int(user_id)}, {'$set': {f'verify_status.{str(chat_id)}': {}}})

        key_name = f"verify_status.{str(chat_id)}.{str(level)}"
        await self.users.update_one(
            {'id': int(user_id)},
            {'$set': {key_name: value}},
            upsert=True
        )

    # --- 🔥 ADVANCED FSUB PENDING LOGIC ---
    
    async def add_pending_request(self, user_id, channel_id):
        try:
            await self.fsub_pending.update_one(
                {'_id': f"{user_id}_{channel_id}"},
                {'$set': {
                    'user_id': int(user_id), 
                    'chat_id': int(channel_id),
                    'date': time.time()
                }},
                upsert=True
            )
        except Exception as e:
            print(f"Error adding pending request: {e}")

    async def remove_pending_request(self, user_id, channel_id):
        try:
            await self.fsub_pending.delete_one({'_id': f"{user_id}_{channel_id}"})
        except Exception as e:
            print(f"Error removing pending request: {e}")

    async def is_user_pending(self, user_id, channel_id):
        try:
            found = await self.fsub_pending.find_one({'_id': f"{user_id}_{channel_id}"})
            return bool(found)
        except:
            return False

    # ✅ REQUIRED FOR "RESET SETTINGS" FEATURE
    async def reset_group_settings(self, chat_id):
        default_settings = {
            'earning_method': 'shortlink', 
            'shortener_mode': 'dynamic',   
            'shorteners': {},              
            'fsub_channels': {},           
            'is_shortlink_active': True,
            'result_mode': 'button',
            'result_page_limit': 10,
            'auto_reaction': False,
            'auto_delete_time': 300,
            'auto_delete_user_msg': False,
            'delete_thanks_msg': True,
            'welcome_enabled': True,
            'welcome_mode': 'default',
            'custom_welcome_text': None,
            'custom_welcome_photo': None,
            'antispam_enabled': False,
            'antispam_action': 'mute',
            'mute_duration': 600,
            'automention_enabled': True,
            'mention_interval': 300,
            'pending_mentions': [],
            'autopost_enabled': False,
            'autopost_interval': 1800,
            'autopost_text': None,
            'autopost_image': None,
            'autopost_media_id': None,     
            'autopost_media_type': None,   
            'autopost_del_time': 60,      
            'autopost_buttons': {},
            'admin_free_access': False,
            'daily_stats_notify': True,
            'caption_url': None,
            'caption_btn_text': None,
            'caption_btn_url': None,
            'howto_url': None,
            'group_link': None,
            'referral_enabled': True,       
            'referral_target': 5,           
            'referral_reward_time': 2592000,
            # 🔥 NAYA: MOVIE UPDATE DEFAULTS 🔥
            'movie_update': {
                'is_active': True,
                'slots': {'1': None, '2': None, '3': None},
                'group_link': None,
                'footer': [] 
            }
        }
        
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': default_settings}
        )
        if int(chat_id) in SETTINGS_CACHE:
            del SETTINGS_CACHE[int(chat_id)]

# ✅ INITIALIZATION
db = UserChatDB(USER_DB_URI, DATABASE_NAME)
