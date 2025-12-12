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

    # --- 🔒 3-LEVEL GROUP VERIFICATION SYSTEM ---
    
    async def get_verify_status(self, user_id, chat_id, level):
        """
        Check if a user is verified for a specific Group AND specific Level.
        Structure: verify_status -> chat_id -> level -> timestamp
        """
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})

            # Agar purana format hai (not dict), to False return karo
            if not isinstance(all_verifications, dict):
                return False

            # Specific Chat ID ka data nikalo
            chat_verifications = all_verifications.get(str(chat_id), {})

            # Agar chat verification purana format hai (int/float), to False return karo
            if isinstance(chat_verifications, (int, float)):
                return False

            # Ab specific Level check karo (Default 0)
            expiry = chat_verifications.get(str(level), 0)
            return expiry > time.time()
            
        return False

    async def update_verify_status(self, user_id, chat_id, level):
        """
        Update verification status for a specific Group AND Level.
        """
        from info import VERIFY_EXPIRE
        expiry_date = time.time() + VERIFY_EXPIRE
        
        # MongoDB Dot notation use karke specific level update karenge
        # Key: verify_status.{chat_id}.{level}
        key_name = f"verify_status.{str(chat_id)}.{str(level)}"
        
        await self.users.update_one(
            {'id': int(user_id)},
            {'$set': {key_name: expiry_date}},
            upsert=True
        )

db = UserChatDB(DATABASE_URI, DATABASE_NAME)
