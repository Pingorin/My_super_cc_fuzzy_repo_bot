import logging
import re
import uuid
import secrets 
import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError
from info import DATABASE_URI, DATABASE_NAME

logger = logging.getLogger(__name__)

class MediaDB:
    def __init__(self, uri, database_name):
        # ✅ Connection: Using DATABASE_URI
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        
        self.data_col = self.db.files_data   
        self.search_col = self.db.files_search 
        self.counters = self.db.counters
        
        # ✅ Collection for Site Mode Cache (Web View)
        self.search_cache = self.db.search_cache 

        # ✅ NEW: Collection for Search Sessions (Button Pagination Fix)
        self.search_results = self.db.search_results

    async def ensure_indexes(self):
        # Regular indexes for fallback search
        await self.search_col.create_index("file_name")
        await self.search_col.create_index("caption")
        await self.search_col.create_index("link_id")
        await self.data_col.create_index("file_unique_id", unique=True)
        
        # ✅ TTL Index for Site Mode (Auto-delete cache after 1 hour)
        await self.search_cache.create_index("created_at", expireAfterSeconds=3600)

        # ✅ NEW: TTL Index for Search Results (Auto-delete after 48 Hours)
        # 172800 seconds = 48 hours
        await self.search_results.create_index("created_at", expireAfterSeconds=172800)

    async def get_next_sequence_value(self, sequence_name, increment=1):
        doc = await self.counters.find_one_and_update(
            {"_id": sequence_name},
            {"$inc": {"sequence_value": increment}}, 
            upsert=True,
            return_document=True
        )
        return doc["sequence_value"]

    # --- 🧹 TEXT CLEANER HELPER ---
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

            # Detect MIME Type for Filtering
            mime_type = getattr(media, "mime_type", "document/unknown")

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
                'mime_type': mime_type, # ✅ Save MIME Type for filtering
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

    # ==================================================================
    # 🔍 SEARCH LOGIC (Updated for File Type Filter)
    # ==================================================================
    async def get_search_results(self, query, file_type=None, max_results=100):
        """
        query: Text to search
        file_type: "video" | "document" | None (For filtering)
        """
        try:
            # 1. Prepare Regex for Text Search
            regex = re.compile(re.escape(query), re.IGNORECASE)

            # 2. Prepare Filter Query (MIME Type)
            filter_query = {}
            if file_type == "video":
                # Select files where mime_type contains 'video'
                filter_query = {"mime_type": {"$regex": "video", "$options": "i"}}
            elif file_type == "document":
                # Select files where mime_type does NOT contain 'video'
                filter_query = {"mime_type": {"$not": {"$regex": "video", "$options": "i"}}}

            # 3. Combine Queries
            # If a filter is applied, use $and. Otherwise, use standard $or.
            if file_type:
                mongo_query = {
                    "$and": [
                        {"$or": [{"file_name": regex}, {"caption": regex}]},
                        filter_query
                    ]
                }
            else:
                mongo_query = {"$or": [{"file_name": regex}, {"caption": regex}]}

            # 4. Execute Query
            cursor = self.search_col.find(mongo_query)
            cursor.sort('$natural', -1) # Sort by newest
            
            return await cursor.to_list(length=max_results)
            
        except Exception as e:
            print(f"DB Search Error: {e}")
            return []

    async def total_files_count(self):
        return await self.data_col.count_documents({})

    async def get_db_size(self):
        try:
            stats = await self.db.command("dbstats")
            return stats['dataSize']
        except:
            return 0

    # ==================================================================
    # 🌍 SITE MODE METHODS (Save & Retrieve Cache)
    # ==================================================================

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

    # ==================================================================
    # 🔑 SEARCH SESSION METHODS (For Button Pagination Fix)
    # ==================================================================

    async def save_search_result(self, query, files):
        """
        Saves the search result to DB and returns a unique ID (Key).
        Used to fix BUTTON_DATA_INVALID error in buttons.
        """
        # Generate a short 6-char URL-safe key
        unique_id = secrets.token_urlsafe(6)
        
        # Simplify file data to save DB space
        simplified_files = []
        for file in files:
            simplified_files.append({
                'file_name': file.get('file_name'),
                'file_size': file.get('file_size'),
                'link_id': file.get('link_id'),
                'caption': file.get('caption', None)
            })

        await self.search_results.insert_one({
            "_id": unique_id,
            "query": query,
            "files": simplified_files,
            "created_at": datetime.datetime.utcnow()
        })
        
        return unique_id

    async def get_search_session(self, unique_id):
        """
        Retrieves the saved files list using the Unique ID.
        """
        return await self.search_results.find_one({"_id": unique_id})

# Initialize with DATABASE_URI
Media = MediaDB(DATABASE_URI, DATABASE_NAME)
