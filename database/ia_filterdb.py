import logging
import re
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from info import DATABASE_URI, DATABASE_NAME

class MediaDB:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        
        self.data_col = self.db.files_data   
        self.search_col = self.db.files_search 
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

    # ✅ NEW: Cleaning Function
    def clean_text(self, text):
        if not text:
            return None
        
        # 1. Remove anything inside [ ] brackets (e.g., [@RunningMoviesHD])
        text = re.sub(r"\[.*?\]", "", text)
        
        # 2. Remove any word starting with @ (e.g., @VPFILS)
        text = re.sub(r"@\w+", "", text)
        
        # 3. Remove extra spaces (Double spaces ko single banao)
        text = re.sub(r"\s+", " ", text).strip()
        
        return text

    async def save_file(self, media, message):
        try:
            duplicate = await self.data_col.find_one({
                'chat_id': message.chat.id,
                'msg_id': message.id
            })
            if duplicate:
                return 'duplicate'

            unique_id = await self.get_next_sequence_value("file_id_counter")
            
            # --- FILE NAME CLEANING ---
            original_filename = media.file_name
            # Yahan hum 'clean_text' function use kar rahe hain
            file_name = self.clean_text(original_filename)
            
            file_size = media.file_size
            file_id = media.file_id
            
            # --- CAPTION CLEANING ---
            caption = message.caption.html if message.caption else None
            
            if caption:
                # Step 1: Remove [ ] and @
                caption = self.clean_text(caption)
                
                # Step 2: Stop at .mkv/.mp4 (Purana Logic)
                regex = r"(?i)(.*?)(\.mkv|\.mp4|\.avi|\.webm|\.m4v|\.flv)"
                match = re.search(regex, caption, re.DOTALL)
                if match:
                    caption = match.group(1) + match.group(2)
            
            # Agar caption khali ho gaya (cleaning ke baad), to file name use karo
            if not caption:
                caption = file_name

            # -------------------------------

            # 1. Save Data
            await self.data_col.insert_one({
                '_id': unique_id,
                'msg_id': message.id,
                'chat_id': message.chat.id,
                'file_id': file_id
            })

            # 2. Save Search Info (Ab Clean Name aur Clean Caption save hoga)
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
            search_query = {
                "$or": [
                    {"file_name": regex}, 
                    {"caption": regex}
                ]
            }
            cursor = self.search_col.find(search_query)
            cursor.sort('$natural', -1)
            files = await cursor.to_list(length=10)
            return files
        except Exception as e:
            print(f"Search Error: {e}")
            return []

    async def get_file_details(self, link_id):
        try:
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
