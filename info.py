import os
import re

# Helper for ID parsing
id_pattern = re.compile(r'^-?\d+$')

# --- MANDATORY VARIABLES ---
API_ID = int(os.environ.get("API_ID", "12345")) 
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")
TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "9e1353ccc623e71f80262309cda5cdfb") # Default Test Key
DATABASE_URI = os.environ.get("DATABASE_URI", "your_mongo_uri")

# --- DATABASE SETTINGS ---
DATABASE_NAME = os.environ.get("DATABASE_NAME", "MyBotDB")
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'Telegram_files')
USER_DB_URI = os.environ.get("USER_DB_URI", "")
if not USER_DB_URI:
    USER_DB_URI = DATABASE_URI
  
# --- GENERAL SETTINGS ---
ADMINS = [int(i) for i in os.environ.get("ADMINS", "").split(" ")] if os.environ.get("ADMINS") else []
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0")) 
PORT = int(os.environ.get("PORT", "8080"))
CHANNELS = [int(ch) for ch in os.environ.get("CHANNELS", "0").split()] if os.environ.get("CHANNELS") else []

# Yahan -1001234567890 ki jagah apna asli Channel ID daalein
TARGET_CHANNEL_ID = int(os.environ.get("TARGET_CHANNEL_ID", "-1003719921511"))

# 👇 NAYA FEATURE: Streaming ke liye Bin Channel (Apne Database Channel ki ID daalein)
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", "-1003173929836"))

# ✅ SITE URL (REQUIRED FOR SITE MODE)
# Render/Heroku users must set this in Environment Variables (e.g., https://my-app.onrender.com)
# Do not add a trailing slash (/) at the end.
SITE_URL = os.environ.get("SITE_URL", "https://nainyj-56b575136034.herokuapp.com")

# --- VERIFICATION SETTINGS ---
IS_VERIFY = os.environ.get("IS_VERIFY", "True").lower() in ["true", "yes", "1"]
VERIFY_TIME = int(os.environ.get("VERIFY_TIME", 1200)) # 20 Min
VERIFY_GAP1 = int(os.environ.get("VERIFY_GAP1", 300))  # 5 Min
VERIFY_GAP2 = int(os.environ.get("VERIFY_GAP2", 300))  # 5 Min

# --- SHORTENER SETTINGS ---
SHORTLINK_URL_1 = os.environ.get("SHORTLINK_URL_1", "shortxlinks.com")
SHORTLINK_API_1 = os.environ.get("SHORTLINK_API_1", "7c480930494be0edb7e546125c35d79840d5146b")

SHORTLINK_URL_2 = os.environ.get("SHORTLINK_URL_2", "softurl.in")
SHORTLINK_API_2 = os.environ.get("SHORTLINK_API_2", "613ce973446725bfe2bf909b320c7a1e84c4bdc8")

SHORTLINK_URL_3 = os.environ.get("SHORTLINK_URL_3", "")
SHORTLINK_API_3 = os.environ.get("SHORTLINK_API_3", "")

# --- FSUB CHANNELS ---
# Slot 1 (Request FSub)
auth_channel = os.environ.get('AUTH_CHANNEL', '') 
AUTH_CHANNEL = int(auth_channel) if auth_channel and id_pattern.search(auth_channel) else None

# Slot 2 (Request FSub)
auth_channel_2 = os.environ.get('AUTH_CHANNEL_2', '')
AUTH_CHANNEL_2 = int(auth_channel_2) if auth_channel_2 and id_pattern.search(auth_channel_2) else None

# Slot 3 (Normal FSub)
auth_channel_3 = os.environ.get('AUTH_CHANNEL_3', '')
AUTH_CHANNEL_3 = int(auth_channel_3) if auth_channel_3 and id_pattern.search(auth_channel_3) else None

# Slot 4 (Post-Verify FSub)
auth_channel_4 = os.environ.get('AUTH_CHANNEL_4', '')
AUTH_CHANNEL_4 = int(auth_channel_4) if auth_channel_4 and id_pattern.search(auth_channel_4) else None
AUTH_CHANNEL_4_TEXT = os.environ.get('AUTH_CHANNEL_4_TEXT', '✅ Join Final Channel')

# --- OTHER SETTINGS ---
USE_CAPTION_FILTER = os.environ.get("USE_CAPTION_FILTER", "True").lower() in ["true", "yes", "1"]
MONGODB_TIMEOUT = 300 # 5 Minutes

# --- SEARCH SETTINGS ---
PM_SEARCH = os.environ.get("PM_SEARCH", "False").lower() in ["true", "yes", "1"]
