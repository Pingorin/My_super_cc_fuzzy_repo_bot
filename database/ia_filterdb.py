import logging
import re
from motor.motor_asyncio import AsyncIOMotorClient
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
        await self.search_col.create_index("caption")
        await self.search_col.create_index("link_id")
        # Duplicate check ko fast karne ke liye index
        await self.data_col.create_index([("chat_id", 1), ("msg_id", 1)], unique=True)

    async def get_next_sequence_value(self, sequence_name, increment=1):
        doc = await self.counters.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"sequence_value": increment}}, # ✅ Bulk Increment
            upsert=True,
            return_document=True
        )
        return doc["sequence_value"]

    # --- ✨ BULK SAVE LOGIC (SUPER FAST) ---
    async def save_batch(self, items):
        # items is a list of tuples: (media, message)
        if not items: return 0, 0 # Saved, Duplicates
        
        count = len(items)
        
        # 1. Ek baar me saare IDs reserve kar lo
        end_sequence = await self.get_next_sequence_value("file_id_counter", increment=count)
        start_sequence = end_sequence - count + 1
        
        data_docs = []
        search_docs = []
        
        current_id = start_sequence
        
        for media, message in items:
            # Cleaning Logic
            def clean_text(text):
                if not text: return None
                text = re.sub(r"\[@RunningMoviesHD\]", "", text, flags=re.IGNORECASE)
                text = re.sub(r"@\w+", "", text)
                text = re.sub(r"[-_]", " ", text)
                return re.sub(r"\s+", " ", text).strip()

            file_name = clean_text(media.file_name)
            caption = message.caption.html if message.caption else None
            
            if caption:
                caption = clean_text(caption)
                regex = r"(?i)(.*?)(\.mkv|\.mp4|\.avi|\.webm|\.m4v|\.flv)"
                match = re.search(regex, caption, re.DOTALL)
                if match:
                    caption = match.group(1) + match.group(2)
                    if "<b>" in caption and "</b>" not in caption: caption += "</b>"
                    if "<i>" in caption and "</i>" not in caption: caption += "</i>"

            # Prepare Documents
            data_docs.append({
                '_id': current_id,
                'msg_id': message.id,
                'chat_id': message.chat.id,
                'file_id': media.file_id
            })
            
            search_docs.append({
                'file_name': file_name,
                'file_size': media.file_size, 
                'caption': caption,
                'link_id': current_id
            })
            
            current_id += 1

        # 2. Bulk Insert (Try-Catch for Duplicates)
        saved_count = 0
        duplicate_count = 0
        
        try:
            # Ordered=False ka matlab: Agar ek fail ho (duplicate), to baaki rukenge nahi
            if data_docs:
                await self.data_col.insert_many(data_docs, ordered=False)
                await self.search_col.insert_many(search_docs, ordered=False)
                saved_count = len(data_docs)
        except Exception as e:
            # Agar duplicate error aaye (BulkWriteError), to hum count nikalenge
            if "E11000" in str(e):
                # Jitne insert ho gaye wo saved, baaki duplicate
                # Exact count nikalna mushkil hai bulk me bina slow kiye, 
                # hum assume karte hain jo fail huye wo duplicate hain.
                try:
                    saved_count = e.details['nInserted']
                    duplicate_count = count - saved_count
                except:
                    saved_count = 0
                    duplicate_count = count
            else:
                print(f"Bulk Save Error: {e}")
                
        return saved_count, duplicate_count

    # Single File Save (Backup ke liye)
    async def get_file_details(self, link_id):
        return await self.data_col.find_one({'_id': int(link_id)})

    async def get_search_results(self, query):
        regex = re.compile(query, re.IGNORECASE)
        search_query = {"$or": [{"file_name": regex}, {"caption": regex}]}
        cursor = self.search_col.find(search_query)
        cursor.sort('$natural', -1)
        files = await cursor.to_list(length=10)
        return files

    async def total_files_count(self):
        return await self.data_col.count_documents({})

    async def get_db_size(self):
        try:
            stats = await self.db.command("dbstats")
            return stats['dataSize']
        except:
            return 0

Media = MediaDB(DATABASE_URI, DATABASE_NAME)
