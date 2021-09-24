from os import altsep, getenv, makedirs, sep
from os.path import isabs, isdir, isfile, join

from dotenv import load_dotenv

load_dotenv(encoding="utf-8")


def die(s: str):
    raise SystemExit(s)


CMD_VERSION = 2

BOT_TOKEN = getenv("BOT_TOKEN") or die("Bot token not provided")
DATA_PATH = getenv("DATA_PATH") or die("Data path not specified")
UPLOAD_DIR = getenv("UPLOAD_DIR") or "uploads"
ESPIONAGE_FILE = getenv("ESPIONAGE_FILE") or die("Espionage file not specified")
FILES_JSON = getenv("FILES_JSON") or "files.json"
SF2S_JSON = getenv("SF2S_JSON") or "soundfonts.json"

ACTIVITY_NAME = getenv("ACTIVITY_NAME") or "Espionage"

COG_ESPIONAGE = getenv("COG_ESPIONAGE") or "Music commands"
COG_MUSIC = getenv("COG_MUSIC") or "Other music commands"
COG_UPLOADING = getenv("COG_UPLOADING") or "File uploading/management"

RANDOM_FILE = "random"

# ensure existing data path with a trailing slash
isdir(DATA_PATH) or makedirs(DATA_PATH, exist_ok=True)
DATA_PATH = DATA_PATH.rstrip(sep + (altsep or ""))
DATA_PATH = join(DATA_PATH, "")

# ensure existing uploads path with a trailing slash
UPLOAD_DIR = UPLOAD_DIR.strip(sep + (altsep or ""))
UPLOAD_PATH = join(DATA_PATH, UPLOAD_DIR, "")
isdir(UPLOAD_PATH) or makedirs(UPLOAD_PATH, exist_ok=True)

FILES_JSON = DATA_PATH + FILES_JSON
SF2S_JSON = DATA_PATH + SF2S_JSON

# join espionage file with data path if relative
if not isabs(ESPIONAGE_FILE):
    ESPIONAGE_FILE = DATA_PATH + ESPIONAGE_FILE

isfile(ESPIONAGE_FILE) or die("Espionage file does not exist")

print(f"Using data path: '{DATA_PATH}'")
print(f"Using upload path: '{UPLOAD_PATH}'")
