import os

from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ESPIONAGE_FILE = os.getenv("ESPIONAGE_FILE")
COMMANDS = os.getenv("COMMANDS").split(" ")
FILES = os.getenv("FILES").split(" ")
