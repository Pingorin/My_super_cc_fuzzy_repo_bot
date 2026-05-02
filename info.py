import os
import re

# Helper for ID parsing
id_pattern = re.compile(r'^-?\d+$')

# --- MANDATORY VARIABLES ---
API_ID = int(os.environ.get("API_ID", "20638104")) 
API_HASH = os.environ.get("API_HASH", "6c884690ca85d39a4c5ad7c15b194e42")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8527539919:AAFFu37tTXtn7PQS0ioJj4lVlEVgQT3Cr5A")

# 🔥 NAYA FEATURE: Redirect Search Results to Another Bot (Bot B)
# Yahan Bot B (File Store Bot) ka username daalein bina '@' lagaye. E.g., "MyMovieFileBot"
FILE_STORE_BOT = os.environ.get("FILE_STORE_BOT", "")

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "9e1353ccc623e71f80262309cda5cdfb") # Default Test Key

# --- DATABASE SETTINGS ---
DATABASE_URI = os.environ.get("DATABASE_URI", "mongodb+srv://ronak99:ronak99@cluster0.xxbkgsd.mongodb.net/?retryWrites=true&w=majority&minPoolSize=1&maxPoolSize=20")

# 🔥 NEW: MULTI-DATABASE ARCHITECTURE SETTINGS 🔥
# Jab DB 1 full ho jaye, toh host (Render/Heroku) ke variables me inki link daal dena
DATABASE_URI_2 = os.environ.get("DATABASE_URI_2", "")
DATABASE_URI_3 = os.environ.get("DATABASE_URI_3", "")
INDEX_DB = int(os.environ.get("INDEX_DB", "1")) # Default DB 1 (Changeable via /setindex command)

DATABASE_NAME = os.environ.get("DATABASE_NAME", "Cluster0")
COLLECTION_NAME = os.environ.get('COLLECTION_NAME', 'Telegram_files')
USER_DB_URI = os.environ.get("USER_DB_URI", "mongodb+srv://Priya55:Priya55@cluster0.nmxnzme.mongodb.net/?retryWrites=true&w=majority&minPoolSize=1&maxPoolSize=20")
if not USER_DB_URI:
    USER_DB_URI = DATABASE_URI
  
# --- GENERAL SETTINGS ---
# 🔥 FIX: Ab Admin IDs bina environment variable ke bhi perfectly work karegi
ADMINS_STR = os.environ.get("ADMINS", "7245547751") # Yahan "" ke andar default admin IDs dal sakte hain space se separate karke (e.g., "123456789 987654321")
ADMINS = [int(i) for i in ADMINS_STR.split()] if ADMINS_STR else []

LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "-1003474604893")) 
PORT = int(os.environ.get("PORT", "8080"))
CHANNELS = [int(ch) for ch in os.environ.get("CHANNELS", "0").split()] if os.environ.get("CHANNELS") else []

# Yahan -1001234567890 ki jagah apna asli Channel ID daalein
TARGET_CHANNEL_ID = int(os.environ.get("TARGET_CHANNEL_ID", "0"))

# 👇 NAYA FEATURE: Streaming ke liye Bin Channel (Apne Database Channel ki ID daalein)
BIN_CHANNEL = int(os.environ.get("BIN_CHANNEL", "0"))

# 🌟 AUTO-POSTER SETTINGS 🌟
# Channel jahan TMDB se movie posters auto-post honge
updates_channel_env = os.environ.get("UPDATES_CHANNEL", "-1003911004326")
UPDATES_CHANNEL = int(updates_channel_env) if updates_channel_env and id_pattern.search(updates_channel_env) else None

# Agar Auto-poster dusre bot se chalwana hai, toh uska token yahan dalein. Main bot se chalwana ho toh khali chhod dein.
POSTER_BOT_TOKEN = os.environ.get("POSTER_BOT_TOKEN", "")

# ✅ SITE URL (REQUIRED FOR SITE MODE)
# Render/Heroku users must set this in Environment Variables (e.g., https://my-app.onrender.com)
# Do not add a trailing slash (/) at the end.
SITE_URL = os.environ.get("SITE_URL", "")

# --- VERIFICATION SETTINGS ---
IS_VERIFY = os.environ.get("IS_VERIFY", "True").lower() in ["true", "yes", "1"]
VERIFY_TIME = int(os.environ.get("VERIFY_TIME", 1200)) # 20 Min
VERIFY_GAP1 = int(os.environ.get("VERIFY_GAP1", 300))  # 5 Min
VERIFY_GAP2 = int(os.environ.get("VERIFY_GAP2", 300))  # 5 Min

# --- SHORTENER SETTINGS ---
SHORTLINK_URL_1 = os.environ.get("SHORTLINK_URL_1", "")
SHORTLINK_API_1 = os.environ.get("SHORTLINK_API_1", "")

SHORTLINK_URL_2 = os.environ.get("SHORTLINK_URL_2", "")
SHORTLINK_API_2 = os.environ.get("SHORTLINK_API_2", "")

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

# ==============================================================================
# 💳 PAYMENT & CONTACT SETTINGS (NEW)
# ==============================================================================
# Apna UPI ID yahan dalein
MERCHANT_UPI_ID = os.environ.get("MERCHANT_UPI_ID", "") 

# Group/Channel link jahan user screenshot bhejega
PAYMENT_SUPPORT_LINK = os.environ.get("PAYMENT_SUPPORT_LINK", "") 

# Owner se custom plan baat karne ka link
CONTACT_OWNER_LINK = os.environ.get("CONTACT_OWNER_LINK", "") 

# Agar aapko custom QR code photo lagani hai (URL), warna bot auto generate karega
CUSTOM_QR_URL = os.environ.get("CUSTOM_QR_URL", "")
