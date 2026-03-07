import logging
import re
import datetime
import uuid
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

    async def ensure_indexes(self):
        try:
            try:
                await self.search_col.drop_indexes()
                print("♻️ Old Indexes Dropped Successfully.")
            except OperationFailure:
                pass 

            await self.search_col.create_index("file_name")
            await self.search_col.create_index("caption")
            await self.search_col.create_index("search_text") 
            await self.search_col.create_index("quality") 
            await self.search_col.create_index("languages") 
            await self.search_col.create_index("year") 
            await self.search_col.create_index("link_id")
            
            # 🚀 FULL-TEXT INDEX 
            await self.search_col.create_index(
                [
                    ("file_name", TEXT),
                    ("search_text", TEXT),
                    ("caption", TEXT),
                    ("languages", TEXT),
                    ("quality", TEXT),
                    ("year", TEXT)
                ],
                name="weighted_movie_search"
            )

            await self.data_col.create_index("file_unique_id", unique=True)
            await self.search_cache.create_index("created_at", expireAfterSeconds=3600)
            await self.temp_searches.create_index("created_at", expireAfterSeconds=172800)
            
            print("✅ Database Indexes Created Successfully!")
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
    # ⚡ MASTERMIND SCORING SEARCH (Beats/Beat, The/Your, Exact Matches Fixed)
    # ==================================================================
    async def get_search_results(self, query, file_type=None, lang=None, quality=None, year=None, size_range=None, sort="relevance"):
        if not query or not query.strip(): return []

        try:
            # ✅ TYPO FIXER
            raw_query = query.strip().lower()
            clean_query = re.sub(r"(?i)\b(englsh|engls|engish|egnlish)\b", "english", raw_query)
            clean_query = re.sub(r"(?i)\b(hndi|hind|hni|hin)\b", "hindi", clean_query)
            clean_query = re.sub(r"(?i)\b(tmal|taml|tmil|tam)\b", "tamil", clean_query)
            clean_query = re.sub(r"(?i)\b(telgu|tlgu|telug|telegu|tel)\b", "telugu", clean_query)
            clean_query = re.sub(r"(?i)\b(malyalam|malaylam|malyalm|malalam|mal)\b", "malayalam", clean_query)
            clean_query = re.sub(r"(?i)\b(kanada|kanda|kannad|kan)\b", "kannada", clean_query)
            
            raw_words = clean_query.split()
            if not raw_words: return []

            # 🚀 Smart Stopwords (Only for MongoDB fetch)
            stop_words = {"the", "a", "an", "is", "of", "and", "in", "on", "for", "with", "to"}
            text_search_words = [w for w in raw_words if w not in stop_words]
            
            # 🔥 PLURAL/SINGULAR INJECTOR FOR MONGODB ("beat" -> "beat beats")
            expanded_text_words = []
            for w in text_search_words:
                expanded_text_words.append(w)
                if w.endswith('s') and len(w) > 3 and not w.endswith('ss'):
                    expanded_text_words.append(w[:-1])
                elif len(w) > 2 and not w.endswith('s'):
                    expanded_text_words.append(w + 's')
                    
            clean_query_for_text = " ".join(expanded_text_words) if expanded_text_words else " ".join(raw_words)

            # ALL Scoring uses the pure raw words! So "The Batman" keeps its "The"
            words = raw_words 

            meta_keywords = {
                "hindi", "tamil", "telugu", "malayalam", "kannada", "bengali", "punjabi", "marathi", "gujarati", "urdu", "english", 
                "1080p", "720p", "480p", "360p", "2160p", "4k", "bluray", "hdrip", "webrip", "cam", "dvdrip", "dual", "multi", "audio", "mkv", "mp4",
                "movie", "full", "hd", "print", "download", "series"
            }

            title_words = [w for w in words if not (re.match(r"^(19|20)\d{2}$", w) or w in meta_keywords)]
            if not title_words: title_words = words 

            # 🚀 1. FAST FETCHING ($match)
            # Yaha koi strict filter nahi hai, toh "The Batman" search karne par "Batman 1989" bhi aaram se pass hoga!
            match_filters = {"$text": {"$search": clean_query_for_text}}

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

            # 🚀 2. THE MASTERMIND SCORING
            match_conditions = [0] 
            alias_map = {
                "hindi": r"(hindi|hin)", "english": r"(english|eng)", "tamil": r"(tamil|tam)", "telugu": r"(telugu|tel)",
                "malayalam": r"(malayalam|mal)", "kannada": r"(kannada|kan)", "dual": r"(dual|multi)", "multi": r"(dual|multi)"
            }
            
            safe_raw_query = re.escape(clean_query)
            safe_title_phrase = re.escape(" ".join(title_words))
            safe_first_word = re.escape(title_words[0]) if title_words else ""

            # 🏆 EXACT PHRASE MATCH (+5000 Points): "The Batman" hai toh seedha Rank 1
            match_conditions.append({
                "$cond": [{"$regexMatch": {"input": {"$ifNull": ["$file_name", ""]}, "regex": rf"\b{safe_raw_query}\b", "options": "i"}}, 5000, 0]
            })
            
            # 🏆 EXACT TITLE PHRASE (+1000 Points): "Leo Hindi" ke time "Leo" ko rank karega
            if safe_title_phrase and safe_title_phrase != safe_raw_query:
                match_conditions.append({
                    "$cond": [{"$regexMatch": {"input": {"$ifNull": ["$file_name", ""]}, "regex": rf"\b{safe_title_phrase}\b", "options": "i"}}, 1000, 0]
                })

            # 🏆 STARTS-WITH FIRST WORD (+500 Points)
            if safe_first_word:
                match_conditions.append({
                    "$cond": [{"$regexMatch": {"input": {"$ifNull": ["$file_name", ""]}, "regex": rf"^[\W_]*{safe_first_word}\b", "options": "i"}}, 500, 0]
                })

            # 🏆 INDIVIDUAL WORD POINTS & PLURALS
            for w in words: 
                is_lang = w in ["hindi", "tamil", "telugu", "malayalam", "kannada", "bengali", "english", "dual", "multi", "punjabi", "marathi"]
                is_meta = re.match(r"^(19|20)\d{2}$", w) or w in meta_keywords
                
                if w in alias_map:
                    safe_w_regex = rf"\b{alias_map[w]}\b"
                else:
                    # 'beats' aur 'beat' dono ek dusre ko match karenge!
                    base = w[:-1] if (w.endswith('s') and len(w) > 3 and not w.endswith('ss')) else w
                    safe_w_regex = rf"\b{re.escape(base)}s?\b"
                
                # 🔥 LANGUAGE KILL-SWITCH (Hindi in Name = +300 pts, Meta = +20 pts)
                name_weight = 300 if is_lang else (20 if is_meta else 100)
                text_weight = 50 if is_lang else (5 if is_meta else 20)
                
                match_conditions.append({"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$file_name", ""]}, "regex": safe_w_regex, "options": "i"}}, name_weight, 0]})
                match_conditions.append({"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$search_text", ""]}, "regex": safe_w_regex, "options": "i"}}, text_weight, 0]})

            pipeline = [
                {"$match": match_filters},
                {"$project": {
                    "file_name": 1, "file_size": 1, "caption": 1, "search_text": 1, "quality": 1, "languages": 1, 
                    "year": 1, "source": 1, "link_id": 1, "chat_id": 1, "file_type": 1, "score": {"$meta": "textScore"},
                    "name_length": {"$strLenCP": {"$ifNull": ["$file_name", ""]}}
                }},
                {"$addFields": {"custom_score": {"$add": match_conditions}}}
            ]

            # 🚀 3. ULTIMATE SORTING (Score -> Length Tie Breaker -> Newest)
            if sort == "new": pipeline.append({"$sort": {"_id": -1}}) 
            elif sort == "old": pipeline.append({"$sort": {"_id": 1}}) 
            elif sort == "large": pipeline.append({"$sort": {"file_size": -1}}) 
            elif sort == "small": pipeline.append({"$sort": {"file_size": 1}}) 
            else:
                pipeline.append({"$sort": {"custom_score": -1, "name_length": 1, "_id": -1}}) 

            pipeline.append({"$limit": 100}) 

            cursor = self.search_col.aggregate(pipeline)
            files = await cursor.to_list(length=100)
            
            # 🔥 THIS FIXES THE "THE" / "YOUR" EMPTY RESULT BUG!
            if not files:
                raise Exception("Empty Text Search Result. Forcing Safe Fallback.")
                
            return files

        except Exception as e:
            print(f"⚠️ Native Search Failed or Empty: {e}. Switching to Fallback.")
            # ==========================================================
            # ✅ SAFE REGEX FALLBACK LOGIC
            # ==========================================================
            try:
                fallback_match = {}
                fallback_or_clauses = []
                
                # Fallback mein ANY WORD match karna allow karenge, toh koi file chhutegi nahi
                for tw in words:
                    if tw in alias_map:
                        safe_tw = rf"\b{alias_map[tw]}\b"
                    else:
                        base = tw[:-1] if (tw.endswith('s') and len(tw) > 3 and not tw.endswith('ss')) else tw
                        safe_tw = rf"\b{re.escape(base)}s?\b"
                        
                    fallback_or_clauses.append({"search_text": {"$regex": safe_tw, "$options": "i"}})
                    fallback_or_clauses.append({"file_name": {"$regex": safe_tw, "$options": "i"}})
                    
                if fallback_or_clauses: 
                    fallback_match["$or"] = fallback_or_clauses
                
                if file_type and file_type != "none": fallback_match["file_type"] = "video" if file_type.lower() == "video" else "document"
                if lang and lang != "none":
                    pattern = LANG_MAP.get(lang, lang)
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"languages": lang}, {"file_name": {"$regex": pattern, "$options": "i"}}, {"caption": {"$regex": pattern, "$options": "i"}}]}]
                if quality and quality != "none":
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"quality": quality}, {"file_name": {"$regex": quality, "$options": "i"}}, {"caption": {"$regex": quality, "$options": "i"}}]}]
                if year and year != "none":
                    fallback_match["$and"] = fallback_match.get("$and", []) + [{"$or": [{"year": str(year)}, {"file_name": {"$regex": str(year)}}]}]

                fallback_pipeline = [
                    {"$match": fallback_match},
                    {"$project": {
                        "file_name": 1, "file_size": 1, "caption": 1, "search_text": 1, "quality": 1, "languages": 1, 
                        "year": 1, "source": 1, "link_id": 1, "chat_id": 1, "file_type": 1,
                        "name_length": {"$strLenCP": {"$ifNull": ["$file_name", ""]}}
                    }},
                    {"$addFields": {"custom_score": {"$add": match_conditions}}}
                ]
                
                if sort == "new": fallback_pipeline.append({"$sort": {"_id": -1}})
                elif sort == "old": fallback_pipeline.append({"$sort": {"_id": 1}})
                elif sort == "large": fallback_pipeline.append({"$sort": {"file_size": -1}})
                elif sort == "small": fallback_pipeline.append({"$sort": {"file_size": 1}})
                else: fallback_pipeline.append({"$sort": {"custom_score": -1, "name_length": 1, "_id": -1}})

                fallback_pipeline.append({"$limit": 100})
                cursor = self.search_col.aggregate(fallback_pipeline)
                return await cursor.to_list(length=100)
            except Exception as inner_e:
                print(f"❌ Fallback also failed: {inner_e}")
                return []

    async def total_files_count(self):
        return await self.data_col.count_documents({})
        
    async def get_db_size(self):
        try:
            stats = await self.db.command("dbstats")
            return stats.get('storageSize', 0) + stats.get('totalIndexSize', 0)
        except:
            return 0

    async def save_search_results(self, query, files, chat_id):
        unique_id = str(uuid.uuid4())[:8]
        simplified_files = []
        for file in files:
            simplified_files.append({
                "file_name": file.get('file_name', 'Unknown'), "file_size": file.get('file_size', 0), "link_id": file.get('link_id', 0),
                "file_chat_id": file.get('chat_id', 0), "file_type": file.get('file_type', 'document')
            })
        await self.search_cache.insert_one({"_id": unique_id, "query": query, "chat_id": chat_id, "files": simplified_files, "created_at": datetime.datetime.utcnow()})
        return unique_id

    async def get_cached_results(self, unique_id):
        return await self.search_cache.find_one({"_id": unique_id})

Media = MediaDB(DATABASE_URI, DATABASE_NAME)
