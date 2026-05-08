import logging
import re
import datetime
import uuid
import html  
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError, OperationFailure
from pymongo import ReturnDocument, ASCENDING
import info 
from info import DATABASE_URI, DATABASE_NAME

# Safe Import for Secondary and Tertiary DBs
DATABASE_URI_2 = getattr(info, "DATABASE_URI_2", None)
DATABASE_URI_3 = getattr(info, "DATABASE_URI_3", None)

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
    "Urdu": "Urdu",
    "Dual Audio": "Dual Audio|Dual-Audio",
    "Multi Audio": "Multi Audio|Multi-Audio"
}

class MediaDB:
    def __init__(self, uri1, uri2, uri3, database_name):
        # 🟢 PRIMARY DATABASE (DB 1 - The Master)
        self._client1 = AsyncIOMotorClient(uri1)
        self.db1 = self._client1[database_name] 
        self.data_col1 = self.db1.files_data   
        self.search_col1 = self.db1.files_search 
        
        # Bot ka "Dimaag" (Counters, Settings aur Cache) hamesha DB 1 par rahega!
        self.counters = self.db1.counters
        self.search_cache = self.db1.search_cache 
        self.temp_searches = self.db1.temp_searches
        self.bot_settings = self.db1.bot_settings 

        # 🔵 SECONDARY DATABASE (DB 2)
        self.has_db2 = bool(uri2 and len(uri2) > 10)
        if self.has_db2:
            self._client2 = AsyncIOMotorClient(uri2)
            self.db2 = self._client2[database_name] 
            self.data_col2 = self.db2.files_data
            self.search_col2 = self.db2.files_search
        else:
            self.db2 = None

        # 🟣 TERTIARY DATABASE (DB 3 - New Storage)
        self.has_db3 = bool(uri3 and len(uri3) > 10)
        if self.has_db3:
            self._client3 = AsyncIOMotorClient(uri3)
            self.db3 = self._client3[database_name] 
            self.data_col3 = self.db3.files_data
            self.search_col3 = self.db3.files_search
        else:
            self.db3 = None

    async def ensure_indexes(self):
        try:
            # 🔥 TTL BUG FIX: Purane time wale rules ko pehle hatayenge taaki clash na ho
            try: await self.search_cache.drop_index("created_at_1")
            except Exception: pass
            try: await self.temp_searches.drop_index("created_at_1")
            except Exception: pass

            # DB 1 Indexes (Faltu TEXT, quality, languages hata diye)
            await self.search_col1.create_index("link_id")
            await self.data_col1.create_index("file_id") # ✅ Fast Scan Index
            await self.data_col1.create_index("file_unique_id", unique=True)

            # Naye time wale rules banayenge
            await self.search_cache.create_index("created_at", expireAfterSeconds=3600)
            await self.temp_searches.create_index("created_at", expireAfterSeconds=43200)
            
            # 🔥 DB 2 Indexes
            if self.has_db2:
                await self.search_col2.create_index("link_id")
                await self.data_col2.create_index("file_id")
                await self.data_col2.create_index("file_unique_id", unique=True)

            # 🔥 DB 3 Indexes
            if self.has_db3:
                await self.search_col3.create_index("link_id")
                await self.data_col3.create_index("file_id")
                await self.data_col3.create_index("file_unique_id", unique=True)
            
            print("✅ Multi-Database Indexes Created Successfully! (Atlas Search Ready)")
        except Exception as e:
            print(f"❌ Error Creating Indexes: {e}")

    # 🔥 UNIQUE COUNTER (Sabhi files ko ek line me rakhega)
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
            return None

    async def update_search_cache(self, search_id, files):
        try:
            await self.temp_searches.update_one(
                {"_id": int(search_id)},
                {"$set": {"files": files}}
            )
        except Exception as e:
            pass

    async def get_search_query(self, search_id):
        try:
            return await self.temp_searches.find_one({"_id": int(search_id)})
        except Exception as e:
            return None

    # 🔥 MANUAL OVERRIDE (Set Active DB) 🔥
    async def get_active_index_db(self):
        try:
            doc = await self.bot_settings.find_one({"_id": "active_db"})
            if doc: return doc.get("db_num", 1)
        except: pass
        
        if self.has_db3: return 3
        if self.has_db2: return 2
        return 1

    async def set_active_index_db(self, db_num):
        await self.bot_settings.update_one(
            {"_id": "active_db"}, 
            {"$set": {"db_num": int(db_num)}}, 
            upsert=True
        )

    @staticmethod
    def clean_text(text):
        if not text: return ""
        text = html.unescape(text)
        text = re.sub(r"<[^>]+>", "", text)
        
        ext_regex = r"(?i)(.*?(?:\.(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)|\b(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)\b))"
        match = re.search(ext_regex, text, flags=re.DOTALL)
        if match: text = match.group(1)

        while True:
            old_text = text
            text = re.sub(r"^(?:\[.*?\]|\(.*?\)|\{.*?\}|<.*?>)\s*", "", text).strip()
            text = re.sub(r"^[^\w\s&]+\s*", "", text).strip()
            if text == old_text:
                break

        promo_patterns = r"@|t\.me/|https?://|www\.\w+|\w+\.(?:com|in|vip|org|net|me|xyz|site|cc|to|club|tech|link|app|click|store|hd)\b"
        text = re.sub(r"\[[^\]]*(?:" + promo_patterns + r")[^\]]*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\([^)]*(?:" + promo_patterns + r")[^)]*\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\{[^}]*(?:" + promo_patterns + r")[^}]*\}", "", text, flags=re.IGNORECASE)
        text = re.sub(r"(https?://\S+|www\.\S+|t\.me/\S+|@\w+|\b\w+\.(?:com|in|vip|org|net|me|xyz|site|cc|to|club|tech|link|app|click|store|hd)\b)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u202a-\u202e]", "", text)

        spam_and_tags = [r"download", r"full movie", r"free", r"watch online", r"join", r"esub", r"hc-esub", r"x264", r"x265", r"code"]
        text = re.sub(r"\b(" + "|".join(spam_and_tags) + r")\b", "", text, flags=re.IGNORECASE)
        
        text = re.sub(r"[^\w\s:()\[\]{}\-&]|_", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def parse_metadata(text):
        if not text: return {"quality": [], "languages": [], "year": []}
        
        text = html.unescape(text)
        cleaned_title = text
        metadata = {"quality": set(), "languages": set(), "year": set()}

        res_pattern = r"(?i)\b(480p|720p|1080p|2160p|4k|uhd)\b"
        for m in re.finditer(res_pattern, cleaned_title):
            val = m.group(1).lower()
            if val in ['4k', 'uhd']: val = '2160p'
            metadata['quality'].add(val)
        cleaned_title = re.sub(res_pattern, "", cleaned_title)

        lang_map = {
            'hin': 'Hindi', 'hindi': 'Hindi', 'tam': 'Tamil', 'tamil': 'Tamil', 'tel': 'Telugu', 'telugu': 'Telugu',
            'mal': 'Malayalam', 'malayalam': 'Malayalam', 'kan': 'Kannada', 'kannada': 'Kannada', 'eng': 'English', 'english': 'English',
            'multi': 'Multi Audio', 'dual': 'Dual Audio'
        }
        lang_pattern = r"(?i)\b(hindi|hin|tamil|tam|telugu|tel|malayalam|mal|kannada|kan|english|eng|multi[\s\-]?audio|dual[\s\-]?audio)\b"
        for m in re.finditer(lang_pattern, cleaned_title):
            val = m.group(1).lower().replace('-', ' ').replace('audio', '').strip()
            for key, mapped in lang_map.items():
                if val in mapped.lower().split('|'): metadata['languages'].add(key)
        cleaned_title = re.sub(lang_pattern, "", cleaned_title)

        year_pattern = r"\b(19\d{2}|20\d{2})\b"
        for m in re.finditer(year_pattern, cleaned_title): metadata['year'].add(m.group(1))
        
        return {"quality": list(metadata["quality"]), "languages": list(metadata["languages"]), "year": list(metadata["year"])}

    async def save_batch(self, items):
        if not items: return 0, 0 
        
        unique_batch_items = []
        batch_ids = set()
        for media, msg in items:
            if media.file_unique_id not in batch_ids:
                batch_ids.add(media.file_unique_id)
                unique_batch_items.append((media, msg))

        unique_ids = [media.file_unique_id for media, msg in unique_batch_items]
        
        # 🔥 SMART UPDATE MAPPING
        existing_map = {}
        link_ids_to_check = []
        
        try:
            existing_docs_1 = await self.data_col1.find({"file_unique_id": {"$in": unique_ids}}).to_list(length=len(unique_batch_items))
            for doc in existing_docs_1: 
                existing_map[doc['file_unique_id']] = {'db': 1, 'link_id': doc['_id']}
                link_ids_to_check.append(doc['_id'])
            
            if self.has_db2:
                existing_docs_2 = await self.data_col2.find({"file_unique_id": {"$in": unique_ids}}).to_list(length=len(unique_batch_items))
                for doc in existing_docs_2: 
                    existing_map[doc['file_unique_id']] = {'db': 2, 'link_id': doc['_id']}
                    link_ids_to_check.append(doc['_id'])
                
            if self.has_db3:
                existing_docs_3 = await self.data_col3.find({"file_unique_id": {"$in": unique_ids}}).to_list(length=len(unique_batch_items))
                for doc in existing_docs_3: 
                    existing_map[doc['file_unique_id']] = {'db': 3, 'link_id': doc['_id']}
                    link_ids_to_check.append(doc['_id'])
        except: pass

        old_text_lengths = {}
        if link_ids_to_check:
            try:
                old_search_1 = await self.search_col1.find({"link_id": {"$in": link_ids_to_check}}).to_list(length=len(link_ids_to_check))
                for doc in old_search_1: old_text_lengths[doc['link_id']] = len(doc.get('file_name', '')) + len(doc.get('search_text', ''))
                
                if self.has_db2:
                    old_search_2 = await self.search_col2.find({"link_id": {"$in": link_ids_to_check}}).to_list(length=len(link_ids_to_check))
                    for doc in old_search_2: old_text_lengths[doc['link_id']] = len(doc.get('file_name', '')) + len(doc.get('search_text', ''))
                
                if self.has_db3:
                    old_search_3 = await self.search_col3.find({"link_id": {"$in": link_ids_to_check}}).to_list(length=len(link_ids_to_check))
                    for doc in old_search_3: old_text_lengths[doc['link_id']] = len(doc.get('file_name', '')) + len(doc.get('search_text', ''))
            except: pass

        new_items = [(media, msg) for media, msg in unique_batch_items if media.file_unique_id not in existing_map]
        update_items = [(media, msg, existing_map[media.file_unique_id]) for media, msg in unique_batch_items if media.file_unique_id in existing_map]
        
        pre_duplicate_count = len(items) - len(new_items)
            
        count = len(new_items)
        end_sequence = None
        start_sequence = 0
        if count > 0:
            end_sequence = await self.get_next_sequence_value("file_id_counter", increment=count)
            if end_sequence:
                start_sequence = end_sequence - count + 1
        
        data_docs, search_docs = [], []
        current_id = start_sequence
        
        all_processing_items = [("new", m, msg, None) for m, msg in new_items] + [("update", m, msg, ex) for m, msg, ex in update_items]
        
        for process_type, media, message, ex_info in all_processing_items:
            raw_fname = media.file_name or ""
            raw_cap = message.caption.html if message.caption else ""
            
            meta_name = self.parse_metadata(raw_fname)
            meta_cap = self.parse_metadata(raw_cap)

            parsed_meta = {
                "quality": list(set(meta_name.get('quality', []) + meta_cap.get('quality', []))),
                "languages": list(set(meta_name.get('languages', []) + meta_cap.get('languages', []))),
                "year": list(set(meta_name.get('year', []) + meta_cap.get('year', [])))
            }
            
            clean_fname = self.clean_text(raw_fname)
            
            meta_regex = r"(?i)(1080p|720p|480p|4k|2160p|s\d+|e\d+|\b19\d{2}\b|\b20\d{2}\b|hindi|tamil|telugu|dual)"
            
            clean_cap_line = ""
            score_cap = 0
            if raw_cap:
                best_cap_line = ""
                max_score = -1
                for line in html.unescape(raw_cap).split('\n'):
                    raw_score = len(re.findall(meta_regex, line))
                    cleaned_line = self.clean_text(line)
                    if raw_score > max_score and len(cleaned_line) > 3:
                        max_score = raw_score
                        best_cap_line = cleaned_line
                clean_cap_line = best_cap_line
                score_cap = max_score
            
            score_fname = len(re.findall(meta_regex, raw_fname))
            if clean_cap_line and len(clean_cap_line) > 3:
                final_display_name = clean_fname if (score_cap == 0 and score_fname > 0) else clean_cap_line
            else:
                final_display_name = clean_fname
                
            final_display_name = final_display_name or "Unknown File"

            untrimmed_raw_text = f"{raw_fname} {raw_cap}"
            untrimmed_raw_text = re.sub(r"(?i)\bS(\d+)\s*E(\d+)\b", r"S\1 E\2", untrimmed_raw_text)
            untrimmed_raw_text = re.sub(r"(?i)\bS(\d+)\s*(?:-|to)\s*(?:S)?(\d+)\b", lambda m: " ".join([f"S{str(i).zfill(2)}" for i in range(int(m.group(1)), int(m.group(2)) + 1)]), untrimmed_raw_text)
            untrimmed_raw_text = re.sub(r"(?i)\bE(\d+)\s*(?:-|to)\s*(?:E)?(\d+)\b", lambda m: " ".join([f"E{str(i).zfill(2)}" for i in range(int(m.group(1)), int(m.group(2)) + 1)]), untrimmed_raw_text)
            untrimmed_raw_text = re.sub(r"(?i)\b(\d{1,2})\s*x\s*(\d{1,4})\b", r"S\1 E\2", untrimmed_raw_text)
            untrimmed_raw_text = re.sub(r"(?i)\b(?:season|s)\s*(\d+)\b", r"S\1", untrimmed_raw_text)
            untrimmed_raw_text = re.sub(r"(?i)\b(?:episode|ep|e)\s*(\d+)\b", r"E\1", untrimmed_raw_text)

            seasons = re.findall(r"(?i)\bS(\d+)\b", untrimmed_raw_text)
            episodes = re.findall(r"(?i)\bE(\d+)\b", untrimmed_raw_text)
            
            variations = []
            orig_raw = (media.file_name or "").lower()
            
            for s in seasons: variations.append(f"s{int(s)} s{str(int(s)).zfill(2)} season{int(s)}")
            for e in episodes: variations.append(f"e{int(e)} e{str(int(e)).zfill(2)} ep{int(e)}")
            for s in seasons:
                for e in episodes: variations.append(f"s{int(s)}e{int(e)} s{str(int(s)).zfill(2)}e{str(int(e)).zfill(2)}")

            for tag in ["part", "vol", "chapter", "ch"]:
                for v in re.findall(rf"(?i){tag}(?:ume)?\s*(\d+)", orig_raw): variations.append(f"{tag}{v}")

            variation_text = " ".join(list(set(variations)))
            spaceless_name = re.sub(r"[^\w]", "", final_display_name).lower()

            clean_full_cap = self.clean_text(raw_cap)
            raw_hidden_data = f"{clean_fname} {clean_full_cap}"
            
            promo_patterns = r"@|t\.me/|https?://|www\.\w+|\w+\.(?:com|in|vip|org|net|me|xyz|site|cc|to|club|tech|link|app|click|store|hd)\b"
            clean_hidden_data = re.sub(r"<[^>]+>", " ", raw_hidden_data)
            clean_hidden_data = re.sub(promo_patterns, " ", clean_hidden_data, flags=re.IGNORECASE)
            
            roman_map = {r'I': '1', r'II': '2', r'III': '3', r'IV': '4', r'V': '5', r'VI': '6', r'VII': '7', r'VIII': '8', r'IX': '9', r'X': '10'}
            for roman, digit in roman_map.items():
                clean_hidden_data = re.sub(rf"(?i)(?<=\s)\b{roman}\b", digit, clean_hidden_data)
            
            meta_injection = " ".join(parsed_meta['quality'] + parsed_meta['year'] + parsed_meta['languages'])
            raw_master_text = f"{clean_hidden_data} {spaceless_name} {variation_text} {meta_injection}".lower()
            
            punctuation_stripped_text = re.sub(r"[^\w\s&]", " ", raw_master_text)
            clean_master_text = re.sub(r"\s+", " ", punctuation_stripped_text).strip()
            
            all_search_words = set(clean_master_text.split())
            display_words = set(re.sub(r"[^\w\s&]", " ", final_display_name.lower()).split())
            
            spam_words = {"nf", "esub", "esubs", "hc", "x264", "x265", "10bit", "org", "rip", "webdl", "web", "dl", "download", "join", "mkv", "mp4", "avi", "hevc", "crav", "ddp", "aac", "ott", "hdrip", "bluray", "print", "audio", "dual", "multi", "subs", "sub", "telegram", "channel", "movies", "movie", "series", "hd", "hub", "link", "watch", "online", "free", "admin", "upload", "uploaded"}
            
            final_unique_words = (all_search_words - display_words) - spam_words
            master_search_text = " ".join(final_unique_words)

            file_type = "video" if message.video else "document"

            if process_type == "new" and current_id > 0:
                data_docs.append({'_id': current_id, 'msg_id': message.id, 'chat_id': message.chat.id, 'file_id': media.file_id, 'file_unique_id': media.file_unique_id, 'file_type': file_type})
                
                search_doc = {
                    'file_name': final_display_name, 'file_size': media.file_size, 'search_text': master_search_text, 
                    'link_id': current_id, 'chat_id': message.chat.id, 'file_type': file_type
                }
                if parsed_meta['quality']: search_doc['quality'] = parsed_meta['quality']
                if parsed_meta['languages']: search_doc['languages'] = parsed_meta['languages']
                if parsed_meta['year']: search_doc['year'] = parsed_meta['year']

                search_docs.append(search_doc)
                current_id += 1
                
            elif process_type == "update":
                db_num = ex_info['db']
                link_id = ex_info['link_id']
                
                new_text_length = len(final_display_name) + len(master_search_text)
                old_text_length = old_text_lengths.get(link_id, 0)
                
                if new_text_length > old_text_length:
                    if db_num == 3 and self.has_db3:
                        active_data, active_search = self.data_col3, self.search_col3
                    elif db_num == 2 and self.has_db2:
                        active_data, active_search = self.data_col2, self.search_col2
                    else:
                        active_data, active_search = self.data_col1, self.search_col1
                        
                    data_update = {
                        'msg_id': message.id, 
                        'chat_id': message.chat.id, 
                        'file_id': media.file_id, 
                        'file_type': file_type
                    }
                    
                    search_update = {
                        'file_name': final_display_name, 
                        'file_size': media.file_size, 
                        'search_text': master_search_text, 
                        'chat_id': message.chat.id, 
                        'file_type': file_type
                    }
                    search_update['quality'] = parsed_meta['quality'] if parsed_meta['quality'] else []
                    search_update['languages'] = parsed_meta['languages'] if parsed_meta['languages'] else []
                    search_update['year'] = parsed_meta['year'] if parsed_meta['year'] else []

                    try:
                        asyncio.create_task(active_data.update_one({'_id': link_id}, {'$set': data_update}))
                        asyncio.create_task(active_search.update_one({'link_id': link_id}, {'$set': search_update}))
                    except Exception: pass

        saved_count = 0
        
        if data_docs or search_docs:
            active_db_num = await self.get_active_index_db()
            
            if active_db_num == 3 and self.has_db3:
                active_data_col = self.data_col3
                active_search_col = self.search_col3
            elif active_db_num == 2 and self.has_db2:
                active_data_col = self.data_col2
                active_search_col = self.search_col2
            else:
                active_data_col = self.data_col1
                active_search_col = self.search_col1

            if data_docs:
                try:
                    await active_data_col.insert_many(data_docs, ordered=False)
                    saved_count = len(data_docs)
                except BulkWriteError as bwe: saved_count = bwe.details['nInserted']
                except Exception: pass 
            
            if search_docs:
                try: await active_search_col.insert_many(search_docs, ordered=False)
                except BulkWriteError: pass
                except Exception: pass
                
        return saved_count, pre_duplicate_count

    async def get_file_details(self, link_id):
        doc = await self.data_col1.find_one({'_id': int(link_id)})
        if not doc and self.has_db2: doc = await self.data_col2.find_one({'_id': int(link_id)})
        if not doc and self.has_db3: doc = await self.data_col3.find_one({'_id': int(link_id)})
        return doc

    async def get_search_data(self, link_id):
        doc = await self.search_col1.find_one({'link_id': int(link_id)})
        if not doc and self.has_db2: doc = await self.search_col2.find_one({'link_id': int(link_id)})
        if not doc and self.has_db3: doc = await self.search_col3.find_one({'link_id': int(link_id)})
        return doc

    async def update_file_id(self, old_file_id, new_file_id):
        try:
            res1 = await self.data_col1.update_one({'file_id': old_file_id}, {'$set': {'file_id': new_file_id}})
            if res1.modified_count > 0: return True
            
            if self.has_db2:
                res2 = await self.data_col2.update_one({'file_id': old_file_id}, {'$set': {'file_id': new_file_id}})
                if res2.modified_count > 0: return True
                
            if self.has_db3:
                res3 = await self.data_col3.update_one({'file_id': old_file_id}, {'$set': {'file_id': new_file_id}})
                if res3.modified_count > 0: return True
                
            return False
        except Exception as e:
            logger.error(f"Error updating file_id for Smart Cache: {e}")
            return False

    # ==================================================================
    # ⚡ ATLAS FUZZY SEARCH (ULTRA FAST + 3-TIER LOGIC + NUMBER PROTECTION)
    # ==================================================================
    async def get_search_results(self, query, file_type=None, lang=None, quality=None, year=None, size_range=None, sort="relevance"):
        if not query or not query.strip(): return []

        try:
            # 1. Basic Cleaning
            raw_query = query.strip().lower()
            clean_query = re.sub(r"(?i)\b(englsh|engls|engish|egnlish)\b", "english", raw_query)
            clean_query = re.sub(r"(?i)\b(hndi|hind|hni|hin)\b", "hindi", clean_query)
            clean_query = re.sub(r"(?i)\b(tmal|taml|tmil|tam)\b", "tamil", clean_query)
            clean_query = re.sub(r"(?i)\b(telgu|tlgu|telug|telegu|tel)\b", "telugu", clean_query)
            clean_query = re.sub(r"(?i)\b(malyalam|malaylam|malyalm|malalam|mal)\b", "malayalam", clean_query)
            clean_query = re.sub(r"(?i)\b(kanada|kanda|kannad|kan)\b", "kannada", clean_query)
            
            # 2. 🔥 DYNAMIC ATLAS FUZZY SEARCH
            should_clauses = []
            
            for word in clean_query.split():
                # 🛡️ Agar word me koi NUMBER hai (e.g. 2024, 1080p, 4k), toh 0 mistakes!
                if any(char.isdigit() for char in word):
                    edits = 0
                # Word ke size ke hisab se edit limit set karna
                elif len(word) <= 3:
                    edits = 0  # KGF, PK, Bat -> No mistakes allowed
                elif len(word) <= 5:
                    edits = 1  # Thor, Hulk, Hindi -> 1 mistake allowed
                else:
                    edits = 2  # Pushpa, Avengers, Spdrman -> 2 mistakes allowed
                
                clause = {
                    "text": {
                        "query": word,
                        "path": ["file_name", "search_text"]
                    }
                }
                
                # Agar edits 0 se zyada hain, tabhi fuzzy block add karenge
                if edits > 0:
                    clause["text"]["fuzzy"] = {
                        "maxEdits": edits,
                        "prefixLength": 1,
                        "maxExpansions": 50
                    }
                    
                should_clauses.append(clause)

            search_stage = {
                "$search": {
                    "index": "default",
                    "compound": {
                        "should": should_clauses,
                        "minimumShouldMatch": 1
                    }
                }
            }

            # 3. EXTRA FILTERS STAGE (Language, Quality, Year, etc.)
            match_filters = {}
            if file_type and file_type != "none": match_filters["file_type"] = "video" if file_type.lower() == "video" else "document"
            if lang and lang != "none":
                pattern = LANG_MAP.get(lang, lang)
                match_filters["$and"] = match_filters.get("$and", []) + [{"$or": [{"languages": lang}, {"file_name": {"$regex": pattern, "$options": "i"}}]}]
            if quality and quality != "none":
                match_filters["$and"] = match_filters.get("$and", []) + [{"$or": [{"quality": quality}, {"file_name": {"$regex": quality, "$options": "i"}}]}]
            if year and year != "none":
                match_filters["$and"] = match_filters.get("$and", []) + [{"$or": [{"year": str(year)}, {"file_name": {"$regex": str(year)}}]}]
            if size_range and size_range != "none":
                MB_500, GB_1, GB_2 = 500*1024*1024, 1024*1024*1024, 2*1024*1024*1024
                if size_range == "min500": match_filters["file_size"] = {"$lt": MB_500}
                elif size_range == "500-1gb": match_filters["file_size"] = {"$gte": MB_500, "$lt": GB_1}
                elif size_range == "1gb-2gb": match_filters["file_size"] = {"$gte": GB_1, "$lt": GB_2}
                elif size_range == "max2gb": match_filters["file_size"] = {"$gte": GB_2}

            # 4. PIPELINE BUILDER
            pipeline = [search_stage]
            
            if match_filters:
                pipeline.append({"$match": match_filters})

            # Data extract karna aur Atlas Search ka asli score nikalna
            pipeline.append({
                "$project": {
                    "file_name": 1, "search_text": 1, "quality": 1, "languages": 1, 
                    "year": 1, "link_id": 1, "chat_id": 1, "file_type": 1, "file_size": 1, 
                    "score": {"$meta": "searchScore"}, 
                    "name_length": {"$strLenCP": {"$ifNull": ["$file_name", ""]}}
                }
            })

            # 5. SORTING
            if sort == "new": pipeline.append({"$sort": {"_id": -1}}) 
            elif sort == "old": pipeline.append({"$sort": {"_id": 1}}) 
            elif sort == "large": pipeline.append({"$sort": {"file_size": -1}}) 
            elif sort == "small": pipeline.append({"$sort": {"file_size": 1}}) 
            else: pipeline.append({"$sort": {"score": -1, "name_length": 1, "_id": -1}}) 

            pipeline.append({"$limit": 100}) 
            
            # 6. PARALLEL DB FETCHING (Speed x3)
            async def fetch_db(collection, pipe):
                try:
                    return await collection.aggregate(pipe).to_list(length=100)
                except Exception:
                    return []
                    
            tasks = [fetch_db(self.search_col1, pipeline)]
            if self.has_db2: tasks.append(fetch_db(self.search_col2, pipeline))
            if self.has_db3: tasks.append(fetch_db(self.search_col3, pipeline))
            
            results = await asyncio.gather(*tasks)
            
            files = []
            for res in results:
                files.extend(res)
            
            if not files: raise Exception("Fallback Search Triggered")

            # 🔥 3-DB Merge Sort: Rank cross-database results by exact Atlas Score
            files.sort(key=lambda x: x.get('score', 0), reverse=True)

            return files[:100]

        except Exception as e:
            # 7. SAFE FALLBACK (Broad 'OR' Logic with Button Filters)
            try:
                fallback_match = {}
                words = clean_query.split()
                fallback_or_clauses = []
                
                for tw in words:
                    safe_tw = rf"\b{re.escape(tw)}\b"
                    fallback_or_clauses.append({"search_text": {"$regex": safe_tw, "$options": "i"}})
                    fallback_or_clauses.append({"file_name": {"$regex": safe_tw, "$options": "i"}})
                    
                if fallback_or_clauses: 
                    fallback_match["$or"] = fallback_or_clauses
                
                if file_type and file_type != "none": fallback_match["file_type"] = "video" if file_type.lower() == "video" else "document"
                if lang and lang != "none":
                    pattern = LANG_MAP.get(lang, lang)
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"languages": lang}, {"file_name": {"$regex": pattern, "$options": "i"}}]}]
                if quality and quality != "none":
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"quality": quality}, {"file_name": {"$regex": quality, "$options": "i"}}]}]
                if year and year != "none":
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"year": str(year)}, {"file_name": {"$regex": str(year)}}]}]
                if size_range and size_range != "none":
                    if size_range == "min500": fallback_match["file_size"] = {"$lt": MB_500}
                    elif size_range == "500-1gb": fallback_match["file_size"] = {"$gte": MB_500, "$lt": GB_1}
                    elif size_range == "1gb-2gb": fallback_match["file_size"] = {"$gte": GB_1, "$lt": GB_2}
                    elif size_range == "max2gb": fallback_match["file_size"] = {"$gte": GB_2}

                fallback_pipeline = [
                    {"$match": fallback_match},
                    {"$project": {
                        "file_name": 1, "search_text": 1, "quality": 1, "languages": 1, 
                        "year": 1, "link_id": 1, "chat_id": 1, "file_type": 1, "file_size": 1,
                        "name_length": {"$strLenCP": {"$ifNull": ["$file_name", ""]}}
                    }}
                ]
                
                if sort == "new": fallback_pipeline.append({"$sort": {"_id": -1}})
                elif sort == "old": fallback_pipeline.append({"$sort": {"_id": 1}})
                elif sort == "large": fallback_pipeline.append({"$sort": {"file_size": -1}})
                elif sort == "small": fallback_pipeline.append({"$sort": {"file_size": 1}})
                else: fallback_pipeline.append({"$sort": {"name_length": 1, "_id": -1}})

                fallback_pipeline.append({"$limit": 30})
                
                async def fetch_fallback(collection, pipe):
                    try:
                        return await collection.aggregate(pipe).to_list(length=30)
                    except Exception:
                        return []
                        
                fb_tasks = [fetch_fallback(self.search_col1, fallback_pipeline)]
                if self.has_db2: fb_tasks.append(fetch_fallback(self.search_col2, fallback_pipeline))
                if self.has_db3: fb_tasks.append(fetch_fallback(self.search_col3, fallback_pipeline))
                
                fb_results = await asyncio.gather(*fb_tasks)
                
                files = []
                for res in fb_results:
                    files.extend(res)
                
                # 🔥 Fallback 3-DB Merge Sort: Sort results combined from all databases
                files.sort(key=lambda x: x.get('name_length', 999))
                
                return files[:30]
                    
            except Exception as inner_e:
                return []

    async def total_files_count(self): 
        count = await self.data_col1.count_documents({})
        if self.has_db2: count += await self.data_col2.count_documents({})
        if self.has_db3: count += await self.data_col3.count_documents({})
        return count
    
    async def get_db_size(self):
        try:
            stats1 = await self.db1.command("dbstats")
            total = stats1.get('storageSize', 0) + stats1.get('totalIndexSize', 0)
            if self.has_db2:
                stats2 = await self.db2.command("dbstats")
                total += stats2.get('storageSize', 0) + stats2.get('totalIndexSize', 0)
            if self.has_db3:
                stats3 = await self.db3.command("dbstats")
                total += stats3.get('storageSize', 0) + stats3.get('totalIndexSize', 0)
            return total
        except: return 0

    async def get_detailed_stats(self):
        stats_dict = {"db1": None, "db2": None, "db3": None, "total_overall": 0}
        total_overall = 0
        try:
            db_stats1 = await self.db1.command("dbstats")
            t1 = db_stats1.get('storageSize', 0) + db_stats1.get('totalIndexSize', 0)
            
            try:
                cursor1 = self.search_col1.aggregate([{"$collStats": {"storageStats": {}}}])
                stats_list1 = await cursor1.to_list(length=1)
                tx1 = stats_list1[0].get("storageStats", {}).get("indexSizes", {}).get("weighted_movie_search", 0) if stats_list1 else 0
            except Exception as e:
                tx1 = 0

            try:
                cursor_cache1 = self.search_cache.aggregate([{"$collStats": {"storageStats": {}}}])
                c1_list = await cursor_cache1.to_list(length=1)
                if c1_list:
                    ss = c1_list[0].get("storageStats", {})
                    cache1 = ss.get('storageSize', 0) + ss.get('totalIndexSize', 0)
                else: cache1 = 0
            except: cache1 = 0

            try:
                cursor_temp1 = self.temp_searches.aggregate([{"$collStats": {"storageStats": {}}}])
                ts1_list = await cursor_temp1.to_list(length=1)
                if ts1_list:
                    ss = ts1_list[0].get("storageStats", {})
                    temp1 = ss.get('storageSize', 0) + ss.get('totalIndexSize', 0)
                else: temp1 = 0
            except: temp1 = 0

            cache_total = cache1 + temp1
            main1 = t1 - (tx1 + cache_total)
            stats_dict["db1"] = {"total": t1, "text": tx1, "cache": cache_total, "main": max(main1, 0)}
            total_overall += t1

            if self.has_db2:
                db_stats2 = await self.db2.command("dbstats")
                t2 = db_stats2.get('storageSize', 0) + db_stats2.get('totalIndexSize', 0)
                try:
                    cursor2 = self.search_col2.aggregate([{"$collStats": {"storageStats": {}}}])
                    stats_list2 = await cursor2.to_list(length=1)
                    tx2 = stats_list2[0].get("storageStats", {}).get("indexSizes", {}).get("weighted_movie_search", 0) if stats_list2 else 0
                except: tx2 = 0
                main2 = t2 - tx2
                stats_dict["db2"] = {"total": t2, "text": tx2, "main": max(main2, 0)}
                total_overall += t2

            if self.has_db3:
                db_stats3 = await self.db3.command("dbstats")
                t3 = db_stats3.get('storageSize', 0) + db_stats3.get('totalIndexSize', 0)
                try:
                    cursor3 = self.search_col3.aggregate([{"$collStats": {"storageStats": {}}}])
                    stats_list3 = await cursor3.to_list(length=1)
                    tx3 = stats_list3[0].get("storageStats", {}).get("indexSizes", {}).get("weighted_movie_search", 0) if stats_list3 else 0
                except: tx3 = 0
                main3 = t3 - tx3
                stats_dict["db3"] = {"total": t3, "text": tx3, "main": max(main3, 0)}
                total_overall += t3

            stats_dict["total_overall"] = total_overall
            return stats_dict
            
        except Exception as e:
            print(f"Overall Stats Error: {e}")
            return {"total_size": 0, "text_index_size": 0, "cache_size": 0, "other_size": 0}

    async def save_search_results(self, query, files, chat_id):
        unique_id = str(uuid.uuid4())[:8]
        simplified_files = []
        for file in files:
            safe_name = file.get('file_name', 'Unknown')
            simplified_files.append({
                "file_name": safe_name, 
                "file_size": file.get('file_size', 0), 
                "link_id": file.get('link_id', 0),
                "file_chat_id": file.get('chat_id', 0), 
                "file_type": file.get('file_type', 'document'),
                "caption": safe_name
            })
        await self.search_cache.insert_one({"_id": unique_id, "query": query, "chat_id": chat_id, "files": simplified_files, "created_at": datetime.datetime.utcnow()})
        return unique_id

    async def get_cached_results(self, unique_id): return await self.search_cache.find_one({"_id": unique_id})

Media = MediaDB(DATABASE_URI, DATABASE_URI_2, DATABASE_URI_3, DATABASE_NAME)
