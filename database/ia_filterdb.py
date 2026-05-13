import logging
import re
import datetime
import uuid
import html  
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError
from pymongo import ReturnDocument, UpdateOne 
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
        self._client1 = AsyncIOMotorClient(uri1)
        self.db1 = self._client1[database_name] 
        self.data_col1 = self.db1.files_data   
        self.search_col1 = self.db1.files_search 
        
        self.counters = self.db1.counters
        self.search_cache = self.db1.search_cache 
        self.temp_searches = self.db1.temp_searches
        self.bot_settings = self.db1.bot_settings 

        self.has_db2 = bool(uri2 and len(uri2) > 10)
        if self.has_db2:
            self._client2 = AsyncIOMotorClient(uri2)
            self.db2 = self._client2[database_name] 
            self.data_col2 = self.db2.files_data
            self.search_col2 = self.db2.files_search
        else:
            self.db2 = None

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
            try: await self.search_cache.drop_index("created_at_1")
            except Exception: pass
            try: await self.temp_searches.drop_index("created_at_1")
            except Exception: pass

            await self.search_col1.create_index("link_id")
            await self.data_col1.create_index("file_id") 
            await self.data_col1.create_index("file_unique_id", unique=True)

            await self.search_cache.create_index("created_at", expireAfterSeconds=3600)
            await self.temp_searches.create_index("created_at", expireAfterSeconds=43200)
            
            if self.has_db2:
                await self.search_col2.create_index("link_id")
                await self.data_col2.create_index("file_id")
                await self.data_col2.create_index("file_unique_id", unique=True)

            if self.has_db3:
                await self.search_col3.create_index("link_id")
                await self.data_col3.create_index("file_id")
                await self.data_col3.create_index("file_unique_id", unique=True)
            
            print("✅ Multi-Database Indexes Created Successfully! (Atlas Search Ready)")
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

        qual_map = {
            '4k': '2160p', 'uhd': '2160p', '2160p': '2160p',
            '1080p': '1080p', '720p': '720p', '480p': '480p', '360p': '360p',
            'bluray': 'Bluray', 'blu-ray': 'Bluray', 'bdrip': 'Bluray',
            'hd': 'HD', 'hdtv': 'HD', 'hdrip': 'HD', 'hq': 'HD',
            'cam': 'CAM', 'camrip': 'CAM', 'hdcam': 'CAM'
        }
        res_pattern = r"(?i)\b(480p|720p|1080p|2160p|360p|4k|uhd|bluray|blu-ray|bdrip|hd|hdtv|hdrip|hq|cam|camrip|hdcam)\b"
        for m in re.finditer(res_pattern, cleaned_title):
            raw_val = m.group(1).lower()
            std_qual = qual_map.get(raw_val)
            if std_qual: metadata['quality'].add(std_qual)
        cleaned_title = re.sub(res_pattern, "", cleaned_title)

        lang_map = {
            'hin': 'Hindi', 'hindi': 'Hindi', 'tam': 'Tamil', 'tamil': 'Tamil',
            'tel': 'Telugu', 'telugu': 'Telugu', 'mal': 'Malayalam', 'malayalam': 'Malayalam',
            'kan': 'Kannada', 'kannada': 'Kannada', 'eng': 'English', 'english': 'English',
            'ben': 'Bengali', 'bengali': 'Bengali', 'pun': 'Punjabi', 'punjabi': 'Punjabi',
            'mar': 'Marathi', 'marathi': 'Marathi', 'guj': 'Gujarati', 'gujarati': 'Gujarati',
            'urdu': 'Urdu', 'multi': 'Multi Audio', 'dual': 'Dual Audio'
        }
        lang_pattern = r"(?i)\b(hindi|hin|tamil|tam|telugu|tel|malayalam|mal|kannada|kan|english|eng|bengali|ben|punjabi|pun|marathi|mar|gujarati|guj|urdu|multi[\s\-]?audio|dual[\s\-]?audio)\b"
        for m in re.finditer(lang_pattern, cleaned_title):
            raw_val = m.group(1).lower().replace('-', ' ').replace('audio', '').strip()
            standard_lang = lang_map.get(raw_val)
            if standard_lang: metadata['languages'].add(standard_lang)
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
        update_ops_data = {1: [], 2: [], 3: []}
        update_ops_search = {1: [], 2: [], 3: []}
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
            for roman, digit in roman_map.items(): clean_hidden_data = re.sub(rf"(?i)(?<=\s)\b{roman}\b", digit, clean_hidden_data)
            
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
                    data_update = {'msg_id': message.id, 'chat_id': message.chat.id, 'file_id': media.file_id, 'file_type': file_type}
                    search_update = {
                        'file_name': final_display_name, 'file_size': media.file_size, 'search_text': master_search_text, 
                        'chat_id': message.chat.id, 'file_type': file_type
                    }
                    search_update['quality'] = parsed_meta['quality'] if parsed_meta['quality'] else []
                    search_update['languages'] = parsed_meta['languages'] if parsed_meta['languages'] else []
                    search_update['year'] = parsed_meta['year'] if parsed_meta['year'] else []
                    update_ops_data[db_num].append(UpdateOne({'_id': link_id}, {'$set': data_update}))
                    update_ops_search[db_num].append(UpdateOne({'link_id': link_id}, {'$set': search_update}))

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
                except: pass 
            if search_docs:
                try: await active_search_col.insert_many(search_docs, ordered=False)
                except: pass
                
        # 🟢 DB Updates
        if update_ops_data[1]:
            try: await self.data_col1.bulk_write(update_ops_data[1], ordered=False)
            except Exception: pass
        if update_ops_search[1]:
            try: await self.search_col1.bulk_write(update_ops_search[1], ordered=False)
            except Exception: pass
        if self.has_db2:
            if update_ops_data[2]:
                try: await self.data_col2.bulk_write(update_ops_data[2], ordered=False)
                except Exception: pass
            if update_ops_search[2]:
                try: await self.search_col2.bulk_write(update_ops_search[2], ordered=False)
                except Exception: pass
        if self.has_db3:
            if update_ops_data[3]:
                try: await self.data_col3.bulk_write(update_ops_data[3], ordered=False)
                except Exception: pass
            if update_ops_search[3]:
                try: await self.search_col3.bulk_write(update_ops_search[3], ordered=False)
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
            return False

    # ==================================================================
    # ⚡ ATLAS FUZZY SEARCH (THE ATLAS TRUST & NO-PENALTY FIX)
    # ==================================================================
    async def get_search_results(self, query, file_type=None, lang=None, quality=None, year=None, size_range=None, sort="relevance"):
        if not query or not query.strip(): return []

        raw_query = query.strip().lower()
        raw_query = re.sub(r"[^\w\s]", " ", raw_query) 
        
        roman_map_search = {r'ii': '2', r'iii': '3', r'iv': '4', r'vi': '6', r'vii': '7', r'viii': '8', r'ix': '9'}
        for roman, digit in roman_map_search.items(): raw_query = re.sub(rf"(?i)\b{roman}\b", digit, raw_query)

        clean_query = re.sub(r"(?i)\b(englsh|engls|engish|egnlish)\b", "english", raw_query)
        clean_query = re.sub(r"(?i)\b(hndi|hind|hni|hin)\b", "hindi", clean_query)
        clean_query = re.sub(r"(?i)\b(tmal|taml|tmil|tam)\b", "tamil", clean_query)
        clean_query = re.sub(r"(?i)\b(telgu|tlgu|telug|telegu|tel)\b", "telugu", clean_query)
        clean_query = re.sub(r"(?i)\b(malyalam|malaylam|malyalm|malalam|mal)\b", "malayalam", clean_query)
        clean_query = re.sub(r"(?i)\b(kanada|kanda|kannad|kan)\b", "kannada", clean_query)

        DESI_SPELLING_MAP = {"rat": "raat", "bat": "baat", "ag": "aag", "aj": "aaj", "ser": "sher", "nhi": "nahi", "nai": "nahi", "ni": "nahi", "hn": "haan", "ha": "haan", "haa": "haan", "mai": "main", "me": "mein", "hu": "hoon", "hun": "hoon", "ashiqui": "aashiqui", "aashiki": "aashiqui", "kch": "kuchh", "isq": "ishq", "bai": "bhai", "fir": "phir", "ful": "phool", "kuda": "khuda", "fansi": "phaansi", "babi": "bhabhi"}
        query_words = clean_query.split()
        normalized_words = [DESI_SPELLING_MAP.get(w, w) for w in query_words]
        
        stop_words = {"the", "a", "an", "is", "of", "and", "in", "on", "for", "with", "to"}
        meta_keywords = {"hindi", "tamil", "telugu", "malayalam", "kannada", "bengali", "punjabi", "marathi", "gujarati", "urdu", "english", "1080p", "720p", "480p", "360p", "2160p", "4k", "bluray", "hdrip", "webrip", "cam", "dvdrip", "dual", "multi", "audio", "mkv", "mp4", "movie", "full", "hd", "print", "download", "series", "remastered", "esub", "hq"}
        
        search_query_full = re.sub(r"\s+", " ", " ".join(normalized_words)).strip()
        if not search_query_full: search_query_full = clean_query
        
        all_query_words = search_query_full.split()
        
        search_core_words = [w for w in all_query_words if w not in meta_keywords and w not in stop_words and not re.match(r"^(19|20)\d{2}$", w)]
        if not search_core_words: 
            search_core_words = all_query_words

        def get_expanded_query(w):
            if w.isdigit(): 
                return f"{w} 0{w} s{w} s0{w} e{w} e0{w} pt{w} part{w} vol{w}"
            return w

        files_map = {} 

        try:
            should_clauses = []
            
            if len(all_query_words) > 1:
                should_clauses.append({
                    "phrase": {
                        "query": search_query_full,
                        "path": "file_name",
                        "slop": 10, 
                        "score": {"boost": {"value": 10000}}
                    }
                })

            if len(all_query_words) > 1:
                must_all = [{"text": {"query": get_expanded_query(w), "path": ["file_name", "search_text"]}} for w in all_query_words if w not in stop_words]
                if must_all:
                    should_clauses.append({"compound": {"must": must_all, "score": {"boost": {"value": 8000}}}})

            if len(search_core_words) > 1 and len(search_core_words) != len(all_query_words):
                must_core = [{"text": {"query": get_expanded_query(w), "path": ["file_name", "search_text"]}} for w in search_core_words]
                if must_core:
                    should_clauses.append({"compound": {"must": must_core, "score": {"boost": {"value": 5000}}}})

            meaningful_fetch_words = [w for w in all_query_words if w not in stop_words]
            if not meaningful_fetch_words: meaningful_fetch_words = all_query_words

            for word in meaningful_fetch_words:
                is_core = word in search_core_words
                boost_val = 100 if is_core else 2 
                
                expanded_w = get_expanded_query(word)
                
                clause_fname = {"text": {"query": expanded_w, "path": "file_name", "score": {"boost": {"value": boost_val}}}}
                clause_stext = {"text": {"query": expanded_w, "path": "search_text", "score": {"boost": {"value": boost_val}}}}
                
                if edits > 0:
                    fuzzy_logic = {"maxEdits": edits, "prefixLength": 1, "maxExpansions": 50}
                    clause_fname["text"]["fuzzy"] = fuzzy_logic
                    clause_stext["text"]["fuzzy"] = fuzzy_logic
                    
                should_clauses.append(clause_fname)
                should_clauses.append(clause_stext)

            search_stage = {"$search": {"index": "default", "compound": {"should": should_clauses, "minimumShouldMatch": 1}}}
            
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

            pipeline = [search_stage]
            if match_filters: pipeline.append({"$match": match_filters})

            pipeline.append({
                "$project": {
                    "file_name": 1, "search_text": 1, "quality": 1, "languages": 1, 
                    "year": 1, "link_id": 1, "chat_id": 1, "file_type": 1, "file_size": 1, 
                    "score": {"$meta": "searchScore"}, 
                    "name_length": {"$strLenCP": {"$ifNull": ["$file_name", ""]}}
                }
            })

            if sort == "new": pipeline.append({"$sort": {"_id": -1}}) 
            elif sort == "old": pipeline.append({"$sort": {"_id": 1}}) 
            elif sort == "large": pipeline.append({"$sort": {"file_size": -1}}) 
            elif sort == "small": pipeline.append({"$sort": {"file_size": 1}}) 

            pipeline.append({"$limit": 300}) 
            
            async def fetch_db(col, pipe):
                try: return await col.aggregate(pipe).to_list(length=300)
                except: return []
            
            tasks = [fetch_db(self.search_col1, pipeline)]
            if self.has_db2: tasks.append(fetch_db(self.search_col2, pipeline))
            if self.has_db3: tasks.append(fetch_db(self.search_col3, pipeline))
            
            all_res = await asyncio.gather(*tasks)
            for res in all_res:
                for f in res: files_map[f['link_id']] = f
            
            if not files_map: raise Exception("Fallback")
        except:
            # 3. 🛡️ FALLBACK REGEX ENGINE
            try:
                fallback_match = {}
                fallback_and_clauses = []
                
                for w in search_core_words:
                    if w.isdigit():
                        safe_w = rf"\b(0*{w}|s0*{w}|e0*{w}|part\s*0*{w}|vol\s*0*{w}|pt\s*0*{w})\b"
                    else:
                        safe_w = rf"\b{re.escape(w)}\b"
                    
                    fallback_and_clauses.append({
                        "$or": [
                            {"search_text": {"$regex": safe_w, "$options": "i"}}, 
                            {"file_name": {"$regex": safe_w, "$options": "i"}}
                        ]
                    })
                    
                if fallback_and_clauses: 
                    fallback_match["$and"] = fallback_match.get("$and", []) + fallback_and_clauses
                
                if file_type and file_type != "none": fallback_match["file_type"] = "video" if file_type.lower() == "video" else "document"
                if lang and lang != "none":
                    pattern = LANG_MAP.get(lang, lang)
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"languages": lang}, {"file_name": {"$regex": pattern, "$options": "i"}}]}]
                if quality and quality != "none":
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"quality": quality}, {"file_name": {"$regex": quality, "$options": "i"}}]}]
                if year and year != "none":
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"year": str(year)}, {"file_name": {"$regex": str(year)}}]}]
                if size_range and size_range != "none":
                    MB_500, GB_1, GB_2 = 500*1024*1024, 1024*1024*1024, 2*1024*1024*1024
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

                fallback_pipeline.append({"$limit": 200})
                
                async def fetch_fallback(col, pipe):
                    try: return await col.aggregate(pipe).to_list(length=200)
                    except: return []
                        
                fb_tasks = [fetch_fallback(self.search_col1, fallback_pipeline)]
                if self.has_db2: fb_tasks.append(fetch_fallback(self.search_col2, fallback_pipeline))
                if self.has_db3: fb_tasks.append(fetch_fallback(self.search_col3, fallback_pipeline))
                
                fb_res = await asyncio.gather(*fb_tasks)
                for res in fb_res:
                    for f in res: files_map[f['link_id']] = f
            except: pass

        files = list(files_map.values())

        # 4. 🔥 FINAL SMART RANKER (THE ATLAS TRUST & NO-PENALTY FIX)
        if files and (sort == "relevance" or not sort):
            def smart_sort(x):
                # 🔥 YAHAN ATLAS KI MEHNAT KO PEHLE POINTS MILTE HAIN
                atlas_score = x.get('score', 0)
                score = atlas_score * 50 
                
                raw_fname = str(x.get('file_name', '')).lower()
                db_full = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", raw_fname)).strip()
                db_full_padded = f" {db_full} "
                
                db_search_text = str(x.get('search_text', '')).lower()
                db_langs = " ".join([str(l).lower() for l in x.get('languages', [])])
                db_quals = " ".join([str(q).lower() for q in x.get('quality', [])])
                db_year = " ".join([str(y).lower() for y in x.get('year', [])])
                
                full_text_to_search = f"{db_full} {db_search_text} {db_langs} {db_quals} {db_year}"
                
                def strip_articles(t):
                    return re.sub(r"^(the|a|an)\s+", "", t).strip()

                sq_full_words = search_query_full.split()
                
                search_core_rank_words = [w for w in sq_full_words if w not in meta_keywords and w not in stop_words and not re.match(r"^(19|20)\d{2}$", w)]
                if not search_core_rank_words: 
                    search_core_rank_words = sq_full_words 
                
                sq_exact_words = [w for w in sq_full_words if w not in meta_keywords and not re.match(r"^(19|20)\d{2}$", w)]
                if not sq_exact_words: sq_exact_words = sq_full_words
                
                sq_flex = strip_articles(" ".join(sq_exact_words))
                db_flex = strip_articles(db_full)
                db_flex_padded = f" {db_flex} "
                
                meta_words = [w for w in sq_full_words if w not in search_core_rank_words and w not in stop_words]

                # =========================================================
                # 🏆 TIER 1: CORE WORD MATCHING (FUZZY TRUST)
                # =========================================================
                if search_core_rank_words:
                    exact_core_matched = 0
                    for w in search_core_rank_words:
                        if len(w) > 3:
                            if w in full_text_to_search or w[:-1] in full_text_to_search:
                                exact_core_matched += 1
                        else:
                            if w.isdigit():
                                pattern = rf"\b(0*{w}|s0*{w}|e0*{w}|part\s*0*{w}|vol\s*0*{w}|pt\s*0*{w})\b"
                                if re.search(pattern, full_text_to_search, re.IGNORECASE):
                                    exact_core_matched += 1
                            else:
                                if f" {w} " in f" {full_text_to_search} ":
                                    exact_core_matched += 1
                    
                    # Exact Match Gets Full 10000 points
                    score += (exact_core_matched * 10000) 
                    
                    # 🔥 THE FIX: Agar word exact nahi mila, par file DB se aayi hai,
                    # Toh Atlas ne usko Fuzzy match kiya hoga (jaise Hrvest -> Harvest).
                    # Penalty DENE KE BAJAYE usko Fuzzy Points (8000) do!
                    fuzzy_matched = len(search_core_rank_words) - exact_core_matched
                    if atlas_score > 0:
                        score += (fuzzy_matched * 8000) 

                # =========================================================
                # 🏆 TIER 2: ABSOLUTE EXACT QUERY BOOST
                # =========================================================
                if db_full == search_query_full:
                    score += 2500
                elif db_full.startswith(search_query_full + " "):
                    score += 2000

                # =========================================================
                # 🏆 TIER 3: EXACT PREFIX & SEQUEL CHECKER
                # =========================================================
                meta_regex = r"^(19\d{2}|20\d{2}|\d{1,3}|i|ii|iii|iv|v|vi|vii|viii|ix|x|part\d+|vol\d+|s\d+|e\d+|hindi|tamil|telugu|malayalam|kannada|english|1080p|720p|480p|4k|bluray|hdrip|cam|esub)$"

                if db_flex == sq_flex:
                    score += 1000
                elif db_flex.startswith(sq_flex + " "):
                    remainder = db_flex[len(sq_flex):].strip()
                    next_word = remainder.split()[0] if remainder else ""
                    if re.match(meta_regex, next_word):
                        score += 800 
                    else:
                        score += 500 
                elif f" {sq_flex} " in db_flex_padded:
                    score += 50

                # =========================================================
                # 🏆 TIER 4: META WORDS SCORING
                # =========================================================
                if meta_words:
                    meta_matched = 0
                    for w in meta_words:
                        if w in full_text_to_search: meta_matched += 1
                    
                    score += (meta_matched * 10) 
                    score -= (len(meta_words) - meta_matched)

                # =========================================================
                # 🏆 TIER 5: TIE-BREAKERS
                # =========================================================
                raw_size = x.get('file_size') or 0
                size_mb = raw_size / (1024 * 1024)
                if size_mb > 0 and size_mb < 20: 
                    score -= 10 
                    
                name_len = x.get('name_length') or len(db_full)
                if name_len > 0:
                    score += (10 / (name_len + 1))
                    
                return score

            files.sort(key=smart_sort, reverse=True)

        return files[:100]

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
        LIMIT_512MB = 512 * 1024 * 1024  

        try:
            db_stats1 = await self.db1.command("dbstats")
            data_size1 = db_stats1.get('dataSize', 0) 
            index_size1 = db_stats1.get('indexSize', 0) 
            
            t1 = data_size1 + index_size1
            stats_dict["db1"] = {"total": t1, "main_data": data_size1, "basic_index": index_size1, "remaining_512mb": max(LIMIT_512MB - t1, 0)}
            total_overall += t1

            if self.has_db2:
                db_stats2 = await self.db2.command("dbstats")
                t2 = db_stats2.get('dataSize', 0) + db_stats2.get('indexSize', 0)
                stats_dict["db2"] = {"total": t2, "main_data": db_stats2.get('dataSize', 0), "basic_index": db_stats2.get('indexSize', 0), "remaining_512mb": max(LIMIT_512MB - t2, 0)}
                total_overall += t2

            if self.has_db3:
                db_stats3 = await self.db3.command("dbstats")
                t3 = db_stats3.get('dataSize', 0) + db_stats3.get('indexSize', 0)
                stats_dict["db3"] = {"total": t3, "main_data": db_stats3.get('dataSize', 0), "basic_index": db_stats3.get('indexSize', 0), "remaining_512mb": max(LIMIT_512MB - t3, 0)}
                total_overall += t3

            stats_dict["total_overall"] = total_overall
            return stats_dict
        except Exception as e:
            return None

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
