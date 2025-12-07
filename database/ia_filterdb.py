import logging
import re
from motor.motor_asyncio import AsyncIOMotorClient
# 👇 Ye line sabse zaruri hai
from bson.objectid import ObjectId 
from info import DATABASE_URI

class MediaDB:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.files

    async def ensure_indexes(self):
        await self.col.create_index([("file_name", "text")])
        await self.col.create_index("file_id", unique=True)

    async def save_file(self, media, message=None):
        try:
            file_id = media.file_id
            file_name = media.file_name
            file_size = media.file_size
            
            caption = None
            if message and message.caption:
                caption = message.caption.html

            file = await self.col.find_one({'file_id': file_id})
            if file:
                return 'duplicate'
            
            await self.col.insert_one({
                'file_id': file_id,
                'file_name': file_name,
                'file_size': file_size,
                'caption': caption,
                'file_type': media.mime_type
            })
            return 'saved'
        except Exception as e:
            print(f"Error saving file: {e}")
            return 'error'

    async def get_search_results(self, query):
        regex = re.compile(query, re.IGNORECASE)
        cursor = self.col.find({"file_name": regex})
        cursor.sort('$natural', -1)
        files = await cursor.to_list(length=10)
        return files

    # 👇 Ye naya function add hona chahiye
    async def get_file_by_id(self, _id):
        try:
            return await self.col.find_one({'_id': ObjectId(_id)})
        except Exception as e:
            print(f"Get File Error: {e}")
            return None

Media = MediaDB(DATABASE_URI, "MyBotDB")
