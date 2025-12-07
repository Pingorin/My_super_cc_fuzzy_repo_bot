import logging
import re
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME

class MediaDB:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        
        self.data_col = self.db.files_data   # Stores IDs
        self.search_col = self.db.files_search # Stores Names
        self.counters = self.db.counters

    async def ensure_indexes(self):
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

    # ✅ STEP 1: Verify we are saving chat_id and msg_id
    async def save_file(self, media, message):
        try:
            # Duplicate Check (Same Chat + Same Message ID)
            duplicate = await self.data_col.find_one({
                'chat_id': message.chat.id,
                'msg_id': message.id
            })
            if duplicate:
                return 'duplicate'

            unique_id = await self.get_next_sequence_value("file_id_counter")
            
            file_name = media.file_name
            file_size = media.file_size
            # Caption handle
            caption = message.caption.html if message.caption else None

            # 1. Save Location Data (For copy_message)
            await self.data_col.insert_one({
                '_id': unique_id,
                'msg_id': message.id,       # Message ID
                'chat_id': message.chat.id  # Channel ID
            })

            # 2. Save Search Data
            await self.search_col.insert_one({
                'file_name': file_name,
                'file_size': file_size,
                'caption': caption,
                'link_id': unique_id
            })
            return 'saved'
            
        except Exception as e:
            print(f"Error saving file: {e}")
            return 'error'

    async def get_search_results(self, query):
        try:
            regex = re.compile(query, re.IGNORECASE)
            cursor = self.search_col.find({"file_name": regex})
            cursor.sort('$natural', -1)
            files = await cursor.to_list(length=10)
            return files
        except Exception as e:
            print(f"Search Error: {e}")
            return []

    async def get_file_details(self, link_id):
        try:
            # Retrieve chat_id and msg_id using link_id
            return await self.data_col.find_one({'_id': int(link_id)})
        except Exception as e:
            print(f"Get File Error: {e}")
            return None

    async def total_files_count(self):
        return await self.data_col.count_documents({})

    async def get_db_size(self):
        try:
            stats = await self.db.command("dbstats")
            return stats['dataSize']
        except:
            return 0

Media = MediaDB(DATABASE_URI, DATABASE_NAME)
