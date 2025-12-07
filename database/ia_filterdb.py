import logging
from struct import pack
import re
from pyrogram.file_id import FileId
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI

class MediaDB:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.files

    async def ensure_indexes(self):
        # Search fast karne ke liye
        await self.col.create_index([("file_name", "text")])
        # Duplicate rokne ke liye unique index
        await self.col.create_index("file_id", unique=True)

    async def save_file(self, media):
        """
        Returns: 
        'saved': Agar nayi file save hui.
        'duplicate': Agar file pehle se thi.
        'error': Agar koi error aaya.
        """
        try:
            file_id = media.file_id
            file_name = media.file_name
            file_size = media.file_size
            
            # 1. Check Duplicate (Pehle se hai ya nahi)
            file = await self.col.find_one({'file_id': file_id})
            if file:
                return 'duplicate'
            
            # 2. Nayi file Save karo
            await self.col.insert_one({
                'file_id': file_id,
                'file_name': file_name,
                'file_size': file_size,
                'caption': media.caption.html if media.caption else None,
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

Media = MediaDB(DATABASE_URI, "MyBotDB")
