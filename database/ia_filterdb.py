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
            await self.search_col.create_index("search_text") # ✅ New Index
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
    # 🧠 SMART INDEXING HELPERS
    # ==================================================================
    @staticmethod
    def clean_text(text):
        if not text: 
            return ""
        
        # 1. Cleanup: Remove URLs and Usernames
        text = re.sub(r'(https?://\S+|www\.\S+)', '', text)
        text = re.sub(r'@[a-zA-Z0-9_]+', '', text)
        
        # 2. Extension Removal (from the end only)
        text = re.sub(r'(?i)\.(mkv|mp4|avi|webm|m4v|flv|zip|rar|tar|pdf)$', '', text)
        
        # 3. Removal: Replace dots, underscores, brackets, punctuation with spaces
        text = re.sub(r'[._\(\)\[\]{}-]', ' ', text)
        
        # 4. Roman Numeral Fix (Append digits to standalone I, II, III, IV, V)
        roman_map = {'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5'}
        def replace_roman(match):
            roman = match.group(0)
            return f"{roman} {roman_map[roman.upper()]}"
            
        text = re.sub(r'(?i)\b(I|II|III|IV|V)\b', replace_roman, text)
        
        # 5. Final Whitespace Cleanup
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def parse_file_details(text):
        details = {'quality': '', 'year': '', 'episodes': '', 'languages': ''}
        text_lower = text.lower()
        
        # 1. Quality Extraction
        q_matches = re.findall(r'\b(480p|720p|1080p|2160p|4k)\b', text_lower)
        if q_matches: details['quality'] = ' '.join(set(q_matches))
        
        # 2. Year Extraction (19xx - 20xx)
        y_matches = re.findall(r'\b((?:19|20)\d{2})\b', text_lower)
        if y_matches: details['year'] = ' '.join(set(y_matches))
        
        # 3. Episode Expansion (Detects S01E01, S1 E1)
        ep_vars = []
        ep_regex = re.finditer(r'\bs(?:eason)?\s*(\d{1,2})\s*e(?:pisode)?\s*(\d{1,2})\b', text_lower)
        for m in ep_regex:
            s, e = m.groups()
            s_int, e_int = int(s), int(e)
            ep_vars.extend([f"e{e_int}", f"e{e}", f"season {s_int} episode {e_int}"])
        details['episodes'] = ' '.join(set(ep_vars))
        
        # 4. Language & Multi-Audio Logic
        langs = ["hindi", "english", "tamil", "telugu", "malayalam", "kannada", "bengali", "marathi", "punjabi", "gujarati", "urdu"]
        found_langs = [l for l in langs if l in text_lower]
        
        # Multi-Audio Logic
        if any(w in text_lower for w in ['multi', 'dual', 'org']):
            if 'hindi' not in found_langs:
                found_langs.append('hindi')
                
        details['languages'] = ' '.join(set(found_langs))
        return details

    # ==================================================================
    # 💾 MASTER PIPELINE SAVE LOGIC
    # ==================================================================
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
        seen_in_batch = set() # ✅ FIX: Ek hi list me aane wali duplicate files ko block karega
        pre_duplicate_count = 0
        
        for media, msg in items:
            if media.file_unique_id not in existing_unique_ids and media.file_unique_id not in seen_in_batch:
                new_items.append((media, msg))
                seen_in_batch.add(media.file_unique_id)
            else:
                pre_duplicate_count += 1
        
        if not new_items: return 0, pre_duplicate_count 
            
        count = len(new_items)
        end_sequence = await self.get_next_sequence_value("file_id_counter", increment=count)
        if not end_sequence: return 0, 0
        
        start_sequence = end_sequence - count + 1
        
        data_docs = []
        search_docs = []
        current_id = start_sequence
        
        for media, message in new_items:
            raw_filename = media.file_name or "Unknown File"
            raw_caption = message.caption.html if message.caption else ""
            
            # --- STEP A: Name Swapping (Display Logic) ---
            clean_name = self.clean_text(raw_filename)
            clean_caption = self.clean_text(raw_caption)
            
            display_name = clean_name
            
            # Check for generic filename signatures
            generic_patterns = ("vid_", "img_", "tg_")
            is_generic = raw_filename.lower().startswith(generic_patterns) or len(clean_name) < 5
            
            if is_generic and clean_caption:
                display_name = clean_caption

            if not display_name:
                display_name = "Unknown File"

            # --- STEP B: Spaceless Generation ---
            spaceless_name = display_name.replace(" ", "")

            # --- STEP C: Smart Merge (Deduplication) ---
            name_words = set(display_name.lower().split())
            caption_words = set(clean_caption.lower().split())
            
            # Extract words present in caption but missing in filename
            extra_words = caption_words - name_words
            extra_caption_text = " ".join(extra_words)

            # --- STEP D: Master Search Field Construction ---
            combined_raw_text = display_name + " " + clean_caption
            file_details = self.parse_file_details(combined_raw_text)
            
            search_components = [
                display_name.lower(),
                spaceless_name.lower(),
                file_details['episodes'],
                file_details['year'],
                file_details['quality'],
                file_details['languages'],
                extra_caption_text
            ]
            
            # Merge components and normalize spaces
            master_search_text = " ".join(filter(None, search_components))
            master_search_text = re.sub(r'\s+', ' ', master_search_text).strip()

            file_type = "video" if message.video else "document"

            # --- STEP E: Database Operations ---
            data_docs.append({
                '_id': current_id,
                'msg_id': message.id,
                'chat_id': message.chat.id,
                'file_id': media.file_id,
                'file_unique_id': media.file_unique_id,
                'file_type': file_type 
            })
            
            search_docs.append({
                'file_name': display_name,         # Elegant Display Name
                'search_text': master_search_text, # Hidden Meta-text for Smart Search
                'caption': clean_caption,          # Cleaned caption
                'file_size': media.file_size, 
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
                return 0, pre_duplicate_count

            if saved_count > 0:
                try:
                    await self.search_col.insert_many(search_docs, ordered=False)
                except BulkWriteError:
                    pass 
                except Exception as e:
                    print(f"⚠️ Search Index Error: {e}")
                
        return saved_count, pre_duplicate_count

    # ==================================================================
    # ⚡ OPTIMIZED SEARCH WITH SORTING
    # ==================================================================
    async def get_search_results(self, query, file_type=None, lang=None, quality=None, year=None, size_range=None, sort="relevance"):
        try:
            must_clauses = []
            words = query.split()
            for word in words:
                must_clauses.append({
                    "text": {
                        "query": word,
                        "path": ["file_name", "search_text", "caption"], 
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
                capital_type = "video" if file_type.lower() == "video" else "document"
                match_filters["file_type"] = capital_type

            if lang and lang != "none":
                pattern = LANG_MAP.get(lang, lang)
                match_filters["$or"] = [
                    {"file_name": {"$regex": pattern, "$options": "i"}},
                    {"search_text": {"$regex": pattern, "$options": "i"}}
                ]

            if quality and quality != "none":
                match_filters["$or"] = [
                    {"file_name": {"$regex": quality, "$options": "i"}},
                    {"search_text": {"$regex": quality, "$options": "i"}}
                ]
            
            if year and year != "none":
                match_filters["search_text"] = {"$regex": str(year)}

            if size_range and size_range != "none":
                MB_500 = 500 * 1024 * 1024
                GB_1 = 1024 * 1024 * 1024
                GB_2 = 2 * 1024 * 1024 * 1024
                
                if size_range == "min500": match_filters["file_size"] = {"$lt": MB_500}
                elif size_range == "500-1gb": match_filters["file_size"] = {"$gte": MB_500, "$lt": GB_1}
                elif size_range == "1gb-2gb": match_filters["file_size"] = {"$gte": GB_1, "$lt": GB_2}
                elif size_range == "max2gb": match_filters["file_size"] = {"$gte": GB_2}

            if match_filters:
                pipeline.append({"$match": match_filters})

            # ✅ SORTING LOGIC
            if sort == "new": pipeline.append({"$sort": {"_id": -1}})
            elif sort == "old": pipeline.append({"$sort": {"_id": 1}})
            elif sort == "large": pipeline.append({"$sort": {"file_size": -1}})
            elif sort == "small": pipeline.append({"$sort": {"file_size": 1}})

            pipeline.append({"$limit": 100}) 

            cursor = self.search_col.aggregate(pipeline)
            files = await cursor.to_list(length=100)
            return files
            
        except Exception as e:
            print(f"⚠️ Index Search Failed: {e}. Switching to Smart Word-by-Word Fallback.")
            
            # ✅ ULTRA SMART REGEX: Spiderman -> s\s*p\s*i\s*d\s*e\s*r\s*m\s*a\s*n
            # Ye "Spiderman" aur "Spider Man" dono ko automatically match kar lega!
            words = query.split()
            and_clauses = []
            
            for word in words:
                # Har character ke beech me optional space (\s*) laga do
                char_list = [re.escape(ch) for ch in word]
                smart_regex_str = r"\s*".join(char_list)
                regex = re.compile(smart_regex_str, re.IGNORECASE)
                
                and_clauses.append({
                    "$or": [
                        {"search_text": regex},
                        {"file_name": regex}, 
                        {"caption": regex}
                    ]
                })

            fallback_filter = {"$and": and_clauses} if and_clauses else {}
            
            if file_type and file_type != "none": 
                fallback_filter["file_type"] = "video" if file_type.lower() == "video" else "document"

            cursor = self.search_col.find(fallback_filter)
            
            if sort == "new": cursor.sort('_id', -1)
            elif sort == "old": cursor.sort('_id', 1)
            elif sort == "large": cursor.sort('file_size', -1)
            elif sort == "small": cursor.sort('file_size', 1)
            else: cursor.sort('$natural', -1)

            files = await cursor.to_list(length=100)
            
            final_files = []
            for f in files:
                fname = f.get('file_name', '').lower()
                meta = f.get('search_text', '').lower()
                full_text = fname + " " + meta
                fsize = f.get('file_size', 0)
                
                if lang and lang != "none":
                    pattern = LANG_MAP.get(lang, lang).lower()
                    if not re.search(pattern, full_text): continue

                if quality and quality != "none" and quality.lower() not in full_text: continue
                if year and year != "none" and str(year) not in full_text: continue
                
                if size_range == "min500" and fsize >= 500*1024*1024: continue
                elif size_range == "500-1gb" and not (500*1024*1024 <= fsize < 1024*1024*1024): continue
                elif size_range == "1gb-2gb" and not (1024*1024*1024 <= fsize < 2*1024*1024*1024): continue
                elif size_range == "max2gb" and fsize < 2*1024*1024*1024: continue
                
                final_files.append(f)
                
            return final_files

    async def get_search_query(self, search_id):
        try:
            return await self.temp_searches.find_one({"_id": int(search_id)})
        except Exception as e:
            print(f"❌ CRITICAL DB ERROR (Get): {e}")
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

    async def get_file_details(self, link_id):
        return await self.data_col.find_one({'_id': int(link_id)})

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
