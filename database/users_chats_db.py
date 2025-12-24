import motor.motor_asyncio
import time
from info import DATABASE_URI, DATABASE_NAME

class UserChatDB:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.groups = self.db.groups
        self.banned = self.db.banned 
        self.fsub_pending = self.db.fsub_pending # ✅ New Collection for Join Requests

    async def add_user(self, id):
        user = await self.users.find_one({'id': int(id)})
        if not user:
            await self.users.insert_one({'id': int(id)})

    # ✅ Add Group with Default Settings
    async def add_group(self, id):
        group = await self.groups.find_one({'id': int(id)})
        if not group:
            default_settings = {
                'id': int(id),
                'earning_method': 'shortlink', # shortlink or fsub
                'shortener_mode': 'dynamic',   # dynamic, together, smart
                'shorteners': {},              # { '1': {'site': '...', 'api': '...'} }
                'fsub_channels': {},           # ✅ Dict for Slots { '1': -100xx }
                'is_shortlink_active': True,
                # Time Defaults
                'time_dynamic': 86400,
                'time_smart': 86400,
                'time_together': 604800,       # 7 Days
                'time_together_3': 86400,      # 24 Hours
                'time_gap1': 300,
                'time_gap2': 300
            }
            await self.groups.insert_one(default_settings)

    # --- ⚙️ GROUP SETTINGS HELPERS ---
    
    async def get_group_settings(self, id):
        return await self.groups.find_one({'id': int(id)})

    async def update_group_settings(self, id, settings):
        await self.groups.update_one({'id': int(id)}, {'$set': settings})

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

    # --- 🔒 FSUB CHANNEL MANAGEMENT (NEW) ---
    async def update_fsub_channel(self, chat_id, slot, channel_id):
        """Saves a specific channel ID to a specific slot (1, 2, 3, or 4)"""
        key = f"fsub_channels.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': {key: int(channel_id)}},
            upsert=True
        )

    async def remove_fsub_channel(self, chat_id, slot):
        """Removes a specific channel ID from a slot"""
        key = f"fsub_channels.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {key: ""}}
        )

    async def remove_all_fsub_channels(self, chat_id):
        """Removes all fsub channels for a group"""
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
        """
        Checks if user has FINAL FULL ACCESS (Level 0).
        """
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})
            if isinstance(all_verifications, (int, float)): return False

            chat_data = all_verifications.get(str(chat_id), {})
            if isinstance(chat_data, (int, float)): return False

            # Check Level 0 (Full Access Token) Expiry
            return chat_data.get('0', 0) > time.time()
            
        return False

    async def get_level_time(self, user_id, chat_id, level):
        """
        Returns the TIMESTAMP when a specific level was completed.
        """
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})
            if isinstance(all_verifications, (int, float)): return 0
            
            chat_data = all_verifications.get(str(chat_id), {})
            if isinstance(chat_data, (int, float)): return 0
            
            return chat_data.get(str(level), 0)
        return 0

    async def update_verify_status(self, user_id, chat_id, level, duration=0, is_reset=False):
        """
        Updates verification status with Auto-Fix & Reset capability.
        """
        current_time = time.time()
        
        if is_reset:
            value = 0 # Reset logic
        elif duration > 0:
            value = current_time + duration # Expiry Timestamp
        else:
            value = current_time # Completion Timestamp

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

    # --- 🔥 ADVANCED FSUB PENDING LOGIC 🔥 ---
    
    async def add_pending_request(self, user_id, channel_id):
        """Adds a user to the pending join request list."""
        try:
            await self.fsub_pending.update_one(
                {'_id': f"{user_id}_{channel_id}"},
                {'$set': {'user_id': int(user_id), 'chat_id': int(channel_id)}},
                upsert=True
            )
        except Exception as e:
            print(f"Error adding pending request: {e}")

    async def remove_pending_request(self, user_id, channel_id):
        """Removes a user from the pending list (When joined/left/approved)."""
        try:
            await self.fsub_pending.delete_one({'_id': f"{user_id}_{channel_id}"})
        except Exception as e:
            print(f"Error removing pending request: {e}")

    async def is_user_pending(self, user_id, channel_id):
        """Checks if a user has a pending join request."""
        try:
            found = await self.fsub_pending.find_one({'_id': f"{user_id}_{channel_id}"})
            return bool(found)
        except:
            return False

db = UserChatDB(DATABASE_URI, DATABASE_NAME)
