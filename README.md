# espionage-bot

A Discord bot that plays the Nokia Espionage ringtone for any user entering the AFK channel.

The bot can also be summoned manually using commands in `files.json`.

## Usage

Copy `.env.example` and configure it.
```shell
BOT_TOKEN       #* your Discord bot token
DATA_PATH       #* global data directory path (absolute or relative)
UPLOAD_DIR      #  uploads directory name (inside the DATA_PATH, relative)
ESPIONAGE_FILE  #  default AFK audio file name (inside the DATA_PATH, relative)
FILES_JSON      #  files storage JSON (inside the DATA_PATH, relative)
SF2S_JSON       #  soundfonts storage JSON (inside the DATA_PATH, relative)
ACTIVITY_NAME   #  Discord activity name "Listening ....."
```

When migrating from previous versions put the old `FILES_JSON` and configured `ESPIONAGE_FILE`
in `DATA_PATH` to have all audio files moved automatically.

Create `files.json` and put additional file commands there.

Install the project with `pipenv install`. Run `start.py` inside the virtual environment.

The bot should at least have the `Connect`, `Speak`, `Mute Members` and `Move Members` permissions.

To use the MIDI support you should upload at least one SoundFont (.sf2) prior to playing, else weird things may happen.

Refer to the discord-py installation guide for other dependencies, e.g. on Linux.
```shell
apt install libffi-dev libnacl-dev python3-dev
apt install ffmpeg
apt install libmagic1
# For MIDI file support
apt install fluidsynth
```
