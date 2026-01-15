import logging
import re
import uuid
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError
from pymongo import ReturnDocument # ✅ Added this import
from info import DATABASE_URI, DATABASE_NAME

logger = logging.getLogger(__name__)

class MediaDB:
    def __init__(self, uri, database_name):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        
        self.data_col = self.db.files_data   
        self.search_col = self.db.files_search 
        self.counters = self.db.counters
        self.search_cache = self.db.search_cache 
        self.temp_searches = self.db.temp_searches

    async def ensure_indexes(self):
        await self.search_col.create_index("file_name")
        await self.search_col.create_index("caption")
        await self.search_col.create_index("link_id")
        await self.data_col.create_index("file_unique_id", unique=True)
        await self.search_cache.create_index("created_at", expireAfterSeconds=3600)
        await self.temp_searches.create_index("created_at", expireAfterSeconds=172800)

    async def get_next_sequence_value(self, sequence_name, increment=1):
        """
        Atomically increments the counter and returns the new integer.
        """
        doc = await self.counters.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"sequence_value": increment}}, 
            upsert=True,
            return_document=ReturnDocument.AFTER # ✅ Explicitly using AFTER
        )
        return doc["sequence_value"]

    async def save_search_query(self, query, user_id):
        try:
            # 1. Get unique Auto-ID
            search_id = await self.get_next_sequence_value("search_id_counter", increment=1)
            
            # 2. Save to Temp Collection
            await self.temp_searches.insert_one({
                "_id": int(search_id),
                "query": query,
                "user_id": int(user_id),
                "created_at": datetime.datetime.utcnow()
            })
            
            return int(search_id)
        except Exception as e:
            logger.error(f"Error saving search query: {e}")
            return None # If DB fails, this returns None

    async def get_search_query(self, search_id):
        try:
            doc = await self.temp_searches.find_one({"_id": int(search_id)})
            return doc['query'] if doc else None
        except Exception as e:
            logger.error(f"Error fetching search ID {search_id}: {e}")
            return None

    # ... (Keep the clean_text, save_batch, get_file_details, get_search_results methods as they are) ...
    # Copy paste the rest of your existing functions here if you are replacing the whole file.
    
    @staticmethod
    def clean_text(text):
        if not text: return ""
        text = re.sub(r"\[@RunningMoviesHD\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"@\w+", "", text)
        text = re.sub(r"[-_.]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    async def save_batch(self, items):
        if not items: return 0, 0 
        
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
        if not new_items: return 0, pre_duplicate_count 
            
        count = len(new_items)
        end_sequence = await self.get_next_sequence_value("file_id_counter", increment=count)
        start_sequence = end_sequence - count + 1
        
        data_docs = []
        search_docs = []
        current_id = start_sequence
        
        for media, message in new_items:
            file_name = self.clean_text(media.file_name)
            if not file_name: file_name = "Unknown File"

            caption = message.caption.html if message.caption else None
            if caption:
                caption = self.clean_text(caption)
                regex = r"(?i)(.*?)(\.mkv|\.mp4|\.avi|\.webm|\.m4v|\.flv)"
                match = re.search(regex, caption, re.DOTALL)
                if match:
                    caption = match.group(1) + match.group(2)

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
                'caption': caption,
                'link_id': current_id,
                'chat_id': message.chat.id
            })
            current_id += 1

        saved_count = 0
        failed_indices = []
        
        if data_docs:
            try:
                await self.data_col.insert_many(data_docs, ordered=False)
                saved_count = len(data_docs)
            except BulkWriteError as bwe:
                saved_count = bwe.details['nInserted']
                for error in bwe.details['writeErrors']:
                    failed_indices.append(error['index'])
                pre_duplicate_count += len(failed_indices)
            except Exception as e:
                print(f"❌ Critical Error Saving FILES_DATA: {e}")
                return 0, count + pre_duplicate_count

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

    async def get_search_results(self, query):
        try:
            words = query.split()
            if len(words) <= 1:
                search_stage = {
                    "$search": {
                        "index": "default",
                        "text": {
                            "query": query,
                            "path": ["file_name", "caption"],
                            "fuzzy": {"maxEdits": 2, "prefixLength": 0, "maxExpansions": 50}
                        }
                    }
                }
            else:
                must_clauses = []
                for word in words:
                    must_clauses.append({
                        "text": {
                            "query": word,
                            "path": ["file_name", "caption"],
                            "fuzzy": {"maxEdits": 1}
                        }
                    })
                search_stage = {
                    "$search": {
                        "index": "default",
                        "compound": {"must": must_clauses}
                    }
                }

            pipeline = [search_stage, {"$limit": 50}]
            cursor = self.search_col.aggregate(pipeline)
            files = await cursor.to_list(length=50)
            return files
        except Exception as e:
            safe_query = re.escape(query)
            regex = re.compile(safe_query, re.IGNORECASE)
            cursor = self.search_col.find({"$or": [{"file_name": regex}, {"caption": regex}]})
            cursor.sort('$natural', -1)
            return await cursor.to_list(length=50)

    async def total_files_count(self):
        return await self.data_col.count_documents({})
        
    async def get_db_size(self):
        try:
            stats = await self.db.command("dbstats")
            return stats['dataSize']
        except: return 0

    async def save_search_results(self, query, files, chat_id):
        unique_id = str(uuid.uuid4())[:8]
        simplified_files = []
        for file in files:
            simplified_files.append({
                "file_name": file['file_name'],
                "file_size": file['file_size'],
                "link_id": file['link_id'],
                "file_chat_id": file.get('chat_id') 
            })
        await self.search_cache.insert_one({
            "_id": unique_id,
            "query": query,
            "chat_id": chat_id,
            "files": simplified_files,
            "created_at": datetime.datetime.utcnow()
        })
        return unique_id

    async def get_cached_results(self, unique_id):
        return await self.search_cache.find_one({"_id": unique_id})

Media = MediaDB(DATABASE_URI, DATABASE_NAME)
