"""
config.py - রুট ডিরেক্টরি থেকে কাজ করে
সব সিক্রেট/সেটিং এখান থেকে লোড হয় .env ফাইল থেকে।
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env ফাইল লোড করুন (বর্তমান ডিরেক্টরি থেকে)
load_dotenv()

# ---- Telegram Bot ----
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN পাওয়া যায়নি। .env ফাইলে BOT_TOKEN যোগ করো।")

# ---- Google Sheets ----
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
if not GOOGLE_SHEET_ID:
    raise RuntimeError("GOOGLE_SHEET_ID পাওয়া যায়নি।")

# credentials.json ফাইলের পাথ (বর্তমান ডিরেক্টরিতে)
GOOGLE_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_CREDENTIALS_PATH", 
    "credentials.json"
)

if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
    raise RuntimeError(
        "credentials.json পাওয়া যায়নি: " + GOOGLE_CREDENTIALS_PATH
    )

# ---- বাংলাদেশ সময় ----
def bd_now():
    from datetime import datetime, timezone, timedelta
    return datetime.now(timezone(timedelta(hours=6)))
