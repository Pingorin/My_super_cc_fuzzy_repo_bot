import logging
import re
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import TEXT
from info import DATABASE_URI, DATABASE_NAME

class MediaDB:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        
        # Collection 1: For Forwarding (Small Size)
        self.data_col = self.db.files_data
        
        # Collection 2: For Searching (Contains Names)
        self.search_col = self.db.files_search
        
        # Collection 3: To keep track of the ID counter
        self.counters = self.db.counters

    async def ensure_indexes(self):
        # files_search पर Text Index (Search के लिए)
        # यह नाम को तेजी से खोजने में मदद करेगा
        await self.search_col.create_index([("file_name", TEXT)])
        
        # link_id पर इंडेक्स ताकि सर्च के बाद डेटा तेजी से मिले
        await self.search_col.create_index("link_id")

    async def get_next_sequence_value(self, sequence_name):
        """
        यह फंक्शन 1, 2, 3... जैसी यूनिक ID जनरेट करेगा।
        """
        doc = await self.counters.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"sequence_value": 1}},
            upsert=True,
            return_document=True
        )
        return doc["sequence_value"]

    async def save_file(self, media, message):
        """
        फाइल को दो टुकड़ों में सेव करता है।
        """
        try:
            # 1. यूनिक ID जनरेट करें (Integer)
            unique_id = await self.get_next_sequence_value("file_id_counter")
            
            file_name = media.file_name
            
            # Caption हैंडलिंग
            caption = message.caption.html if message.caption else None

            # --- Collection 1: DATA (सिर्फ जरूरी डेटा फॉरवर्डिंग के लिए) ---
            await self.data_col.insert_one({
                '_id': unique_id,             # जैसे: 1, 2, 3
                'msg_id': message.id,         # Telegram Message ID
                'chat_id': message.chat.id    # Source Channel ID
            })

            # --- Collection 2: SEARCH (नाम और लिंक ID) ---
            await self.search_col.insert_one({
                'file_name': file_name,
                'caption': caption,
                'link_id': unique_id          # यह files_data के _id से जुड़ेगा
            })
            
            return 'saved'
            
        except Exception as e:
            print(f"Error saving file: {e}")
            return 'error'

    async def get_search_results(self, query):
        """
        files_search में नाम ढूंढता है और link_id के साथ रिजल्ट देता है।
        """
        # Text Search Query
        # $text सर्च बहुत तेज़ होता है और भारी डेटाबेस के लिए अच्छा है
        cursor = self.search_col.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}} # Relevancy के हिसाब से सॉर्ट करें
        )
        cursor.sort([("score", {"$meta": "textScore"})])
        
        # टॉप 10 रिजल्ट्स
        files = await cursor.to_list(length=10)
        return files

    async def get_file_details(self, link_id):
        """
        link_id (Integer) का उपयोग करके files_data से msg_id और chat_id लाता है।
        """
        try:
            return await self.data_col.find_one({'_id': int(link_id)})
        except Exception as e:
            print(f"Get File Error: {e}")
            return None

# डेटाबेस ऑब्जेक्ट
Media = MediaDB(DATABASE_URI, DATABASE_NAME)
