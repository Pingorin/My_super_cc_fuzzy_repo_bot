import motor.motor_asyncio
from info import DATABASE_URI, DATABASE_NAME

class UserChatDB:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.groups = self.db.groups

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

# Database Object
db = UserChatDB(DATABASE_URI, DATABASE_NAME)
