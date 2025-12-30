import motor.motor_asyncio
import time
from info import USER_DB_URI, DATABASE_NAME

class UserChatDB:
    def __init__(self, uri, database_name):
        # Connects to the User Database Cluster
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.groups = self.db.groups
        self.banned = self.db.banned 
        # ✅ Yeh collection pending Join Requests store karega
        self.fsub_pending = self.db.fsub_pending
        # ✅ Yeh collection warnings store karega (Anti-Spam)
        self.warnings = self.db.warnings 

    async def add_user(self, id):
        user = await self.users.find_one({'id': int(id)})
        if not user:
            await self.users.insert_one({'id': int(id)})

    # ✅ MODIFIED: Added Defaults for ALL New Features (Auto Post, Mention, Anti-Spam, etc.)
    async def add_group(self, id, title):
        group = await self.groups.find_one({'id': int(id)})
        
        if not group:
            default_settings = {
                'id': int(id),
                'title': title,
                'earning_method': 'shortlink', 
                'shortener_mode': 'dynamic',   
                'shorteners': {},              
                'fsub_channels': {},           
                'is_shortlink_active': True,
                
                # Search Settings
                'result_mode': 'hybrid',        # Default: hybrid
                'result_page_limit': 10,        
                
                # Auto-Delete & Reaction Defaults
                'auto_reaction': False,         
                'auto_delete_time': 300,        
                'auto_delete_user_msg': False,  
                'delete_thanks_msg': True,      

                # Welcome Settings Defaults
                'welcome_enabled': True,       
                'welcome_mode': 'default',     
                'custom_welcome_text': None,   
                'custom_welcome_photo': None,  

                # Anti-Spam Defaults
                'antispam_enabled': False,      # Default: OFF
                'antispam_action': 'mute',      # 'mute' (Warn) or 'kick'
                'mute_duration': 600,           # Default: 10 Minutes (600s)

                # Auto Mention Defaults
                'automention_enabled': True,     # Default: ON
                'mention_interval': 300,         # Default: 5 min
                'last_mention_time': 0,          
                'pending_mentions': [],          # List of IDs

                # ✅ Auto Post Defaults
                'autopost_enabled': False,      # Default: OFF
                'autopost_interval': 1800,      # Default: 30 min (1800s)
                'last_autopost_time': 0,        
                'autopost_text': None,          
                'autopost_image': None,         
                'autopost_buttons': {},         
                
                # ✅ Admin Free Access Default
                'admin_free_access': False,     # Default: Disabled

                # Time Defaults
                'time_dynamic': 86400,
                'time_smart': 86400,
                'time_together': 604800,       
                'time_together_3': 86400,      
                'time_gap1': 300,
                'time_gap2': 300
            }
            await self.groups.insert_one(default_settings)
        else:
            # Update Title if changed
            await self.groups.update_one({'id': int(id)}, {'$set': {'title': title}})

    # --- ⚙️ GROUP SETTINGS HELPERS ---
    
    async def get_group_settings(self, id):
        return await self.groups.find_one({'id': int(id)})

    async def update_group_settings(self, id, settings):
        await self.groups.update_one({'id': int(id)}, {'$set': settings})

    # --- 📰 AUTO POST HELPERS (NEW) ---

    async def set_autopost_button(self, chat_id, slot, text, url):
        key = f"autopost_buttons.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': {key: {'text': text, 'url': url}}}
        )

    async def remove_autopost_button(self, chat_id, slot):
        key = f"autopost_buttons.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {key: ""}}
        )

    async def reset_autopost_content(self, chat_id):
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': {
                'autopost_text': None, 
                'autopost_image': None, 
                'autopost_buttons': {}
            }}
        )

    # --- 📣 AUTO MENTION HELPERS ---

    async def add_pending_mention(self, chat_id, user_id):
        """Adds a user to the pending mention list if not already present."""
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$addToSet': {'pending_mentions': int(user_id)}}
        )

    async def get_pending_mentions(self, chat_id):
        """Fetches the list of pending users."""
        group = await self.groups.find_one({'id': int(chat_id)})
        return group.get('pending_mentions', []) if group else []

    async def remove_pending_mentions(self, chat_id, user_ids):
        """Removes mentioned users from the list and updates timestamp."""
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$pull': {'pending_mentions': {'$in': user_ids}}}
        )
        # Update last run time to now
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

    async def remove_shortener(self, chat_id, slot):
        key = f"shorteners.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {key: ""}}
        )

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
            print(f"Auto-Fix Error: {e}")

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

    async def remove_fsub_channel(self, chat_id, slot):
        key = f"fsub_channels.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {key: ""}}
        )

    async def remove_all_fsub_channels(self, chat_id):
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {'fsub_channels': ""}} 
        )

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

        # Auto-Fix Logic for Corrupt Data
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

# ✅ INITIALIZATION
db = UserChatDB(USER_DB_URI, DATABASE_NAME)
