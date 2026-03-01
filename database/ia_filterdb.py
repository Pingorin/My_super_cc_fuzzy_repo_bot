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
            await self.search_col.create_index("file_name")
            await self.search_col.create_index("caption")
            await self.search_col.create_index("search_text") 
            await self.search_col.create_index("quality") 
            await self.search_col.create_index("languages") 
            await self.search_col.create_index("year") 
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

        text = re.sub(r"<[^>]+>", "", text)

        ext_regex = r"(?i)(.*?(?:\.(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)|\b(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)\b))"
        match = re.search(ext_regex, text, flags=re.DOTALL)
        if match:
            text = match.group(1)

        promo_patterns = r"@|t\.me/|https?://|www\.\w+|\w+\.(?:com|in|vip|org|net|me|xyz|site|cc|to|club|tech|link|app|click|store|hd)\b"
        text = re.sub(r"\[[^\]]*(?:" + promo_patterns + r")[^\]]*\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\([^)]*(?:" + promo_patterns + r")[^)]*\)", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\{[^}]*(?:" + promo_patterns + r")[^}]*\}", "", text, flags=re.IGNORECASE)

        text = re.sub(r"(https?://\S+|www\.\S+|t\.me/\S+|@\w+|\b\w+\.(?:com|in|vip|org|net|me|xyz|site|cc|to|club|tech|link|app|click|store|hd)\b)", "", text, flags=re.IGNORECASE)

        text = re.sub(r"[\u200b\u200c\u200d\u200e\u200f\ufeff\u202a-\u202e]", "", text)

        spam_and_tags = [
            r"download", r"full movie", r"free", r"watch online", r"join",
            r"esub", r"hc-esub", r"x264", r"x265", r"code"
        ]
        pattern = r"\b(" + "|".join(spam_and_tags) + r")\b"
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        text = re.sub(r"[^\w\s:()\[\]{}\-]|_", " ", text)
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    # ==================================================================
    # ✅ EXTRACT STRUCTURED METADATA
    # ==================================================================
    @staticmethod
    def parse_metadata(text):
        if not text:
            return {"cleaned_title": "", "quality": [], "languages": [], "source": [], "year": []}

        ext_regex = r"(?i)(.*?(?:\.(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)|\b(?:mkv|mp4|avi|webm|m4v|flv|zip|rar|pdf|mka)\b))"
        match = re.search(ext_regex, text, flags=re.DOTALL)
        if match:
            text = match.group(1)

        cleaned_title = text
        metadata = {
            "quality": set(),
            "languages": set(),
            "source": set(),
            "year": set()
        }

        res_pattern = r"(?i)\b(480p|720p|1080p|2160p|4k|uhd)\b"
        for m in re.finditer(res_pattern, cleaned_title):
            val = m.group(1).lower()
            if val in ['4k', 'uhd']: val = '2160p'
            metadata['quality'].add(val)
        cleaned_title = re.sub(res_pattern, "", cleaned_title)

        src_pattern = r"(?i)\b(web-dl|webrip|bluray|brrip|hdrip|hdcam|predvdrip)\b"
        for m in re.finditer(src_pattern, cleaned_title):
            metadata['source'].add(m.group(1).upper()) 
        cleaned_title = re.sub(src_pattern, "", cleaned_title)

        lang_map = {
            'hin': 'Hindi', 'hindi': 'Hindi',
            'tam': 'Tamil', 'tamil': 'Tamil',
            'tel': 'Telugu', 'telugu': 'Telugu',
            'mal': 'Malayalam', 'malayalam': 'Malayalam',
            'kan': 'Kannada', 'kannada': 'Kannada',
            'eng': 'English', 'english': 'English',
            'multi': 'Multi Audio', 'dual': 'Dual Audio'
        }
        lang_pattern = r"(?i)\b(hindi|hin|tamil|tam|telugu|tel|malayalam|mal|kannada|kan|english|eng|multi[\s\-]?audio|dual[\s\-]?audio)\b"
        for m in re.finditer(lang_pattern, cleaned_title):
            val = m.group(1).lower().replace('-', ' ').replace('audio', '').strip()
            if val in lang_map:
                metadata['languages'].add(lang_map[val])
        cleaned_title = re.sub(lang_pattern, "", cleaned_title)

        year_pattern = r"\b(19\d{2}|20\d{2})\b"
        for m in re.finditer(year_pattern, cleaned_title):
            metadata['year'].add(m.group(1))
        cleaned_title = re.sub(year_pattern, "", cleaned_title)

        promo_patterns = r"@|t\.me/|https?://|www\.\w+|\w+\.(?:com|in|vip|org|net|me|xyz|site|cc|to|club|tech|link|app|click|store|hd)\b"
        cleaned_title = re.sub(r"<[^>]+>", "", cleaned_title)
        cleaned_title = re.sub(promo_patterns, "", cleaned_title, flags=re.IGNORECASE)
        cleaned_title = re.sub(r"\[[\s\+\-\|]*\]|\([\s\+\-\|]*\)", "", cleaned_title)
        cleaned_title = re.sub(r"[^\w\s:()\[\]{}\-]|_", " ", cleaned_title)
        cleaned_title = re.sub(r"\s+", " ", cleaned_title).strip()

        return {
            "cleaned_title": cleaned_title,
            "quality": list(metadata["quality"]),
            "languages": list(metadata["languages"]),
            "source": list(metadata["source"]),
            "year": list(metadata["year"])
        }

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
                
            # ✅ CAPTION BUG FIXED & METADATA MERGED
            meta_name = self.parse_metadata(media.file_name)
            raw_caption = message.caption.html if message.caption else ""
            meta_cap = self.parse_metadata(raw_caption)

            parsed_meta = {
                "quality": list(set(meta_name['quality'] + meta_cap['quality'])),
                "languages": list(set(meta_name['languages'] + meta_cap['languages'])),
                "year": list(set(meta_name['year'] + meta_cap['year'])),
                "source": list(set(meta_name['source'] + meta_cap['source']))
            }

            # ==========================================================
            # 🔥 HIDDEN SEARCH INDEXING
            # ==========================================================
            hidden_search_data = display_name

            hidden_search_data = re.sub(r"(?i)\bS(\d+)\s*E(\d+)\b", r"S\1 E\2", hidden_search_data)

            def expand_season(match):
                start, end = int(match.group(1)), int(match.group(2))
                if start > end or end - start > 50: return match.group(0)
                return " ".join([f"S{str(i).zfill(2)}" for i in range(start, end + 1)])
            hidden_search_data = re.sub(r"(?i)\bS(\d+)\s*(?:-|to)\s*(?:S)?(\d+)\b", expand_season, hidden_search_data)
            
            def expand_episode(match):
                start, end = int(match.group(1)), int(match.group(2))
                if start > end or end - start > 200: return match.group(0)
                return " ".join([f"E{str(i).zfill(2)}" for i in range(start, end + 1)])
            hidden_search_data = re.sub(r"(?i)\bE(\d+)\s*(?:-|to)\s*(?:E)?(\d+)\b", expand_episode, hidden_search_data)

            hidden_search_data = re.sub(r"(?i)\b(\d{1,2})\s*x\s*(\d{1,4})\b", r"S\1 E\2", hidden_search_data)
            hidden_search_data = re.sub(r"(?i)\b(?:season|s)\s*(\d+)\b", r"S\1", hidden_search_data)
            hidden_search_data = re.sub(r"(?i)\b(?:episode|ep|e)\s*(\d+)\b", r"E\1", hidden_search_data)

            variations = []
            orig_raw = media.file_name.lower()
            
            seasons = re.findall(r"(?i)\bS(\d+)\b", hidden_search_data)
            episodes = re.findall(r"(?i)\bE(\d+)\b", hidden_search_data)

            s_nums = []
            for s in seasons:
                s_num = int(s)
                s_pad = str(s_num).zfill(2)
                s_nums.append((s_num, s_pad))
                variations.append(f"s{s_num} s{s_pad} so{s_num} season{s_num} season {s_num}")

            e_nums = []
            for e in episodes:
                e_num = int(e)
                e_pad = str(e_num).zfill(2)
                e_nums.append((e_num, e_pad))
                variations.append(f"e{e_num} e{e_pad} eo{e_num} ep{e_num} ep {e_num} episode{e_num} episode {e_num}")

            for s_num, s_pad in s_nums:
                for e_num, e_pad in e_nums:
                    variations.append(f"s{s_num}e{e_num} s{s_pad}e{e_pad} season {s_num} episode {e_num}")

            if "part" in orig_raw:
                parts = re.findall(r"(?i)part\s*(\d+)", orig_raw)
                for p in parts: variations.append(f"part{p} p{p}")
            if "vol" in orig_raw:
                vols = re.findall(r"(?i)vol(?:ume)?\s*(\d+)", orig_raw)
                for v in vols: variations.append(f"vol{v} volume{v} v{v}")
            if "chapter" in orig_raw or "ch" in orig_raw:
                chaps = re.findall(r"(?i)(?:chapter|ch)\s*(\d+)", orig_raw)
                for c in chaps: variations.append(f"chapter{c} ch{c}")

            variation_text = " ".join(list(set(variations)))

            spaceless_name = display_name.replace(" ", "").replace("-", "").replace(".", "")
            spaceless_cap = cap_text.replace(" ", "").replace("-", "").replace(".", "")

            master_search_text = f"{display_name} {hidden_search_data} {spaceless_name} {spaceless_cap} {variation_text}".lower()
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
            
            # ✅ Base Search Document
            search_doc = {
                'file_name': display_name,
                'file_size': media.file_size, 
                'caption': caption,
                'search_text': master_search_text, 
                'link_id': current_id,
                'chat_id': message.chat.id,
                'file_type': file_type 
            }

            # ✅ MEMORY OPTIMIZATION: Simple Keys
            if parsed_meta['quality']:
                search_doc['quality'] = parsed_meta['quality']
            
            if parsed_meta['languages']:
                search_doc['languages'] = parsed_meta['languages']
                
            if parsed_meta['year']:
                search_doc['year'] = parsed_meta['year']
                
            if parsed_meta['source']:
                search_doc['source'] = parsed_meta['source']

            search_docs.append(search_doc)
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
    # ⚡ OPTIMIZED SMART REGEX SEARCH
    # ==================================================================
    async def get_search_results(self, query, file_type=None, lang=None, quality=None, year=None, size_range=None, sort="relevance"):
        try:
            # ==========================================================
            # 🔥 COMPLETE LANGUAGE TYPO FIXER (Spell Checker)
            # ==========================================================
            query = re.sub(r"(?i)\b(englsh|engls|engish|egnlish)\b", "english", query)
            query = re.sub(r"(?i)\b(hndi|hind|hni)\b", "hindi", query)
            query = re.sub(r"(?i)\b(tmal|taml|tmil)\b", "tamil", query)
            query = re.sub(r"(?i)\b(telgu|tlgu|telug|telegu)\b", "telugu", query)
            query = re.sub(r"(?i)\b(malyalam|malaylam|malyalm|malalam)\b", "malayalam", query)
            query = re.sub(r"(?i)\b(kanada|kanda|kannad)\b", "kannada", query)
            query = re.sub(r"(?i)\b(bengli|bangali|bngali)\b", "bengali", query)
            query = re.sub(r"(?i)\b(punjbi|panjabi|pnjabi)\b", "punjabi", query)
            query = re.sub(r"(?i)\b(marthi|mrathi)\b", "marathi", query)
            query = re.sub(r"(?i)\b(gujrati|gujrti)\b", "gujarati", query)
            query = re.sub(r"(?i)\b(daul\s*audio|dualaudio|dual\s*adiuo)\b", "dual audio", query)
            query = re.sub(r"(?i)\b(mlti\s*audio|multiaudio|multi\s*adiuo)\b", "multi audio", query)
            # ==========================================================

            # ✅ QUERY PROCESSING
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
            match_filters = {"$and": and_clauses} if and_clauses else {}
            
            if file_type and file_type != "none":
                capital_type = "video" if file_type.lower() == "video" else "document"
                match_filters["file_type"] = capital_type

            # ✅ FAST BUTTON FILTERS (Simple Keys)
            if lang and lang != "none":
                pattern = LANG_MAP.get(lang, lang)
                if "$and" not in match_filters: match_filters["$and"] = []
                match_filters["$and"].append({
                    "$or": [
                        {"languages": lang},
                        {"file_name": {"$regex": pattern, "$options": "i"}},
                        {"caption": {"$regex": pattern, "$options": "i"}}
                    ]
                })

            if quality and quality != "none":
                if "$and" not in match_filters: match_filters["$and"] = []
                match_filters["$and"].append({
                    "$or": [
                        {"quality": quality},
                        {"file_name": {"$regex": quality, "$options": "i"}},
                        {"caption": {"$regex": quality, "$options": "i"}}
                    ]
                })
            
            if year and year != "none":
                if "$and" not in match_filters: match_filters["$and"] = []
                match_filters["$and"].append({
                    "$or": [
                        {"year": str(year)},
                        {"file_name": {"$regex": str(year)}}
                    ]
                })

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
                pipeline.append({"$sort": {"_id": -1}}) 
            elif sort == "old":
                pipeline.append({"$sort": {"_id": 1}}) 
            elif sort == "large":
                pipeline.append({"$sort": {"file_size": -1}}) 
            elif sort == "small":
                pipeline.append({"$sort": {"file_size": 1}}) 
            else:
                pipeline.append({"$sort": {"_id": -1}}) 

            pipeline.append({"$limit": 100}) 

            cursor = self.search_col.aggregate(pipeline)
            files = await cursor.to_list(length=100)
            return files
            
        except Exception as e:
            print(f"⚠️ Index Search Failed: {e}. Switching to Fallback.")
            
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
                
                db_langs = f.get('languages', [])
                if lang and lang != "none":
                    if db_langs:
                        if lang not in db_langs: continue
                    else:
                        pattern = LANG_MAP.get(lang, lang).lower()
                        if not re.search(pattern, full_text): continue

                db_quals = f.get('quality', [])
                if quality and quality != "none":
                    if db_quals:
                        if quality not in db_quals: continue
                    else:
                        if quality.lower() not in full_text: continue

                db_years = f.get('year', [])
                if year and year != "none":
                    if db_years:
                        if str(year) not in db_years: continue
                    else:
                        if str(year) not in fname: continue
                
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
