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

    async def save_file(self, media, message):
        try:
            duplicate = await self.data_col.find_one({
                'chat_id': message.chat.id,
                'msg_id': message.id
            })
            if duplicate:
                return 'duplicate'

            unique_id = await self.get_next_sequence_value("file_id_counter")
            
            file_name = media.file_name
            file_size = media.file_size
            file_id = media.file_id
            
            # --- CAPTION CLEANING LOGIC ---
            caption = message.caption.html if message.caption else None
            
            if caption:
                # Ye Extensions dhoondhega (Case Insensitive)
                # Aap aur bhi add kar sakte hain
                regex = r"(?i)(.*?)(\.mkv|\.mp4|\.avi|\.webm|\.m4v|\.flv)"
                
                # Search karega
                match = re.search(regex, caption, re.DOTALL)
                
                if match:
                    # Group 1: File ka naam
                    # Group 2: Extension (.mkv)
                    # Sirf wahi tak rakhna hai, uske baad ka sab uda dena hai
                    caption = match.group(1) + match.group(2)
                    
                    # Agar caption HTML (Bold) me tha, to Tags fix karne ki koshish (Optional safety)
                    if "<b>" in caption and "</b>" not in caption:
                        caption += "</b>"
                    if "<i>" in caption and "</i>" not in caption:
                        caption += "</i>"
                        
            # -------------------------------

            # 1. Save Data
            await self.data_col.insert_one({
                '_id': unique_id,
                'msg_id': message.id,
                'chat_id': message.chat.id,
                'file_id': file_id
            })

            # 2. Save Search Info (Clean Caption ke saath)
            await self.search_col.insert_one({
                'file_name': file_name,
                'file_size': file_size, 
                'caption': caption, # Ab ye clean wala save hoga
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
