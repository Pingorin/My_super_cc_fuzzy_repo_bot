import logging
import re
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError
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
        await self.data_col.create_index("file_unique_id", unique=True)

    async def get_next_sequence_value(self, sequence_name, increment=1):
        doc = await self.counters.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"sequence_value": increment}}, 
            upsert=True,
            return_document=True
        )
        return doc["sequence_value"]

    # --- 🚀 ROBUST SAVE BATCH (Standard Caption) ---
    async def save_batch(self, items):
        if not items: return 0, 0 
        
        # 1. Global Duplicate Check
        unique_ids = [media.file_unique_id for media, msg in items]
        try:
            existing_docs = await self.data_col.find({
                "file_unique_id": {"$in": unique_ids}
            }).to_list(length=len(items))
            existing_unique_ids = set(doc['file_unique_id'] for doc in existing_docs)
        except:
            existing_unique_ids = set()

        new_items = []
        for media, msg in items:
            if media.file_unique_id not in existing_unique_ids:
                new_items.append((media, msg))
        
        pre_duplicate_count = len(items) - len(new_items)
        if not new_items:
            return 0, pre_duplicate_count 
            
        # 2. ID Generation
        count = len(new_items)
        end_sequence = await self.get_next_sequence_value("file_id_counter", increment=count)
        start_sequence = end_sequence - count + 1
        
        data_docs = []
        search_docs = []
        current_id = start_sequence
        
        for media, message in new_items:
            def clean_text(text):
                if not text: return ""
                # Sirf specific junk remove karega
                text = re.sub(r"\[@RunningMoviesHD\]", "", text, flags=re.IGNORECASE)
                text = re.sub(r"@\w+", "", text) # Username removal
                text = re.sub(r"[-_]", " ", text) # Hyphen removal
                return re.sub(r"\s+", " ", text).strip()

            file_name = clean_text(media.file_name)
            if not file_name: file_name = "Unknown File"

            # ✅ CAPTION LOGIC (Rich Caption maintained)
            caption = message.caption.html if message.caption else None
            if caption:
                caption = clean_text(caption)
                # Sirf extension ke baad ka hissa cut karega, baaki sab rakhega
                regex = r"(?i)(.*?)(\.mkv|\.mp4|\.avi|\.webm|\.m4v|\.flv)"
                match = re.search(regex, caption, re.DOTALL)
                if match:
                    caption = match.group(1) + match.group(2)
                    # HTML Tags fix
                    if "<b>" in caption and "</b>" not in caption: caption += "</b>"
                    if "<i>" in caption and "</i>" not in caption: caption += "</i>"

            data_docs.append({
                '_id': current_id,
                'msg_id': message.id,
                'chat_id': message.chat.id,
                'file_id': media.file_id,
                'file_unique_id': media.file_unique_id
            })
            
            search_docs.append({
                'file_name': file_name,
                'file_size': media.file_size, 
                'caption': caption, # ✅ Full cleaned caption saved
                'link_id': current_id
            })
            current_id += 1

        saved_count = 0
        failed_indices = []
        
        # 3. Safe Insertion
        if data_docs:
            try:
                # Step A: Files Data
                await self.data_col.insert_many(data_docs, ordered=False)
                saved_count = len(data_docs)
                
            except BulkWriteError as bwe:
                saved_count = bwe.details['nInserted']
                for error in bwe.details['writeErrors']:
                    failed_indices.append(error['index'])
                pre_duplicate_count += len(failed_indices)
                print(f"⚠️ Partial Save: {saved_count} saved.")
                
            except Exception as e:
                print(f"❌ Critical Error Saving FILES_DATA: {e}")
                return 0, count + pre_duplicate_count

            # Step B: Files Search (Only Valid)
            if saved_count > 0:
                valid_search_docs = []
                for i, doc in enumerate(search_docs):
                    if i not in failed_indices:
                        valid_search_docs.append(doc)
                
                if valid_search_docs:
                    try:
                        await self.search_col.insert_many(valid_search_docs, ordered=False)
                    except Exception as e:
                        print(f"⚠️ Search Index Error: {e}")
                
        return saved_count, pre_duplicate_count

    async def get_file_details(self, link_id):
        return await self.data_col.find_one({'_id': int(link_id)})

    # Atlas Search Logic (Typos Allowed)
    async def get_search_results(self, query):
        try:
            pipeline = [
                {
                    "$search": {
                        "index": "default",
                        "text": {
                            "query": query,
                            "path": ["file_name", "caption"],
                            "fuzzy": {
                                "maxEdits": 2,
                                "prefixLength": 0,
                                "maxExpansions": 50
                            }
                        }
                    }
                },
                {"$limit": 10}
            ]
            cursor = self.search_col.aggregate(pipeline)
            files = await cursor.to_list(length=10)
            return files
        except Exception as e:
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
