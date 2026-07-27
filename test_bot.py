#!/usr/bin/env python3
"""Simple test script to verify bot imports"""
import sys
import os
import importlib
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ python-dotenv loaded")

    import telegram
    print("✅ python-telegram-bot loaded")

    config = importlib.import_module("03_Bot.config")
    print("✅ Bot config loaded")

    print("\n✅ All imports successful! The bot is ready to run.")
    print("\n📝 To start the bot, run:")
    print("   ./run_bot.sh")

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
