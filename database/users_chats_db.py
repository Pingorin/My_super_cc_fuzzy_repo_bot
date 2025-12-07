import motor.motor_asyncio
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
        """User ko database me add karta hai"""
        user = await self.users.find_one({'id': int(id)})
        if not user:
            await self.users.insert_one({'id': int(id)})

    async def add_group(self, id):
        """Group ko database me add karta hai"""
        group = await self.groups.find_one({'id': int(id)})
        if not group:
            await self.groups.insert_one({'id': int(id)})

    async def total_users_count(self):
        """Total Users ginta hai"""
        return await self.users.count_documents({})

    async def total_groups_count(self):
        """Total Groups ginta hai"""
        return await self.groups.count_documents({})

    # --- MISSING FUNCTIONS ADDED BELOW ---

    async def get_banned(self):
        """Banned users aur chats ki list return karta hai"""
        users = []
        chats = []
        async for banned_user in self.banned.find({"type": "user"}):
            users.append(banned_user["id"])
        async for banned_chat in self.banned.find({"type": "chat"}):
            chats.append(banned_chat["id"])
        return users, chats

    async def add_ban(self, id, type="user"):
        """User ya Chat ko ban karta hai"""
        is_exist = await self.banned.find_one({"id": int(id), "type": type})
        if not is_exist:
            await self.banned.insert_one({"id": int(id), "type": type})

    async def remove_ban(self, id, type="user"):
        """User ya Chat ko unban karta hai"""
        await self.banned.delete_one({"id": int(id), "type": type})

# Database Object
db = UserChatDB(DATABASE_URI, DATABASE_NAME)
