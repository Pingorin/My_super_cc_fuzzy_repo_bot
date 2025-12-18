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

    async def add_user(self, id):
        user = await self.users.find_one({'id': int(id)})
        if not user:
            await self.users.insert_one({'id': int(id)})

    # ✅ UPDATED: Add Group with Default Settings
    async def add_group(self, id):
        group = await self.groups.find_one({'id': int(id)})
        if not group:
            default_settings = {
                'id': int(id),
                'earning_method': 'shortlink', # shortlink or fsub
                'shortener_mode': 'dynamic',   # dynamic, together, smart
                'shorteners': {},              # { '1': {'site': '...', 'api': '...'} }
                'fsub_channels': [],
                'is_shortlink_active': True
            }
            await self.groups.insert_one(default_settings)

    # --- ⚙️ GROUP SETTINGS HELPERS (NEW) ---
    
    async def get_group_settings(self, id):
        return await self.groups.find_one({'id': int(id)})

    async def update_group_settings(self, id, settings):
        await self.groups.update_one({'id': int(id)}, {'$set': settings})

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

    # --- STATS & BAN LOGIC ---

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

    # --- 🔒 ADVANCED VERIFICATION SYSTEM (WATERFALL & AUTO-RESET) ---
    
    async def get_verify_status(self, user_id, chat_id):
        """
        Checks if user has FINAL FULL ACCESS (Level 0).
        """
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})

            # Legacy Check 1
            if isinstance(all_verifications, (int, float)):
                return False

            chat_data = all_verifications.get(str(chat_id), {})

            # Legacy Check 2
            if isinstance(chat_data, (int, float)):
                return False

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
        
        # Calculate Value
        if is_reset:
            value = 0 # Reset logic
        elif duration > 0:
            value = current_time + duration # Expiry Timestamp
        else:
            value = current_time # Completion Timestamp

        # --- AUTO-FIX LOGIC ---
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            current_status = user.get('verify_status')
            if isinstance(current_status, (int, float)):
                await self.users.update_one({'id': int(user_id)}, {'$set': {'verify_status': {}}})
            elif isinstance(current_status, dict):
                chat_status = current_status.get(str(chat_id))
                if isinstance(chat_status, (int, float)):
                    await self.users.update_one({'id': int(user_id)}, {'$set': {f'verify_status.{str(chat_id)}': {}}})

        # Safe Update
        key_name = f"verify_status.{str(chat_id)}.{str(level)}"
        await self.users.update_one(
            {'id': int(user_id)},
            {'$set': {key_name: value}},
            upsert=True
        )

db = UserChatDB(DATABASE_URI, DATABASE_NAME)
