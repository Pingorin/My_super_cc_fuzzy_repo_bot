import logging
import re
import datetime
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError
from pymongo import ReturnDocument
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
        try:
            await self.search_col.create_index("file_name")
            await self.search_col.create_index("caption")
            await self.search_col.create_index("link_id")
            await self.data_col.create_index("file_unique_id", unique=True)
            await self.search_cache.create_index("created_at", expireAfterSeconds=3600)
            await self.temp_searches.create_index("created_at", expireAfterSeconds=172800)
            print("✅ Database Indexes Created Successfully")
        except Exception as e:
            print(f"❌ Error Creating Indexes: {e}")

    async def get_next_sequence_value(self, sequence_name, increment=1):
        try:
            doc = await self.counters.find_one_and_update(
                {"_id": sequence_name},
                {"$inc": {"sequence_value": increment}}, 
                upsert=True,
                return_document=ReturnDocument.AFTER 
            )
            return doc["sequence_value"]
        except Exception as e:
            print(f"❌ Error Getting Sequence ID: {e}")
            return None

    # ==================================================================
    # ⚡ CACHING SAVE FUNCTION
    # ==================================================================
    async def save_search_query(self, query, user_id, files):
        try:
            search_id = await self.get_next_sequence_value("search_id_counter", increment=1)
            if not search_id: return None

            await self.temp_searches.update_one(
                {"_id": int(search_id)},
                {"$set": {
                    "query": query,
                    "user_id": int(user_id),
                    "files": files,
                    "created_at": datetime.datetime.utcnow()
                }},
                upsert=True
            )
            return int(search_id)
        except Exception as e:
            print(f"❌ CRITICAL DB ERROR (Save): {e}")
            return None

    # ✅ NEW: Update Cache (Needed for Pagination on Filtered Results)
    async def update_search_cache(self, search_id, files):
        try:
            await self.temp_searches.update_one(
                {"_id": int(search_id)},
                {"$set": {"files": files}}
            )
        except Exception as e:
            print(f"❌ Cache Update Error: {e}")

    async def get_search_query(self, search_id):
        try:
            return await self.temp_searches.find_one({"_id": int(search_id)})
        except Exception as e:
            print(f"❌ CRITICAL DB ERROR (Get): {e}")
            return None

    # ==================================================================
    
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
        if not end_sequence: return 0, 0
        
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

            # ✅ STRICT TYPE DETECTION
            file_type = "document" 
            if message.video:
                file_type = "video"
            elif message.document:
                file_type = "document"

            data_docs.append({
                '_id': current_id,
                'msg_id': message.id,
                'chat_id': message.chat.id,
                'file_id': media.file_id,
                'file_unique_id': media.file_unique_id,
                'file_type': file_type 
            })
            
            search_docs.append({
                'file_name': file_name,
                'file_size': media.file_size, 
                'caption': caption,
                'link_id': current_id,
                'chat_id': message.chat.id,
                'file_type': file_type # Saved for Filtering
            })
            current_id += 1

        saved_count = 0
        if data_docs:
            try:
                await self.data_col.insert_many(data_docs, ordered=False)
                saved_count = len(data_docs)
            except BulkWriteError as bwe:
                saved_count = bwe.details['nInserted']
            except Exception as e:
                print(f"❌ Critical Error Saving FILES_DATA: {e}")
                return 0, count + pre_duplicate_count

            if saved_count > 0:
                try:
                    await self.search_col.insert_many(search_docs, ordered=False)
                except Exception as e:
                    print(f"⚠️ Search Index Error: {e}")
                
        return saved_count, pre_duplicate_count

    async def get_file_details(self, link_id):
        return await self.data_col.find_one({'_id': int(link_id)})

    # ==================================================================
    # ⚡ OPTIMIZED SEARCH WITH DB FILTERING
    # ==================================================================
    async def get_search_results(self, query, file_type=None, lang=None, quality=None, year=None, size_range=None):
        try:
            # Stage 1: Search ($search with Index)
            # Ensure "default" index exists on Atlas
            must_clauses = []
            words = query.split()
            for word in words:
                must_clauses.append({
                    "text": {
                        "query": word,
                        "path": ["file_name", "caption"],
                        "fuzzy": {"maxEdits": 1}
                    }
                })

            pipeline = []
            pipeline.append({
                "$search": {
                    "index": "default", 
                    "compound": {"must": must_clauses}
                }
            })

            # Stage 2: Filter ($match)
            match_filters = {}
            
            if file_type and file_type != "none":
                # Convert to match DB storage (lowercase usually)
                capital_type = "video" if file_type.lower() == "video" else "document"
                match_filters["file_type"] = capital_type

            if lang and lang != "none":
                match_filters["file_name"] = {"$regex": lang, "$options": "i"}

            if quality and quality != "none":
                match_filters["file_name"] = {"$regex": quality, "$options": "i"}
            
            if year and year != "none":
                match_filters["file_name"] = {"$regex": str(year)}

            if size_range and size_range != "none":
                MB_500 = 500 * 1024 * 1024
                GB_1 = 1024 * 1024 * 1024
                GB_2 = 2 * 1024 * 1024 * 1024
                
                if size_range == "min500":
                    match_filters["file_size"] = {"$lt": MB_500}
                elif size_range == "500-1gb":
                    match_filters["file_size"] = {"$gte": MB_500, "$lt": GB_1}
                elif size_range == "1gb-2gb":
                    match_filters["file_size"] = {"$gte": GB_1, "$lt": GB_2}
                elif size_range == "max2gb":
                    match_filters["file_size"] = {"$gte": GB_2}

            if match_filters:
                pipeline.append({"$match": match_filters})

            pipeline.append({"$limit": 100}) 

            cursor = self.search_col.aggregate(pipeline)
            files = await cursor.to_list(length=100)
            return files
            
        except Exception as e:
            # Fallback: Regex Search (Slower but works without Atlas Search Index)
            # Useful for local testing or if index is missing
            print(f"⚠️ Index Search Failed: {e}. Switching to Fallback.")
            safe_query = re.escape(query)
            regex = re.compile(safe_query, re.IGNORECASE)
            
            fallback_filter = {"$or": [{"file_name": regex}, {"caption": regex}]}
            
            # Apply basic DB filters where possible
            if file_type and file_type != "none": 
                fallback_filter["file_type"] = "video" if file_type.lower() == "video" else "document"

            cursor = self.search_col.find(fallback_filter)
            cursor.sort('$natural', -1)
            files = await cursor.to_list(length=100)
            
            # Manually filter the rest in Python
            final_files = []
            for f in files:
                fname = f.get('file_name', '').lower()
                fsize = f.get('file_size', 0)
                
                if lang and lang != "none" and lang.lower() not in fname: continue
                if quality and quality != "none" and quality.lower() not in fname: continue
                if year and year != "none" and str(year) not in fname: continue
                
                if size_range == "min500" and fsize >= 500*1024*1024: continue
                elif size_range == "500-1gb" and not (500*1024*1024 <= fsize < 1024*1024*1024): continue
                elif size_range == "1gb-2gb" and not (1024*1024*1024 <= fsize < 2*1024*1024*1024): continue
                elif size_range == "max2gb" and fsize < 2*1024*1024*1024: continue
                
                final_files.append(f)
                
            return final_files

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
                "file_chat_id": file.get('chat_id'),
                "file_type": file.get('file_type', 'document')
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
