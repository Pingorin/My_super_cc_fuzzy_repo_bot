import logging
import re
from motor.motor_asyncio import AsyncIOMotorClient
from info import DATABASE_URI, DATABASE_NAME

class MediaDB:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        
        # Collection 1: Data (Small - Sirf IDs rakhta hai)
        self.data_col = self.db.files_data   
        
        # Collection 2: Search (Big - Naam aur Details rakhta hai)
        self.search_col = self.db.files_search 
        
        # Collection 3: Counters (Integer ID generate karne ke liye)
        self.counters = self.db.counters

    async def ensure_indexes(self):
        # Search fast karne ke liye indexes
        await self.search_col.create_index("file_name")
        await self.search_col.create_index("link_id")

    async def get_next_sequence_value(self, sequence_name):
        """Auto-Increment ID generator (1, 2, 3...)"""
        doc = await self.counters.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"sequence_value": 1}},
            upsert=True,
            return_document=True
        )
        return doc["sequence_value"]

    async def save_file(self, media, message):
        """File ko do collections me tod kar save karta hai"""
        try:
            # 1. DUPLICATE CHECK
            # Check karte hain ki kya ye wala message pehle se saved hai?
            duplicate = await self.data_col.find_one({
                'chat_id': message.chat.id,
                'msg_id': message.id
            })
            if duplicate:
                return 'duplicate'

            # 2. GENERATE ID
            unique_id = await self.get_next_sequence_value("file_id_counter")
            
            # 3. GATHER DATA
            file_name = media.file_name
            file_size = media.file_size
            caption = message.caption.html if message.caption else None

            # 4. SAVE TO DATA COLLECTION (Small Part)
            # Isme hum custom Integer ID use karte hain as '_id'
            await self.data_col.insert_one({
                '_id': unique_id,             # e.g., 125
                'msg_id': message.id,         # Real Telegram Message ID
                'chat_id': message.chat.id    # Channel ID
            })

            # 5. SAVE TO SEARCH COLLECTION (Big Part)
            # Isme hum 'link_id' rakhte hain jo upar wale '_id' se judta hai
            await self.search_col.insert_one({
                'file_name': file_name,
                'file_size': file_size,       # Size button me dikhane ke liye
                'caption': caption,
                'link_id': unique_id          # Connection Link
            })
            return 'saved'
            
        except Exception as e:
            print(f"Error saving file: {e}")
            return 'error'

    async def get_search_results(self, query):
        """Regex use karke search karta hai"""
        try:
            regex = re.compile(query, re.IGNORECASE)
            cursor = self.search_col.find({"file_name": regex})
            cursor.sort('$natural', -1) # Latest files pehle
            
            # Top 10 results return karo
            files = await cursor.to_list(length=10)
            return files
        except Exception as e:
            print(f"Search Error: {e}")
            return []

    async def get_file_details(self, link_id):
        """Integer ID (link_id) se asli Message ID nikalta hai"""
        try:
            return await self.data_col.find_one({'_id': int(link_id)})
        except Exception as e:
            print(f"Get File Error: {e}")
            return None

    # --- STATS FUNCTIONS (For /stats command) ---

    async def get_db_size(self):
        """Database ka total size (storage) batata hai"""
        try:
            stats = await self.db.command("dbstats")
            return stats['dataSize'] 
        except Exception as e:
            print(f"DB Size Error: {e}")
            return 0
    
    async def total_files_count(self):
        """Total kitni files saved hain"""
        return await self.data_col.count_documents({})

# Database Object
Media = MediaDB(DATABASE_URI, DATABASE_NAME)
