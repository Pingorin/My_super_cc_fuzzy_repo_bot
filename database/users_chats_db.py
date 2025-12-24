import motor.motor_asyncio
import time
import datetime
from info import DATABASE_URI, DATABASE_NAME

class UserChatDB:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.users = self.db.users
        self.groups = self.db.groups
        self.banned = self.db.banned 
        self.fsub_pending = self.db.fsub_pending # ✅ Join Requests के लिए कलेक्शन
        self.req = self.db.join_req # Join Request collection (Legacy support के लिए)

    async def add_user(self, id):
        user = await self.users.find_one({'id': int(id)})
        if not user:
            await self.users.insert_one({'id': int(id)})

    # ✅ चेक करता है कि ग्रुप डेटाबेस में है या नहीं
    async def get_chat(self, chat_id):
        chat = await self.groups.find_one({'id': int(chat_id)})
        return chat if chat else False
    
    # ✅ सभी ग्रुप्स की लिस्ट लाता है (/settings कमांड के लिए जरूरी)
    async def get_all_chats(self):
        return self.groups.find({})

    # ✅ नया ग्रुप ऑब्जेक्ट बनाता है (डिफ़ॉल्ट सेटिंग्स के साथ)
    def new_group(self, chat_id, title):
        return {
            'id': int(chat_id),
            'title': title,
            'chat_status': True,
            'earning_method': 'shortlink',
            'shortener_mode': 'dynamic',
            'shorteners': {},
            'fsub_channels': {},
            'is_shortlink_active': True,
            'time_dynamic': 86400,
            'time_smart': 86400,
            'time_together': 604800,
            'time_together_3': 86400,
            'time_gap1': 300,
            'time_gap2': 300
        }

    # ✅ ग्रुप को Title के साथ डेटाबेस में सेव या अपडेट करना
    async def add_chat(self, chat_id, title):
        chat_dict = self.new_group(chat_id, title)
        # अगर ग्रुप पहले से है तो अपडेट करेगा, नहीं तो नया बनाएगा (upsert=True)
        await self.groups.update_one({'id': int(chat_id)}, {'$set': chat_dict}, upsert=True)

    # ✅ ग्रुप को डिफ़ॉल्ट सेटिंग्स के साथ जोड़ना (पुराने कोड के सपोर्ट के लिए)
    async def add_group(self, id):
        group = await self.groups.find_one({'id': int(id)})
        if not group:
            chat = self.new_group(id, "Group") 
            await self.groups.insert_one(chat)

    # --- ⚙️ ग्रुप सेटिंग्स के लिए हेल्पर्स ---
    
    async def get_group_settings(self, id):
        return await self.groups.find_one({'id': int(id)})

    async def update_group_settings(self, id, settings):
        await self.groups.update_one({'id': int(id)}, {'$set': settings})

    # --- शॉर्टनर मैनेजमेंट ---
    async def add_shortener(self, chat_id, slot, site, api):
        key = f"shorteners.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': {key: {'site': site, 'api': api}}}
        )

    async def remove_shortener(self, chat_id, slot):
        key = f"shorteners.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {key: ""}}
        )

    # --- 🔒 FSUB चैनल मैनेजमेंट ---
    async def update_fsub_channel(self, chat_id, slot, channel_id):
        key = f"fsub_channels.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$set': {key: int(channel_id)}},
            upsert=True
        )

    async def remove_fsub_channel(self, chat_id, slot):
        key = f"fsub_channels.{slot}"
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {key: ""}}
        )

    async def remove_all_fsub_channels(self, chat_id):
        await self.groups.update_one(
            {'id': int(chat_id)},
            {'$unset': {'fsub_channels': ""}}
        )

    # --- 📊 स्टेट्स और बैन लॉजिक ---

    async def total_users_count(self):
        return await self.users.count_documents({})

    async def total_groups_count(self):
        return await self.groups.count_documents({})

    async def get_banned(self):
        users = []
        chats = []
        async for banned_user in self.banned.find({"type": "user"}):
            users.append(banned_user["id"])
        async for banned_chat in self.banned.find({"type": "chat"}):
            chats.append(banned_chat["id"])
        return users, chats

    async def add_ban(self, id, type="user"):
        is_exist = await self.banned.find_one({"id": int(id), "type": type})
        if not is_exist:
            await self.banned.insert_one({"id": int(id), "type": type})

    async def remove_ban(self, id, type="user"):
        await self.banned.delete_one({"id": int(id), "type": type})

    # --- 🔒 वेरिफिकेशन सिस्टम ---
    
    async def get_verify_status(self, user_id, chat_id):
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})
            if isinstance(all_verifications, (int, float)): return False
            chat_data = all_verifications.get(str(chat_id), {})
            if isinstance(chat_data, (int, float)): return False
            return chat_data.get('0', 0) > time.time()
        return False

    async def get_level_time(self, user_id, chat_id, level):
        user = await self.users.find_one({'id': int(user_id)})
        if user:
            all_verifications = user.get('verify_status', {})
            if isinstance(all_verifications, (int, float)): return 0
            chat_data = all_verifications.get(str(chat_id), {})
            if isinstance(chat_data, (int, float)): return 0
            return chat_data.get(str(level), 0)
        return 0

    async def update_verify_status(self, user_id, chat_id, level, duration=0, is_reset=False):
        current_time = time.time()
        if is_reset:
            value = 0 
        elif duration > 0:
            value = current_time + duration 
        else:
            value = current_time 

        user = await self.users.find_one({'id': int(user_id)})
        if user:
            current_status = user.get('verify_status')
            if isinstance(current_status, (int, float)):
                await self.users.update_one({'id': int(user_id)}, {'$set': {'verify_status': {}}})
            elif isinstance(current_status, dict):
                chat_status = current_status.get(str(chat_id))
                if isinstance(chat_status, (int, float)):
                    await self.users.update_one({'id': int(user_id)}, {'$set': {f'verify_status.{str(chat_id)}': {}}})

        key_name = f"verify_status.{str(chat_id)}.{str(level)}"
        await self.users.update_one(
            {'id': int(user_id)},
            {'$set': {key_name: value}},
            upsert=True
        )

    # --- 🔥 जॉइन रिक्वेस्ट लॉजिक (FSUB) ---
    
    async def add_pending_request(self, user_id, channel_id):
        try:
            await self.fsub_pending.update_one(
                {'_id': f"{user_id}_{channel_id}"},
                {'$set': {'user_id': int(user_id), 'chat_id': int(channel_id), 'date': datetime.datetime.now()}},
                upsert=True
            )
        except Exception as e:
            print(f"Error adding pending request: {e}")

    async def is_user_pending(self, user_id, channel_id):
        try:
            found = await self.fsub_pending.find_one({'_id': f"{user_id}_{channel_id}"})
            return bool(found)
        except:
            return False

    async def remove_pending_request(self, user_id, channel_id):
        try:
            await self.fsub_pending.delete_one({'_id': f"{user_id}_{channel_id}"})
        except Exception as e:
            print(f"Error removing pending request: {e}")

db = UserChatDB(DATABASE_URI, DATABASE_NAME)
