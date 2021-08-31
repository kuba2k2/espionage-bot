from discord import Activity, ActivityType
from discord.ext import commands
from discord.ext.commands import Bot

from espionage import Espionage
from music import Music
from settings import ACTIVITY_NAME, BOT_TOKEN, UPLOAD_PATH
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


def main():
    files = load_files()
    sf2s = load_sf2s()
    for name in files:
        if "author" not in files[name]:
            files[name]["author"] = {
                "id": 0,
                "guild": 0,
            }
    client.add_cog(Espionage(bot=client, files=files, sf2s=sf2s))
    client.add_cog(Music(bot=client, files=files, sf2s=sf2s))
    client.add_cog(Uploading(bot=client, files=files, sf2s=sf2s, path=UPLOAD_PATH))
    client.run(BOT_TOKEN)


if __name__ == "__main__":
    main()
