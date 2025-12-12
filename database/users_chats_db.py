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

    # --- 🔒 3-LEVEL GROUP VERIFICATION SYSTEM (FIXED) ---
    
    async def get_verify_status(self, user_id, chat_id, level):
        """
        Check verification status safely handles legacy data.
        """
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})

            # 1. Agar root verify_status hi number hai (Legacy Data)
            if isinstance(all_verifications, (int, float)):
                return False

            # 2. Specific Chat ID ka data nikalo
            chat_verifications = all_verifications.get(str(chat_id), {})

            # 3. Agar chat verification data number hai (Intermediate Legacy Data)
            if isinstance(chat_verifications, (int, float)):
                return False

            # 4. Ab specific Level check karo (Default 0)
            expiry = chat_verifications.get(str(level), 0)
            return expiry > time.time()
            
        return False

    async def update_verify_status(self, user_id, chat_id, level):
        """
        Update verification status with Auto-Fix for legacy schema.
        """
        from info import VERIFY_EXPIRE
        expiry_date = time.time() + VERIFY_EXPIRE
        
        # 1. Fetch user to check current schema state
        user = await self.users.find_one({'id': int(user_id)})
        
        if user:
            current_status = user.get('verify_status')
            
            # ⚠️ AUTO-FIX 1: Agar ROOT status purana (number) hai -> Reset to dict
            if isinstance(current_status, (int, float)):
                await self.users.update_one(
                    {'id': int(user_id)},
                    {'$set': {'verify_status': {}}}
                )
            
            # ⚠️ AUTO-FIX 2: Agar ROOT dict hai, par CHAT data number hai -> Reset chat key
            elif isinstance(current_status, dict):
                chat_status = current_status.get(str(chat_id))
                if isinstance(chat_status, (int, float)):
                    await self.users.update_one(
                        {'id': int(user_id)},
                        {'$set': {f'verify_status.{str(chat_id)}': {}}}
                    )

        # 2. Safe Update using Dot Notation
        key_name = f"verify_status.{str(chat_id)}.{str(level)}"
        
        await self.users.update_one(
            {'id': int(user_id)},
            {'$set': {key_name: expiry_date}},
            upsert=True
        )

db = UserChatDB(DATABASE_URI, DATABASE_NAME)
