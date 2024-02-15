from os import altsep, getenv, makedirs, sep
from os.path import isabs, isdir, isfile, join

from dotenv import load_dotenv

load_dotenv(encoding="utf-8")


def die(s: str):
    raise SystemExit(s)


CMD_VERSION = 3

RANDOM_FILE = "random"
MIDI_IMPL_NONE = "nomidi"
MIDI_IMPL_FLUIDSYNTH = "fluidsynth"
MIDI_IMPL_TIMIDITY = "timidity"
PACK_ICON = b"\xf0\x9f\x93\x81".decode()

BOT_TOKEN = getenv("BOT_TOKEN") or die("Bot token not provided")
DATA_PATH = getenv("DATA_PATH") or "data/"
UPLOAD_DIR = getenv("UPLOAD_DIR") or "uploads"
ESPIONAGE_FILE = getenv("ESPIONAGE_FILE") or die("Espionage file not specified")
FILES_JSON = getenv("FILES_JSON") or "files.json"
SF2S_JSON = getenv("SF2S_JSON") or "soundfonts.json"
LOG_CSV = getenv("LOG_CSV") or "log.csv"
NICKNAME_STATUS = getenv("NICKNAME_STATUS") == "true"

ACTIVITY_NAME = getenv("ACTIVITY_NAME") or "Espionage"

COG_ESPIONAGE = getenv("COG_ESPIONAGE") or "Music commands"
COG_MUSIC = getenv("COG_MUSIC") or "Playback options"
COG_UPLOADING = getenv("COG_UPLOADING") or "Music Uploading"

MIDI_IMPL = getenv("MIDI_IMPL") or MIDI_IMPL_NONE
MIDI_MUTE_124 = getenv("MIDI_MUTE_124") == "true"
MIDI_MUTE_124_FILE = getenv("MIDI_MUTE_124_FILE") or "mute124.sf2"

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
LOG_CSV = DATA_PATH + LOG_CSV

# join espionage file with data path if relative
if not isabs(ESPIONAGE_FILE):
    ESPIONAGE_FILE = DATA_PATH + ESPIONAGE_FILE

isfile(ESPIONAGE_FILE) or die("Espionage file does not exist")
MIDI_IMPL in [MIDI_IMPL_NONE, MIDI_IMPL_FLUIDSYNTH, MIDI_IMPL_TIMIDITY] or die(
    "Invalid MIDI_IMPL"
)
MIDI_MUTE_124 and (isfile(MIDI_MUTE_124_FILE) or die("mute124.sf2 file not found!"))

print(f"Using data path: '{DATA_PATH}'")
print(f"Using upload path: '{UPLOAD_PATH}'")
