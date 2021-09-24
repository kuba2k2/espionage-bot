from os import makedirs, replace, sep
from os.path import basename, dirname, isdir, isfile, join

from discord import Activity, ActivityType
from discord.ext import commands
from discord.ext.commands import Bot

from espionage import Espionage
from music import Music
from settings import ACTIVITY_NAME, BOT_TOKEN, DATA_PATH, UPLOAD_DIR, UPLOAD_PATH
from uploading import Uploading
from utils import load_files, load_sf2s

client = Bot(command_prefix=commands.when_mentioned_or("!"))


@client.event
async def on_ready():
    print("We have logged in as {0.user}".format(client))
    await client.change_presence(
        activity=Activity(
            type=ActivityType.listening,
            name=ACTIVITY_NAME,
        )
    )


def migrate(file: dict):
    version = file["version"] if "version" in file else 1
    if version < 2:
        # add missing author info
        if "author" not in file:
            file["author"] = {
                "id": 0,
                "guild": 0,
            }

        # naive data directory migration
        if file["filename"].startswith(UPLOAD_DIR):
            new_path = join(DATA_PATH, file["filename"])
            if isfile(file["filename"]) or isdir(file["filename"]):
                makedirs(dirname(new_path), exist_ok=True)
                replace(file["filename"], new_path)
            file["filename"] = new_path.replace("/", sep)

        # change filenames to the last path component
        # so that it's relative to UPLOAD_DIR
        file["filename"] = basename(file["filename"])
        file["version"] = 2


def main():
    files = load_files()
    sf2s = load_sf2s()

    for file in files.values():
        migrate(file)
    for sf2 in sf2s.values():
        migrate(sf2)

    client.add_cog(Espionage(bot=client, files=files, sf2s=sf2s))
    client.add_cog(Music(bot=client, files=files, sf2s=sf2s))
    client.add_cog(Uploading(bot=client, files=files, sf2s=sf2s))
    client.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
