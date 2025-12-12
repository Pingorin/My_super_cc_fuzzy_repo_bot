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

    # --- 🔒 GROUP SPECIFIC VERIFICATION (UPDATED) ---
    
    async def get_verify_status(self, user_id, chat_id):
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            # Ab hum 'verify_status' ke andar specific Group ID check karenge
            # Database structure: verify_status: { '-100123...': expiry_time, '-100456...': expiry_time }
            all_verifications = user.get('verify_status', {})
            
            # Agar purana data (single timestamp) hai to use handle karo
            if isinstance(all_verifications, (int, float)):
                return all_verifications > time.time()
                
            # Specific Group ka check
            return all_verifications.get(str(chat_id), 0) > time.time()
        return False

    async def update_verify_status(self, user_id, chat_id):
        from info import VERIFY_EXPIRE
        expiry_date = time.time() + VERIFY_EXPIRE
        
        # Specific Group ID ke liye update karo
        # MongoDB Dot notation use karke nested object update karenge
        key_name = f"verify_status.{str(chat_id)}"
        
        await self.users.update_one(
            {'id': int(user_id)},
            {'$set': {key_name: expiry_date}},
            upsert=True
        )

db = UserChatDB(DATABASE_URI, DATABASE_NAME)
