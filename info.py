import os

# Mandatory Variables
API_ID = int(os.environ.get("API_ID", "12345")) # अपना API ID डालें (अगर Local run कर रहे हैं)
API_HASH = os.environ.get("API_HASH", "apna_hash_yahan")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "apna_bot_token")
DATABASE_URI = os.environ.get("DATABASE_URI", "apna_mongodb_url")

# 👇 Ye Naya Variable Add Karein (Zaruri Hai)
DATABASE_NAME = os.environ.get("DATABASE_NAME", "MyBotDB")

# Optional
ADMINS = [int(i) for i in os.environ.get("ADMINS", "").split(" ")] if os.environ.get("ADMINS") else []
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0")) # Agar log channel nahi hai to 0 rakhein
PORT = int(os.environ.get("PORT", "8080"))
# Channel ID jahan files upload hoti hain (Multiple IDs comma laga kar daal sakte hain)
CHANNELS = [-1003342421845] 

# --- VERIFICATION SETTINGS ---
IS_VERIFY = True
VERIFY_EXPIRE = 24 * 60 * 60 # 24 Hours

# LEVEL 1 (Mandatory if verify ON)
SHORTLINK_URL_1 = "shortxlinks.com"
SHORTLINK_API_1 = "7c480930494be0edb7e546125c35d79840d5146b"

# LEVEL 2 (Optional - Leave empty to disable)
SHORTLINK_URL_2 = "softurl.in"
SHORTLINK_API_2 = "613ce973446725bfe2bf909b320c7a1e84c4bdc8"

# LEVEL 3 (Optional - Leave empty to disable)
SHORTLINK_URL_3 = ""
SHORTLINK_API_3 = ""
