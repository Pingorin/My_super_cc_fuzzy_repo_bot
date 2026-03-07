import logging
import re
import datetime
import uuid
import traceback
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import BulkWriteError, OperationFailure
from pymongo import ReturnDocument, ASCENDING, TEXT
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
    "Urdu": "Urdu",
    "Dual Audio": "Dual Audio|Dual-Audio",
    "Multi Audio": "Multi Audio|Multi-Audio"
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

    # ==================================================================
    # ⚡ SAFE INDEXING SETUP (Restart hone par index delete nahi hoga)
    # ==================================================================
    async def ensure_indexes(self):
        try:
            await self.search_col.create_index("file_name")
            await self.search_col.create_index("caption")
            await self.search_col.create_index("search_text") 
            await self.search_col.create_index("quality") 
            await self.search_col.create_index("languages") 
            await self.search_col.create_index("year") 
            await self.search_col.create_index("link_id")
            
            # 🚀 FULL-TEXT INDEX (Safe Creation)
            try:
                await self.search_col.create_index(
                    [
                        ("file_name", TEXT),
                        ("search_text", TEXT),
                        ("caption", TEXT),
                        ("languages", TEXT),
                        ("quality", TEXT),
                        ("year", TEXT)
                    ],
                    weights={
                        "file_name": 100,     
                        "search_text": 80,    
                        "languages": 50,      
                        "quality": 30,        
                        "year": 10,           
                        "caption": 5          
                    },
                    name="weighted_movie_search"
                )
            except OperationFailure:
                # Agar pehle se alag weight ka index hai, toh hi usko delete karke naya banayega
                try:
                    await self.search_col.drop_index("weighted_movie_search")
                    await self.search_col.create_index(
                        [("file_name", TEXT), ("search_text", TEXT), ("caption", TEXT), ("languages", TEXT), ("quality", TEXT), ("year", TEXT)],
                        weights={"file_name": 100, "search_text": 80, "languages": 50, "quality": 30, "year": 10, "caption": 5},
                        name="weighted_movie_search"
                    )
                except Exception as ex:
                    print(f"⚠️ Could not recreate Text Index: {ex}")

            await self.data_col.create_index("file_unique_id", unique=True)
            await self.search_cache.create_index("created_at", expireAfterSeconds=3600)
            await self.temp_searches.create_index("created_at", expireAfterSeconds=172800)
            
            print("✅ Database Indexes Checked & Ready! (Instant Start)")
        except Exception as e:
            print(f"❌ Error Checking Indexes: {e}")

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

    @staticmethod
    def clean_text(text):
        if not text: return ""
        text = re.sub(r"<[^>]+>", "", text)
        ext_regex = r"(?i)(.*?(?:\.(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)|\b(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)\b))"
        match = re.search(ext_regex, text, flags=re.DOTALL)
        if match: text = match.group(1)

        promo_patterns = r"@|t\.me/|https?://|www\.\w+|\w+\.(?:com|in|vip|org|net|me|xyz|site|cc|to|club|tech|link|app|click|store|hd)\b"
        text = re.sub(r"\[[^\]]*(?:" + promo_patterns + r")[^\]]*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\([^)]*(?:" + promo_patterns + r")[^)]*\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\{[^}]*(?:" + promo_patterns + r")[^}]*\}", "", text, flags=re.IGNORECASE)
        text = re.sub(r"(https?://\S+|www\.\S+|t\.me/\S+|@\w+|\b\w+\.(?:com|in|vip|org|net|me|xyz|site|cc|to|club|tech|link|app|click|store|hd)\b)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u202a-\u202e]", "", text)

        spam_and_tags = [r"download", r"full movie", r"free", r"watch online", r"join", r"esub", r"hc-esub", r"x264", r"x265", r"code"]
        text = re.sub(r"\b(" + "|".join(spam_and_tags) + r")\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"[^\w\s:()\[\]{}\-]|_", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def parse_metadata(text):
        if not text: return {"cleaned_title": "", "quality": [], "languages": [], "source": [], "year": []}
        ext_regex = r"(?i)(.*?(?:\.(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)|\b(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)\b))"
        match = re.search(ext_regex, text, flags=re.DOTALL)
        if match: text = match.group(1)

        cleaned_title = text
        metadata = {"quality": set(), "languages": set(), "source": set(), "year": set()}

        res_pattern = r"(?i)\b(480p|720p|1080p|2160p|4k|uhd)\b"
        for m in re.finditer(res_pattern, cleaned_title):
            val = m.group(1).lower()
            if val in ['4k', 'uhd']: val = '2160p'
            metadata['quality'].add(val)
        cleaned_title = re.sub(res_pattern, "", cleaned_title)

        src_pattern = r"(?i)\b(web-dl|webrip|bluray|brrip|hdrip|hdcam|predvdrip)\b"
        for m in re.finditer(src_pattern, cleaned_title): metadata['source'].add(m.group(1).upper()) 
        cleaned_title = re.sub(src_pattern, "", cleaned_title)

        lang_map = {
            'hin': 'Hindi', 'hindi': 'Hindi', 'tam': 'Tamil', 'tamil': 'Tamil', 'tel': 'Telugu', 'telugu': 'Telugu',
            'mal': 'Malayalam', 'malayalam': 'Malayalam', 'kan': 'Kannada', 'kannada': 'Kannada', 'eng': 'English', 'english': 'English',
            'multi': 'Multi Audio', 'dual': 'Dual Audio'
        }
        lang_pattern = r"(?i)\b(hindi|hin|tamil|tam|telugu|tel|malayalam|mal|kannada|kan|english|eng|multi[\s\-]?audio|dual[\s\-]?audio)\b"
        for m in re.finditer(lang_pattern, cleaned_title):
            val = m.group(1).lower().replace('-', ' ').replace('audio', '').strip()
            for key, mapped in LANG_MAP.items():
                if val in mapped.lower().split('|'): metadata['languages'].add(key)
        cleaned_title = re.sub(lang_pattern, "", cleaned_title)

        year_pattern = r"\b(19\d{2}|20\d{2})\b"
        for m in re.finditer(year_pattern, cleaned_title): metadata['year'].add(m.group(1))
        cleaned_title = re.sub(year_pattern, "", cleaned_title)

        cleaned_title = re.sub(r"<[^>]+>|@\w+|t\.me/\S+|https?://\S+|www\.\S+", "", cleaned_title, flags=re.IGNORECASE)
        cleaned_title = re.sub(r"\[[\s\+\-\|]*\]|\([\s\+\-\|]*\)", "", cleaned_title)
        cleaned_title = re.sub(r"[^\w\s:()\[\]{}\-]|_", " ", cleaned_title)
        return {"cleaned_title": re.sub(r"\s+", " ", cleaned_title).strip(), "quality": list(metadata["quality"]), "languages": list(metadata["languages"]), "source": list(metadata["source"]), "year": list(metadata["year"])}

    async def save_batch(self, items):
        if not items: return 0, 0 
        unique_ids = [media.file_unique_id for media, msg in items]
        try:
            existing_docs = await self.data_col.find({"file_unique_id": {"$in": unique_ids}}).to_list(length=len(items))
            existing_unique_ids = set(doc['file_unique_id'] for doc in existing_docs)
        except: existing_unique_ids = set()

        new_items = [(media, msg) for media, msg in items if media.file_unique_id not in existing_unique_ids]
        pre_duplicate_count = len(items) - len(new_items)
        if not new_items: return 0, pre_duplicate_count 
            
        count = len(new_items)
        end_sequence = await self.get_next_sequence_value("file_id_counter", increment=count)
        if not end_sequence: return 0, 0
        
        start_sequence = end_sequence - count + 1
        data_docs, search_docs = [], []
        current_id = start_sequence
        
        for media, message in new_items:
            display_name = self.clean_text(media.file_name) or "Unknown File"
            caption = message.caption.html if message.caption else None
            cap_text = caption if caption else ""
                
            meta_name = self.parse_metadata(media.file_name)
            meta_cap = self.parse_metadata(message.caption.html if message.caption else "")

            parsed_meta = {
                "quality": list(set(meta_name['quality'] + meta_cap['quality'])),
                "languages": list(set(meta_name['languages'] + meta_cap['languages'])),
                "year": list(set(meta_name['year'] + meta_cap['year'])),
                "source": list(set(meta_name['source'] + meta_cap['source']))
            }

            hidden_search_data = display_name
            roman_map = {r'I': '1', r'II': '2', r'III': '3', r'IV': '4', r'V': '5', r'VI': '6', r'VII': '7', r'VIII': '8', r'IX': '9', r'X': '10'}
            for roman, digit in roman_map.items():
                hidden_search_data = re.sub(rf"(?i)(?<=\s)\b{roman}\b", digit, hidden_search_data)

            hidden_search_data = re.sub(r"(?i)\bS(\d+)\s*E(\d+)\b", r"S\1 E\2", hidden_search_data)
            hidden_search_data = re.sub(r"(?i)\bS(\d+)\s*(?:-|to)\s*(?:S)?(\d+)\b", lambda m: " ".join([f"S{str(i).zfill(2)}" for i in range(int(m.group(1)), int(m.group(2)) + 1)]), hidden_search_data)
            hidden_search_data = re.sub(r"(?i)\bE(\d+)\s*(?:-|to)\s*(?:E)?(\d+)\b", lambda m: " ".join([f"E{str(i).zfill(2)}" for i in range(int(m.group(1)), int(m.group(2)) + 1)]), hidden_search_data)
            hidden_search_data = re.sub(r"(?i)\b(\d{1,2})\s*x\s*(\d{1,4})\b", r"S\1 E\2", hidden_search_data)
            hidden_search_data = re.sub(r"(?i)\b(?:season|s)\s*(\d+)\b", r"S\1", hidden_search_data)
            hidden_search_data = re.sub(r"(?i)\b(?:episode|ep|e)\s*(\d+)\b", r"E\1", hidden_search_data)

            variations = []
            orig_raw = (media.file_name or "").lower()
            
            seasons = re.findall(r"(?i)\bS(\d+)\b", hidden_search_data)
            episodes = re.findall(r"(?i)\bE(\d+)\b", hidden_search_data)
            for s in seasons: variations.append(f"s{int(s)} s{str(int(s)).zfill(2)} season{int(s)}")
            for e in episodes: variations.append(f"e{int(e)} e{str(int(e)).zfill(2)} ep{int(e)}")
            for s in seasons:
                for e in episodes: variations.append(f"s{int(s)}e{int(e)} s{str(int(s)).zfill(2)}e{str(int(e)).zfill(2)}")

            for tag in ["part", "vol", "chapter", "ch"]:
                for v in re.findall(rf"(?i){tag}(?:ume)?\s*(\d+)", orig_raw): variations.append(f"{tag}{v}")

            variation_text = " ".join(list(set(variations)))
            spaceless_name = display_name.replace(" ", "").replace("-", "").replace(".", "")
            master_search_text = f"{display_name} {hidden_search_data} {spaceless_name} {variation_text}".lower()

            file_type = "video" if message.video else "document"

            data_docs.append({'_id': current_id, 'msg_id': message.id, 'chat_id': message.chat.id, 'file_id': media.file_id, 'file_unique_id': media.file_unique_id, 'file_type': file_type})
            
            search_doc = {'file_name': display_name, 'file_size': media.file_size, 'caption': caption, 'search_text': master_search_text, 'link_id': current_id, 'chat_id': message.chat.id, 'file_type': file_type}
            if parsed_meta['quality']: search_doc['quality'] = parsed_meta['quality']
            if parsed_meta['languages']: search_doc['languages'] = parsed_meta['languages']
            if parsed_meta['year']: search_doc['year'] = parsed_meta['year']

            search_docs.append(search_doc)
            current_id += 1

        if data_docs:
            try:
                await self.data_col.insert_many(data_docs, ordered=False)
                await self.search_col.insert_many(search_docs, ordered=False)
            except Exception as e: pass
        return len(data_docs), pre_duplicate_count

    async def get_file_details(self, link_id):
        return await self.data_col.find_one({'_id': int(link_id)})

    # ==================================================================
    # ⚡ HYBRID SEARCH: Stopword Remover & 100% Crash-Proof Python Fallback
    # ==================================================================
    async def get_search_results(self, query, file_type=None, lang=None, quality=None, year=None, size_range=None, sort="relevance"):
        if not query or not query.strip(): return []

        try:
            # ✅ TYPO FIXER
            query = re.sub(r"(?i)\b(englsh|engls|engish|egnlish)\b", "english", query)
            query = re.sub(r"(?i)\b(hndi|hind|hni|hin)\b", "hindi", query)
            query = re.sub(r"(?i)\b(tmal|taml|tmil|tam)\b", "tamil", query)
            query = re.sub(r"(?i)\b(telgu|tlgu|telug|telegu|tel)\b", "telugu", query)
            query = re.sub(r"(?i)\b(malyalam|malaylam|malyalm|malalam|mal)\b", "malayalam", query)
            query = re.sub(r"(?i)\b(kanada|kanda|kannad|kan)\b", "kannada", query)
            
            clean_query = query.strip().lower()
            raw_words = clean_query.split()
            
            # 🔥 STOPWORD REMOVER
            stop_words = {"the", "a", "an", "is", "of", "and", "in", "on", "for", "with", "to"}
            words = [w for w in raw_words if w not in stop_words]
            if not words: words = raw_words 
            
            meta_keywords = {
                "hindi", "tamil", "telugu", "malayalam", "kannada", "bengali", "punjabi", "marathi", "gujarati", "urdu", "english", 
                "1080p", "720p", "480p", "360p", "2160p", "4k", "bluray", "hdrip", "webrip", "cam", "dvdrip", "dual", "multi", "audio", "mkv", "mp4",
                "movie", "full", "hd", "print", "download", "series"
            }

            title_words = [w for w in words if not (re.match(r"^(19|20)\d{2}$", w) or w in meta_keywords)]
            if not title_words: title_words = words 

            alias_map = {"hindi": r"(hindi|hin)", "english": r"(english|eng)", "tamil": r"(tamil|tam)", "telugu": r"(telugu|tel)", "malayalam": r"(malayalam|mal)", "kannada": r"(kannada|kan)", "dual": r"(dual|multi)", "multi": r"(dual|multi)"}

            # 🚀 1. FAST FETCHING
            match_filters = {"$text": {"$search": " ".join(words)}}

            title_or_clauses = []
            for tw in title_words:
                safe_tw = re.escape(tw)
                title_or_clauses.append({"search_text": {"$regex": rf"\b{safe_tw}\b", "$options": "i"}})
                title_or_clauses.append({"file_name": {"$regex": rf"\b{safe_tw}\b", "$options": "i"}})
                
            if title_or_clauses: match_filters["$and"] = match_filters.get("$and", []) + [{"$or": title_or_clauses}]

            # Button Filters
            if file_type and file_type != "none": match_filters["file_type"] = "video" if file_type.lower() == "video" else "document"
            if lang and lang != "none":
                pattern = LANG_MAP.get(lang, lang)
                match_filters["$and"] = match_filters.get("$and", []) + [{"$or": [{"languages": lang}, {"file_name": {"$regex": pattern, "$options": "i"}}, {"caption": {"$regex": pattern, "$options": "i"}}]}]
            if quality and quality != "none":
                match_filters["$and"] = match_filters.get("$and", []) + [{"$or": [{"quality": quality}, {"file_name": {"$regex": quality, "$options": "i"}}, {"caption": {"$regex": quality, "$options": "i"}}]}]
            if year and year != "none":
                match_filters["$and"] = match_filters.get("$and", []) + [{"$or": [{"year": str(year)}, {"file_name": {"$regex": str(year)}}]}]
            if size_range and size_range != "none":
                MB_500, GB_1, GB_2 = 500*1024*1024, 1024*1024*1024, 2*1024*1024*1024
                if size_range == "min500": match_filters["file_size"] = {"$lt": MB_500}
                elif size_range == "500-1gb": match_filters["file_size"] = {"$gte": MB_500, "$lt": GB_1}
                elif size_range == "1gb-2gb": match_filters["file_size"] = {"$gte": GB_1, "$lt": GB_2}
                elif size_range == "max2gb": match_filters["file_size"] = {"$gte": GB_2}

            match_conditions = []
            
            if title_words:
                safe_first = re.escape(title_words[0])
                match_conditions.append({"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$file_name", ""]}, "regex": rf"^[\W_]*{safe_first}\b", "options": "i"}}, 50, 0]})

            for w in words:
                regex_pattern = alias_map.get(w, re.escape(w))
                is_lang = w in ["hindi", "tamil", "telugu", "malayalam", "kannada", "bengali", "english", "dual", "multi", "punjabi", "marathi"]
                is_meta = re.match(r"^(19|20)\d{2}$", w) or w in meta_keywords
                
                name_weight, text_weight = (100, 50) if is_lang else ((20, 5) if is_meta else (40, 10))
                
                match_conditions.append({"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$file_name", ""]}, "regex": rf"\b{regex_pattern}\b", "options": "i"}}, name_weight, 0]})
                match_conditions.append({"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$search_text", ""]}, "regex": rf"\b{regex_pattern}\b", "options": "i"}}, text_weight, 0]})

            pipeline = [
                {"$match": match_filters},
                {"$project": {"file_name": 1, "file_size": 1, "caption": 1, "search_text": 1, "quality": 1, "languages": 1, "year": 1, "source": 1, "link_id": 1, "chat_id": 1, "file_type": 1, "score": {"$meta": "textScore"}}},
                {"$addFields": {"custom_score": {"$add": match_conditions}}}
            ]

            if sort == "new": pipeline.append({"$sort": {"_id": -1}}) 
            elif sort == "old": pipeline.append({"$sort": {"_id": 1}}) 
            elif sort == "large": pipeline.append({"$sort": {"file_size": -1}}) 
            elif sort == "small": pipeline.append({"$sort": {"file_size": 1}}) 
            else: pipeline.append({"$sort": {"custom_score": -1, "score": {"$meta": "textScore"}, "_id": -1}}) 

            pipeline.append({"$limit": 100}) 
            cursor = self.search_col.aggregate(pipeline)
            return await cursor.to_list(length=100)

        except Exception as e:
            print(f"⚠️ Native Search Failed: {e}. Switching to Python Fallback.")
            # ==========================================================
            # ✅ 100% CRASH-PROOF PYTHON FALLBACK ENGINE
            # ==========================================================
            try:
                fallback_match = {}
                fallback_or_clauses = [{"search_text": {"$regex": rf"{re.escape(tw)}", "$options": "i"}} for tw in title_words] + [{"file_name": {"$regex": rf"{re.escape(tw)}", "$options": "i"}} for tw in title_words]
                if fallback_or_clauses: fallback_match["$and"] = [{"$or": fallback_or_clauses}]
                
                if file_type and file_type != "none": fallback_match["file_type"] = "video" if file_type.lower() == "video" else "document"
                if lang and lang != "none":
                    pattern = LANG_MAP.get(lang, lang)
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"languages": lang}, {"file_name": {"$regex": pattern, "$options": "i"}}, {"caption": {"$regex": pattern, "$options": "i"}}]}]
                if quality and quality != "none":
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"quality": quality}, {"file_name": {"$regex": quality, "$options": "i"}}, {"caption": {"$regex": quality, "$options": "i"}}]}]
                if year and year != "none":
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"year": str(year)}, {"file_name": {"$regex": str(year)}}]}]

                # Fetching max 150 docs to score in Python safely
                cursor = self.search_col.find(fallback_match).limit(150)
                files = await cursor.to_list(length=150)

                # Safe Python Scoring
                for f in files:
                    score = 0
                    fname = str(f.get("file_name", "")).lower()
                    stext = str(f.get("search_text", "")).lower()
                    
                    if title_words and re.search(rf"^[\W_]*{re.escape(title_words[0])}\b", fname):
                        score += 50
                        
                    for w in words:
                        pattern = alias_map.get(w, re.escape(w))
                        is_lang = w in ["hindi", "tamil", "telugu", "malayalam", "kannada", "bengali", "english", "dual", "multi", "punjabi", "marathi"]
                        is_meta = re.match(r"^(19|20)\d{2}$", w) or w in meta_keywords
                        n_weight = 100 if is_lang else (20 if is_meta else 40)
                        t_weight = 50 if is_lang else (5 if is_meta else 10)

                        if re.search(rf"\b{pattern}\b", fname): score += n_weight
                        elif re.search(rf"\b{pattern}\b", stext): score += t_weight
                    f["custom_score"] = score

                # Safe Sort using link_id (integers only, no ObjectId comparison crash!)
                if sort == "new": files.sort(key=lambda x: x.get("link_id", 0), reverse=True)
                elif sort == "old": files.sort(key=lambda x: x.get("link_id", 0))
                elif sort == "large": files.sort(key=lambda x: x.get("file_size", 0), reverse=True)
                elif sort == "small": files.sort(key=lambda x: x.get("file_size", 0))
                else: files.sort(key=lambda x: (x.get("custom_score", 0), x.get("link_id", 0)), reverse=True)
                
                return files[:100]
            except Exception as inner_e:
                print(f"❌ Python Fallback CRITICAL FAILURE: {inner_e}")
                traceback.print_exc()
                return []

    async def total_files_count(self): return await self.data_col.count_documents({})
    
    async def get_db_size(self):
        try:
            stats = await self.db.command("dbstats")
            return stats.get('storageSize', 0) + stats.get('totalIndexSize', 0)
        except: return 0

    async def save_search_results(self, query, files, chat_id):
        unique_id = str(uuid.uuid4())[:8]
        # ✅ FIX: Using .get() ensures Bot NEVER crashes due to missing keys
        simplified_files = [{
            "file_name": f.get('file_name', 'Unknown File'), 
            "file_size": f.get('file_size', 0), 
            "link_id": f.get('link_id', 0), 
            "file_chat_id": f.get('chat_id', 0), 
            "file_type": f.get('file_type', 'document')
        } for f in files]
        
        await self.search_cache.insert_one({"_id": unique_id, "query": query, "chat_id": chat_id, "files": simplified_files, "created_at": datetime.datetime.utcnow()})
        return unique_id

    async def get_cached_results(self, unique_id): 
        return await self.search_cache.find_one({"_id": unique_id})

Media = MediaDB(DATABASE_URI, DATABASE_NAME)
