import logging
import re
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from info import DATABASE_URI, DATABASE_NAME

class MediaDB:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        
        # Collections
        self.data_col = self.db.files_data   # Msg ID, Chat ID (Small)
        self.search_col = self.db.files_search # File Name, Link ID (Searchable)
        self.counters = self.db.counters

    async def ensure_indexes(self):
        # Regex search ke liye normal index kaafi hai
        await self.search_col.create_index("file_name")
        await self.search_col.create_index("link_id")

    async def get_next_sequence_value(self, sequence_name):
        doc = await self.counters.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"sequence_value": 1}},
            upsert=True,
            return_document=True
        )
        return doc["sequence_value"]

    async def save_file(self, media, message):
        try:
            # 1. Generate ID
            unique_id = await self.get_next_sequence_value("file_id_counter")
            
            file_name = media.file_name
            caption = message.caption.html if message.caption else None

            # 2. Save Data (Small Part)
            await self.data_col.insert_one({
                '_id': unique_id,
                'msg_id': message.id,
                'chat_id': message.chat.id
            })

            # 3. Save Search Info (Big Part)
            await self.search_col.insert_one({
                'file_name': file_name,
                'caption': caption,
                'link_id': unique_id
            })
            return 'saved'
            
        except Exception as e:
            print(f"Error saving file: {e}")
            return 'error'

    # ✅ CHANGE: Wapis Regex Search par aa gaye hain
    async def get_search_results(self, query):
        try:
            # Pattern Matching (Case Insensitive)
            regex = re.compile(query, re.IGNORECASE)
            
            # files_search collection me dhoondho
            cursor = self.search_col.find({"file_name": regex})
            cursor.sort('$natural', -1) # Latest files pehle
            
            files = await cursor.to_list(length=10)
            return files
        except Exception as e:
            print(f"Search Error: {e}")
            return []

    async def get_file_details(self, link_id):
        try:
            # Data collection se asli IDs nikalo
            return await self.data_col.find_one({'_id': int(link_id)})
        except Exception as e:
            print(f"Get File Error: {e}")
            return None

Media = MediaDB(DATABASE_URI, DATABASE_NAME)
