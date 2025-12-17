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

    async def add_group(self, id):
        group = await self.groups.find_one({'id': int(id)})
        if not group:
            await self.groups.insert_one({'id': int(id)})

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

    # --- 🔒 ADVANCED VERIFICATION SYSTEM (WATERFALL SUPPORT) ---
    
    async def get_verify_status(self, user_id, chat_id):
        """
        Checks if user has FINAL FULL ACCESS (Level 0).
        """
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})

            # Legacy Check 1 (Root is int)
            if isinstance(all_verifications, (int, float)):
                return False

            chat_data = all_verifications.get(str(chat_id), {})

            # Legacy Check 2 (Chat Data is int)
            if isinstance(chat_data, (int, float)):
                return False

            # Check Level 0 (Full Access Token) Expiry
            return chat_data.get('0', 0) > time.time()
            
        return False

    async def get_level_time(self, user_id, chat_id, level):
        """
        Returns the TIMESTAMP when a specific level was completed.
        Used for calculating Gaps.
        """
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})
            
            # Legacy Checks
            if isinstance(all_verifications, (int, float)): return 0
            
            chat_data = all_verifications.get(str(chat_id), {})
            if isinstance(chat_data, (int, float)): return 0
            
            # Return saved timestamp
            return chat_data.get(str(level), 0)
        return 0

    async def update_verify_status(self, user_id, chat_id, level, duration=0):
        """
        Updates verification status.
        - If duration > 0: Sets Expiry (For Full Access).
        - If duration == 0: Sets Current Time (For marking level completion).
        """
        current_time = time.time()
        
        # Calculate Value to Save
        if duration > 0:
            value = current_time + duration # Expiry Timestamp
        else:
            value = current_time # Completion Timestamp

        # --- AUTO-FIX LOGIC START ---
        # Pehle check karo ki database schema sahi hai ya nahi
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            current_status = user.get('verify_status')
            
            # Case A: Root is number -> Reset
            if isinstance(current_status, (int, float)):
                await self.users.update_one(
                    {'id': int(user_id)},
                    {'$set': {'verify_status': {}}}
                )
            
            # Case B: Chat Key is number -> Reset specific chat
            elif isinstance(current_status, dict):
                chat_status = current_status.get(str(chat_id))
                if isinstance(chat_status, (int, float)):
                    await self.users.update_one(
                        {'id': int(user_id)},
                        {'$set': {f'verify_status.{str(chat_id)}': {}}}
                    )
        # --- AUTO-FIX LOGIC END ---

        # Safe Update
        key_name = f"verify_status.{str(chat_id)}.{str(level)}"
        
        await self.users.update_one(
            {'id': int(user_id)},
            {'$set': {key_name: value}},
            upsert=True
        )

db = UserChatDB(DATABASE_URI, DATABASE_NAME)
