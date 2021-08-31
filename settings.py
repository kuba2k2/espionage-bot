import os

from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

BOT_TOKEN = os.getenv("BOT_TOKEN")
ESPIONAGE_FILE = os.getenv("ESPIONAGE_FILE")
FILES_JSON = os.getenv("FILES_JSON")
SF2S_JSON = os.getenv("SF2S_JSON") or "soundfonts.json"
ACTIVITY_NAME = os.getenv("ACTIVITY_NAME")
UPLOAD_PATH = os.getenv("UPLOAD_PATH")

COG_ESPIONAGE = os.getenv("COG_ESPIONAGE") or "Music commands"
COG_MUSIC = os.getenv("COG_MUSIC") or "Other music commands"
COG_UPLOADING = os.getenv("COG_UPLOADING") or "File uploading/management"

RANDOM_FILE = "random"
