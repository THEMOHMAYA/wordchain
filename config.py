"""
Configuration settings for Wordchain Telegram Bot.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Turn timer in seconds (20 seconds)
TURN_TIMEOUT_SECONDS = int(os.getenv("TURN_TIMEOUT_SECONDS", "20"))

# Max attempts per turn / max wrong words (3 attempts)
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))
MAX_STRIKES = MAX_ATTEMPTS

# Lobby duration in seconds (2 minutes / 120s)
LOBBY_DURATION_SECONDS = int(os.getenv("LOBBY_DURATION_SECONDS", "120"))

# Player constraints (MIN_PLAYERS = 1 allows solo practice & easy testing!)
MIN_PLAYERS = int(os.getenv("MIN_PLAYERS", "1"))
MAX_PLAYERS = int(os.getenv("MAX_PLAYERS", "20"))
