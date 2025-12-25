import os
import re

# Helper for ID parsing (IDs check karne ke liye)
id_pattern = re.compile(r'^-?\d+$')

# Mandatory Variables
API_ID = int(os.environ.get("API_ID", "12345")) 
API_HASH = os.environ.get("API_HASH", "apna_hash_yahan")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "apna_bot_token")
DATABASE_URI = os.environ.get("DATABASE_URI", "apna_mongodb_url")

# Database Names
DATABASE_NAME = os.environ.get("DATABASE_NAME", "MyBotDB")
USER_DB_URI = os.environ.get("USER_DB_URI", "")
if not USER_DB_URI:
    USER_DB_URI = DATABASE_URI
  
# Optional
ADMINS = [int(i) for i in os.environ.get("ADMINS", "").split(" ")] if os.environ.get("ADMINS") else []
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0")) 
PORT = int(os.environ.get("PORT", "8080"))
CHANNELS = [-1003342421845] 

# --- VERIFICATION SETTINGS ---
# Environment variable se control karne ke liye update kiya gaya hai
IS_VERIFY = os.environ.get("IS_VERIFY", "True").lower() in ["true", "yes", "1"]

# Verification Time & Gaps
VERIFY_TIME = int(os.environ.get("VERIFY_TIME", 1200)) # 20 Min
VERIFY_GAP1 = int(os.environ.get("VERIFY_GAP1", 300))  # 5 Min
VERIFY_GAP2 = int(os.environ.get("VERIFY_GAP2", 300))  # 5 Min

# Shortener Info
SHORTLINK_URL_1 = os.environ.get("SHORTLINK_URL_1", "shortxlinks.com")
SHORTLINK_API_1 = os.environ.get("SHORTLINK_API_1", "7c480930494be0edb7e546125c35d79840d5146b")

SHORTLINK_URL_2 = os.environ.get("SHORTLINK_URL_2", "softurl.in")
SHORTLINK_API_2 = os.environ.get("SHORTLINK_API_2", "613ce973446725bfe2bf909b320c7a1e84c4bdc8")

SHORTLINK_URL_3 = os.environ.get("SHORTLINK_URL_3", "softurl.in")
SHORTLINK_API_3 = os.environ.get("SHORTLINK_API_3", "613ce973446725bfe2bf909b320c7a1e84c4bdc8")

# =========================================================
# 🔥 FSUB CHANNELS (Error Fix & New Feature)
# =========================================================

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
