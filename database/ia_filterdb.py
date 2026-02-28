import logging
import re
import datetime
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError
from pymongo import ReturnDocument
from info import DATABASE_URI, DATABASE_NAME

logger = logging.getLogger(__name__)

# ✅ SMART LANGUAGE MAPPING
LANG_MAP = {
    "English": "English|Eng",
    "Hindi": "Hindi|Hin",
    "Tamil": "Tamil|Tam",
    "Telugu": "Telugu|Tel",
    "Malayalam": "Malayalam|Mal",
    "Kannada": "Kannada|Kan",
    "Bengali": "Bengali|Ben",
    "Punjabi": "Punjabi|Pun",
    "Marathi": "Marathi|Mar",
    "Gujarati": "Gujarati|Guj",
    "Urdu": "Urdu"
}

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
            await self.search_col.create_index("search_text") # ✅ Naya index fast search ke liye
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
    # ✅ HIGHLY OPTIMIZED CLEAN_TEXT
    # ==================================================================
    @staticmethod
    def clean_text(text):
        if not text:
            return ""

        # Step 1: Remove HTML Tags (Fixes <b>, <i>, <code> tags)
        text = re.sub(r"<[^>]+>", "", text)

        # Step 2: EXTENSION CUT-OFF 
        ext_regex = r"(?i)(.*?(?:\.(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)|\b(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)\b))"
        match = re.search(ext_regex, text, flags=re.DOTALL)
        if match:
            text = match.group(1)

        # Step 3: Remove Brackets ONLY if they contain @, t.me, or URLs
        text = re.sub(r"\[[^\]]*(?:@|t\.me/|https?://|www\.)[^\]]*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\([^)]*(?:@|t\.me/|https?://|www\.)[^)]*\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\{[^}]*(?:@|t\.me/|https?://|www\.)[^}]*\}", "", text, flags=re.IGNORECASE)

        # Step 4: Remove standalone URLs and Handles
        text = re.sub(r"(https?://\S+|www\.\S+|t\.me/\S+|@\w+)", "", text, flags=re.IGNORECASE)

        # Step 5: Invisible Characters
        text = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u202a-\u202e]", "", text)

        # ==========================================================
        # 🔥 STEP 6: STANDARDIZE TAGS & EXPAND RANGES
        # ==========================================================
        
        # 1. Alias Normalization (Part, Vol, Volume, Chapter -> S)
        text = re.sub(r"(?i)\b(part|vol|volume|chapter)\s*(\d+)\b", r"S\2", text)
        
        # 2. XxY format standardization (e.g., 1x05 -> S1 E05)
        text = re.sub(r"(?i)\b(\d{1,2})\s*x\s*(\d{1,4})\b", r"S\1 E\2", text)
        
        # 3. Standardize Words to S and E
        text = re.sub(r"(?i)\b(?:season|s)\s*(\d+)\b", r"S\1", text)
        text = re.sub(r"(?i)\b(?:episode|ep|e)\s*(\d+)\b", r"E\1", text)
        
        # 4. Expand Season Ranges (e.g., S1-3 -> S01 S02 S03)
        def expand_season(match):
            start, end = int(match.group(1)), int(match.group(2))
            if start > end or end - start > 50: return match.group(0)
            return " ".join([f"S{str(i).zfill(2)}" for i in range(start, end + 1)])
        text = re.sub(r"(?i)\bS(\d+)\s*(?:-|to)\s*(?:S)?(\d+)\b", expand_season, text)
        
        # 5. Expand Episode Ranges (e.g., E05-08 -> E05 E06 E07 E08)
        def expand_episode(match):
            start, end = int(match.group(1)), int(match.group(2))
            if start > end or end - start > 200: return match.group(0)
            return " ".join([f"E{str(i).zfill(2)}" for i in range(start, end + 1)])
        text = re.sub(r"(?i)\bE(\d+)\s*(?:-|to)\s*(?:E)?(\d+)\b", expand_episode, text)
        
        # 6. Zero-Padding (e.g., S1 -> S01, E5 -> E05)
        text = re.sub(r"(?i)\bS(\d+)\b", lambda m: f"S{m.group(1).zfill(2)}", text)
        text = re.sub(r"(?i)\bE(\d+)\b", lambda m: f"E{m.group(1).zfill(2)}", text)

        # ==========================================================

        # Step 7: Spam Words and Tags
        spam_and_tags = [
            r"download", r"full movie", r"free", r"watch online", r"join",
            r"esub", r"hc-esub", r"x264", r"x265", r"code"
        ]
        pattern = r"\b(" + "|".join(spam_and_tags) + r")\b"
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # Step 8: Emojis, Symbols, Punctuation
        text = re.sub(r"[^\w\s:()\[\]{}\-]|_", " ", text)

        # Step 9: Space Management
        text = re.sub(r"\s+", " ", text)

        return text.strip()

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
            display_name = self.clean_text(media.file_name)
            if not display_name: display_name = "Unknown File"

            caption = message.caption.html if message.caption else None
            cap_text = ""
            if caption:
                caption = self.clean_text(caption)
                cap_text = caption

            # ==========================================================
            # ✅ GENERATE ALIASES FOR SEASON & EPISODE
            # ==========================================================
            variations = []
            
            seasons = re.findall(r"(?i)\bS(\d+)\b", display_name)
            for s in seasons:
                s_num = int(s)
                s_pad = str(s_num).zfill(2)
                variations.append(f"s{s_num} s{s_pad} so{s_num} season{s_num} s{s_num}season{s_num}")

            episodes = re.findall(r"(?i)\bE(\d+)\b", display_name)
            for e in episodes:
                e_num = int(e)
                e_pad = str(e_num).zfill(2)
                variations.append(f"e{e_num} e{e_pad} eo{e_num} ep{e_num} episode{e_num} e{e_num}episode{e_num}")

            variation_text = " ".join(variations)

            # ==========================================================
            # ✅ SPACELESS GENERATION & MASTER SEARCH TEXT
            # ==========================================================
            spaceless_name = display_name.replace(" ", "").replace("-", "").replace(".", "")
            spaceless_cap = cap_text.replace(" ", "").replace("-", "").replace(".", "")
            master_search_text = f"{display_name} {spaceless_name} {spaceless_cap} {variation_text}".lower()
            # ==========================================================

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
                'file_name': display_name,
                'file_size': media.file_size, 
                'caption': caption,
                'search_text': master_search_text,
                'link_id': current_id,
                'chat_id': message.chat.id,
                'file_type': file_type 
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
    # ⚡ OPTIMIZED SMART REGEX SEARCH WITH SORTING
    # ==================================================================
    async def get_search_results(self, query, file_type=None, lang=None, quality=None, year=None, size_range=None, sort="relevance"):
        try:
            # ==========================================================
            # ✅ QUERY PROCESSING (SMART REGEX SEARCH)
            # ==========================================================
            and_clauses = []
            words = query.split()
            
            for word in words:
                char_array = [re.escape(c) for c in word]
                smart_regex = r"[\s\W]*".join(char_array)
                
                and_clauses.append({
                    "$or": [
                        {"file_name": {"$regex": smart_regex, "$options": "i"}},
                        {"search_text": {"$regex": smart_regex, "$options": "i"}},
                        {"caption": {"$regex": smart_regex, "$options": "i"}}
                    ]
                })

            pipeline = []
            
            # Stage 1: Match Filters
            match_filters = {"$and": and_clauses} if and_clauses else {}
            
            if file_type and file_type != "none":
                capital_type = "video" if file_type.lower() == "video" else "document"
                match_filters["file_type"] = capital_type

            if lang and lang != "none":
                pattern = LANG_MAP.get(lang, lang)
                if "$and" not in match_filters:
                    match_filters["$and"] = []
                match_filters["$and"].append({
                    "$or": [
                        {"file_name": {"$regex": pattern, "$options": "i"}},
                        {"search_text": {"$regex": pattern, "$options": "i"}},
                        {"caption": {"$regex": pattern, "$options": "i"}}
                    ]
                })

            if quality and quality != "none":
                if "$and" not in match_filters:
                    match_filters["$and"] = []
                match_filters["$and"].append({
                    "$or": [
                        {"file_name": {"$regex": quality, "$options": "i"}},
                        {"search_text": {"$regex": quality, "$options": "i"}},
                        {"caption": {"$regex": quality, "$options": "i"}}
                    ]
                })
            
            if year and year != "none":
                match_filters["file_name"] = {"$regex": str(year)}

            if size_range and size_range != "none":
                MB_500 = 500 * 1024 * 1024
                GB_1 = 1024 * 1024 * 1024
                GB_2 = 2 * 1024 * 1024 * 1024
                
                if size_range == "min500": match_filters["file_size"] = {"$lt": MB_500}
                elif size_range == "500-1gb": match_filters["file_size"] = {"$gte": MB_500, "$lt": GB_1}
                elif size_range == "1gb-2gb": match_filters["file_size"] = {"$gte": GB_1, "$lt": GB_2}
                elif size_range == "max2gb": match_filters["file_size"] = {"$gte": GB_2}

            pipeline.append({"$match": match_filters})

            # ✅ SORTING LOGIC
            if sort == "new":
                pipeline.append({"$sort": {"_id": -1}}) # Descending ID = Newest
            elif sort == "old":
                pipeline.append({"$sort": {"_id": 1}}) # Ascending ID = Oldest
            elif sort == "large":
                pipeline.append({"$sort": {"file_size": -1}}) # High to Low
            elif sort == "small":
                pipeline.append({"$sort": {"file_size": 1}}) # Low to High
            else:
                pipeline.append({"$sort": {"_id": -1}}) # Default relevance replaced by Newest

            pipeline.append({"$limit": 100}) 

            cursor = self.search_col.aggregate(pipeline)
            files = await cursor.to_list(length=100)
            return files
            
        except Exception as e:
            print(f"⚠️ Index Search Failed: {e}. Switching to Fallback.")
            
            # ✅ Apply Same Smart Regex Logic in Fallback
            and_clauses_fallback = []
            for word in query.split():
                char_array = [re.escape(c) for c in word]
                smart_regex = r"[\s\W]*".join(char_array)
                and_clauses_fallback.append({
                    "$or": [
                        {"file_name": {"$regex": smart_regex, "$options": "i"}},
                        {"search_text": {"$regex": smart_regex, "$options": "i"}},
                        {"caption": {"$regex": smart_regex, "$options": "i"}}
                    ]
                })
            
            fallback_filter = {"$and": and_clauses_fallback} if and_clauses_fallback else {}
            if file_type and file_type != "none": 
                fallback_filter["file_type"] = "video" if file_type.lower() == "video" else "document"

            cursor = self.search_col.find(fallback_filter)
            
            # Manual Sort for Fallback
            if sort == "new": cursor.sort('_id', -1)
            elif sort == "old": cursor.sort('_id', 1)
            elif sort == "large": cursor.sort('file_size', -1)
            elif sort == "small": cursor.sort('file_size', 1)
            else: cursor.sort('_id', -1)

            files = await cursor.to_list(length=100)
            
            final_files = []
            for f in files:
                fname = f.get('file_name', '').lower()
                caption = (f.get('caption') or "").lower()
                search_txt = f.get('search_text', '').lower()
                full_text = fname + " " + caption + " " + search_txt
                fsize = f.get('file_size', 0)
                
                if lang and lang != "none":
                    pattern = LANG_MAP.get(lang, lang).lower()
                    if not re.search(pattern, full_text): continue

                if quality and quality != "none" and quality.lower() not in full_text: continue
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
