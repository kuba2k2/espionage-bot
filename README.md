# espionage-bot

A Discord bot that plays the Nokia Espionage ringtone for any user entering the AFK channel.

The bot can also be summoned manually using commands in `files.json`.

## Usage

### With Docker Compose
```shell
$ mkdir -p ~/docker/espionage-bot
$ cd ~/docker/espionage-bot
$ mkdir ./data/
$ wget https://raw.githubusercontent.com/kuba2k2/espionage-bot/master/docker-compose.yml
$ vim docker-compose.yml
```
Edit the file adding your Discord bot token to `BOT_TOKEN=`.

Place the `espionage.mp3` file in `~/docker/espionage-bot/data` (or edit the Compose environment variables accordingly).

Run `espionage-bot`:
```shell
$ docker-compose up --detach
```

### With Docker
```shell
$ git clone https://github.com/kuba2k2/espionage-bot
$ cd espionage-bot
$ mkdir ./data/
$ cp .env.example .env
$ vim .env
```
Edit the file adding your Discord bot token to `BOT_TOKEN=`.

Place the `espionage.mp3` file in the `data/` directory.

Build and run the image:
```shell
$ docker build --tag espionage-bot .
$ docker run -d -v $(pwd)/data:/app/data --env-file .env espionage-bot
```

### With Python (pipenv)
```shell
$ git clone https://github.com/kuba2k2/espionage-bot
$ cd espionage-bot
$ mkdir ./data/
$ cp .env.example .env
$ vim .env
```
Edit the file adding your Discord bot token to `BOT_TOKEN=`.

Place the `espionage.mp3` file in the `data/` directory.

Refer to the discord-py installation guide for other dependencies, e.g. on Linux:
```shell
$ apt install libffi-dev libnacl-dev python3-dev
$ apt install ffmpeg
$ apt install libmagic1
# For MIDI file support
$ apt install fluidsynth
```

Install and run the project:
```shell
$ pipenv install
$ pipenv run python start.py
```

## Notes
When migrating from previous versions put the old `FILES_JSON` and configured `ESPIONAGE_FILE`
in `DATA_PATH` to have all audio files moved automatically.

The bot should at least have the `Connect`, `Speak`, `Mute Members` and `Move Members` permissions.

To use the MIDI support you should upload at least one SoundFont (.sf2) prior to playing, else weird things may happen.
