# espionage-bot

A Discord bot that plays the Nokia Espionage ringtone for any user entering the AFK channel.

The bot can also be summoned manually using commands in `files.json`.

## Usage

Create `.env` and set your bot token and MP3 file path there.

Create `files.json` and put additional file commands there.

Install the project with `pipenv install`. Run `start.py` inside the virtual environment.

The bot should at least have the `Connect`, `Speak`, `Mute Members` and `Move Members` permissions.

Refer to the discord-py installation guide for other dependencies, e.g. on Linux.
```shell
apt install libffi-dev libnacl-dev python3-dev
apt install ffmpeg
```
