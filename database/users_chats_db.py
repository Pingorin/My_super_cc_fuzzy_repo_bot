import motor.motor_asyncio
import time # ✅ Time module add kiya
from info import DATABASE_URI, DATABASE_NAME

class UserChatDB:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.groups = self.db.groups
        # Collection for banned users/chats
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

    # --- 🔒 VERIFICATION SYSTEM FUNCTIONS (NEW) ---
    
    async def get_verify_status(self, user_id):
        # User ko database me dhundo
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            # Check karo: 'verify_status' ka time abhi ke time se bada hai ya nahi
            # Agar verify_status key nahi hai to default 0 milega (yani Not Verified)
            return user.get('verify_status', 0) > time.time()
        return False

    async def update_verify_status(self, user_id):
        from info import VERIFY_EXPIRE # Circular import se bachne ke liye yahan import kiya
        
        # Abhi ka time + Expire Time (e.g. 24 hours)
        expiry_date = time.time() + VERIFY_EXPIRE
        
        # Database update karo
        await self.users.update_one(
            {'id': int(user_id)},
            {'$set': {'verify_status': expiry_date}},
            upsert=True # Agar user nahi hai to create kar dega
        )

db = UserChatDB(DATABASE_URI, DATABASE_NAME)
