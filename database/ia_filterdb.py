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
        # Regular indexes (Backup ke liye)
        await self.search_col.create_index("file_name")
        await self.search_col.create_index("caption")
        await self.search_col.create_index("link_id")
        await self.data_col.create_index([("chat_id", 1), ("msg_id", 1)], unique=True)

    async def get_next_sequence_value(self, sequence_name, increment=1):
        doc = await self.counters.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"sequence_value": increment}}, 
            upsert=True,
            return_document=True
        )
        return doc["sequence_value"]

    # --- BULK SAVE (FAST) ---
    async def save_batch(self, items):
        if not items: return 0, 0 
        
        count = len(items)
        end_sequence = await self.get_next_sequence_value("file_id_counter", increment=count)
        start_sequence = end_sequence - count + 1
        
        data_docs = []
        search_docs = []
        current_id = start_sequence
        
        for media, message in items:
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

        saved_count = 0
        duplicate_count = 0
        
        try:
            if data_docs:
                await self.data_col.insert_many(data_docs, ordered=False)
                await self.search_col.insert_many(search_docs, ordered=False)
                saved_count = len(data_docs)
        except Exception as e:
            if "E11000" in str(e):
                try:
                    saved_count = e.details['nInserted']
                    duplicate_count = count - saved_count
                except:
                    saved_count = 0
                    duplicate_count = count
            else:
                print(f"Bulk Save Error: {e}")
        return saved_count, duplicate_count

    async def get_file_details(self, link_id):
        return await self.data_col.find_one({'_id': int(link_id)})

    # 🚀 ATLAS SEARCH LOGIC (LUCENE - MAX POWER) 🚀
    async def get_search_results(self, query):
        try:
            # $search Aggregation Pipeline
            pipeline = [
                {
                    "$search": {
                        "index": "default", # Step 1 wala index name
                        "text": {
                            "query": query,
                            "path": ["file_name", "caption"], # Kahan dhundna hai
                            "fuzzy": {
                                "maxEdits": 2,       # ✅ Max Limit (3 allowed nahi hai, 2 best hai)
                                "prefixLength": 0,   # ✅ Pehla letter bhi galat ho sakta hai
                                "maxExpansions": 50  # ✅ Zyada variations check karega
                            }
                        }
                    }
                },
                {
                    "$limit": 10 # Top 10 results
                }
            ]
            
            # Aggregate run karo
            cursor = self.search_col.aggregate(pipeline)
            files = await cursor.to_list(length=10)
            return files
            
        except Exception as e:
            print(f"Atlas Search Error: {e}")
            # Fallback: Agar Atlas Index nahi bana, to purana Regex use karo
            print("Falling back to Regex Search...")
            regex = re.compile(query, re.IGNORECASE)
            cursor = self.search_col.find({"$or": [{"file_name": regex}, {"caption": regex}]})
            cursor.sort('$natural', -1)
            return await cursor.to_list(length=10)

    async def total_files_count(self):
        return await self.data_col.count_documents({})

    async def get_db_size(self):
        try:
            stats = await self.db.command("dbstats")
            return stats['dataSize']
        except:
            return 0

Media = MediaDB(DATABASE_URI, DATABASE_NAME)
