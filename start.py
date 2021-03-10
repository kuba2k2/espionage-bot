import json
from os import unlink
from os.path import isfile
from time import time
from typing import Dict

from discord import (
    Activity,
    ActivityType,
    Guild,
    User,
    Member,
    VoiceChannel,
    VoiceClient,
    VoiceState,
    FFmpegOpusAudio,
    Message,
    Attachment,
)
from discord.ext import commands
from discord.ext.commands import Cog, Context, Bot, CommandError, Command

from settings import BOT_TOKEN, ESPIONAGE_FILE, FILES_JSON, ACTIVITY_NAME, UPLOAD_PATH

client = Bot(command_prefix=commands.when_mentioned_or("!"))


class FFmpegFileOpusAudio(FFmpegOpusAudio):
    def __init__(self, filename: str, *args, **kwargs):
        self.filename = filename
        super().__init__(filename, *args, **kwargs)


async def connect_to(channel: VoiceChannel) -> VoiceClient:
    guild: Guild = channel.guild
    voice: VoiceClient = guild.voice_client
    if voice is None or not voice.is_connected():
        voice = await channel.connect()
    elif voice.channel != channel:
        await voice.move_to(channel)
    elif voice.is_playing():
        voice.pause()
    return voice


def is_alone(voice: VoiceClient):
    if not voice:
        return False
    return len(voice.channel.voice_states) <= 1


async def disconnect(voice: VoiceClient):
    await voice.disconnect()


async def ensure_voice(_, ctx: Context):
    member: Member = ctx.args[2] or ctx.author
    if not member.voice:
        await ctx.send(f"User is not connected to a voice channel.", delete_after=3)
        raise CommandError(f"{ctx.author} not connected to a voice channel.")
    await connect_to(member.voice.channel)


class Espionage(Cog, name="Music commands"):
    def __init__(self, bot: Bot, files: Dict[str, dict]):
        self.bot = bot
        self.files = files
        self.bot.event(self.on_voice_state_update)
        for name in files.keys():
            self.add_command(name)

    def add_command(self, name: str):
        if self.bot.get_command(name):
            return
        cmd = self.files[name]
        command: Command = self.bot.command(
            name=name,
            brief=cmd["help"]
            or (
                f"Loop {cmd['filename']}" if cmd["loop"] else f"Play {cmd['filename']}"
            ),
        )(self.play_command)
        command.before_invoke(ensure_voice)
        command.cog = self

    def remove_command(self, name: str):
        if not self.bot.get_command(name):
            return
        self.bot.remove_command(name)

    @commands.guild_only()
    async def play_command(self, _, ctx: Context, __: User = None):
        cmd = ctx.command.name
        cmd = self.files[cmd]
        # force playing the specified file
        await self.play(
            ctx.voice_client.channel,
            file=cmd["filename"],
            loop=cmd["loop"],
        )

    async def on_voice_state_update(
        self, member: Member, before: VoiceState, after: VoiceState
    ):
        if member.id == self.bot.user.id:
            # the bot was moved to (or joined) the AFK channel
            if after.mute or after.afk:
                await member.edit(mute=False)
            return

        # the bot is the only connected user
        if is_alone(member.guild.voice_client):
            await disconnect(member.guild.voice_client)

        # the channel is unchanged
        if before.channel == after.channel:
            return

        # a user left a voice channel
        if not after.channel:
            return

        # a user joined the AFK channel
        if (not before.afk or not before.channel) and after.afk:
            # play the default file or leave the currently playing file
            await self.play(
                member.voice.channel,
                file=ESPIONAGE_FILE if not member.guild.voice_client else None,
                loop=True,
            )
            return

        # a user joined the channel when the bot was alone
        # for some reason this fixes silence when moving the bot
        # to an empty channel
        if (
            member.guild.voice_client
            and member.guild.voice_client.channel == after.channel
            and len(after.channel.voice_states) == 2
        ):
            await self.play(
                after.channel,
                file=None,
                loop=True,
            )

    async def play(self, channel: VoiceChannel, file: str, loop: bool):
        # connect to the specified voice channel
        await connect_to(channel)
        # repeat the file
        self.repeat(channel, file, loop)

    def repeat(
        self,
        channel: VoiceChannel,
        file: str = None,
        loop: bool = True,
        repeated: bool = False,
    ):
        # get the currently connected voice client
        voice: VoiceClient = channel.guild.voice_client

        # the bot is no longer connected
        if not voice:
            return

        # the current source differs from the desired source
        if voice.source and file and voice.source.filename != file:
            # when changing the playing file avoid repeating the previous one
            if repeated:
                return
            if voice.is_playing() or voice.is_paused():
                voice.stop()
        # return if already playing
        if voice.is_playing():
            return
        # resume if audio paused
        if voice.is_paused():
            voice.resume()
            return

        # file not specified - not to change the already playing file
        if not file:
            return
        source = FFmpegFileOpusAudio(file)
        voice.play(
            source,
            after=lambda e: not loop
            or self.repeat(channel, file=file, loop=loop, repeated=True),
        )


class Uploading(Cog, name="File uploading/management"):
    def __init__(self, bot: Bot, path: str):
        self.bot = bot
        self.path = path

    @commands.command()
    @commands.guild_only()
    async def upload(self, ctx: Context, name: str = None):
        """Upload the attached file as a command."""
        message: Message = ctx.message
        if not name:
            await ctx.send(
                "Usage: `!upload <command name>`. Attach one audio file.",
                delete_after=3,
            )
            return
        if len(message.attachments) != 1:
            await ctx.send("You must add exactly one attachment.", delete_after=3)
            return
        attachment: Attachment = message.attachments[0]

        cog: Espionage = self.bot.get_cog("Music commands")
        if not cog:
            return
        files = cog.files

        replaced = False
        # delete the already existing file
        if self.bot.get_command(name):
            replaced = True
            unlink(files[name]["filename"])

        # create a safe filename
        filename = f"{self.path}/{int(time())}_{attachment.filename}"

        # save the attachment
        with open(filename, "wb") as f:
            await attachment.save(f)

        # replace the command descriptor
        files[name] = {
            "filename": filename,
            "help": f"Uploaded by {ctx.author}",
            "loop": True,
        }

        # add the command to the music cog
        cog.add_command(name)
        # save the command descriptors
        with open(FILES_JSON, "w") as f:
            json.dump(files, f, indent=4)

        await ctx.send(
            f"File **{attachment.filename}** uploaded as `!{name}`."
            if not replaced
            else f"Replaced `!{name}` with **{attachment.filename}**.",
            delete_after=10,
        )

    @commands.command()
    @commands.guild_only()
    async def eloop(self, ctx: Context, name: str = None):
        """Enable looping of the specified audio."""
        if not name:
            await ctx.send("Usage: `!enoloop <command name>`.", delete_after=3)
            return
        if not self.set_loop(name, True):
            await ctx.send(f"The command `!{name}` does not exist.", delete_after=3)
            return
        await ctx.send(f"Looping enabled for `!{name}`.", delete_after=3)

    @commands.command()
    @commands.guild_only()
    async def enoloop(self, ctx: Context, name: str = None):
        """Disable looping of the specified audio."""
        if not name:
            await ctx.send("Usage: `!enoloop <command name>`.", delete_after=3)
            return
        if not self.set_loop(name, False):
            await ctx.send(f"The command `!{name}` does not exist.", delete_after=3)
            return
        await ctx.send(f"Looping disabled for `!{name}`.", delete_after=3)

    def set_loop(self, name: str, loop: bool) -> bool:
        cog: Espionage = self.bot.get_cog("Music commands")
        if not cog:
            return
        files = cog.files

        if name not in files:
            return False

        if files[name]["loop"] != loop:
            files[name]["loop"] = loop
            # remove the command to update help text
            cog.remove_command(name)
            cog.add_command(name)
            # save the command descriptors
            with open(FILES_JSON, "w") as f:
                json.dump(files, f, indent=4)
        return True

    @commands.command()
    @commands.guild_only()
    async def aremove(self, ctx: Context, name: str = None):
        """Remove the specified audio."""
        if not name:
            await ctx.send("Usage: `!aremove <command name>`.", delete_after=3)
            return
        cog: Espionage = self.bot.get_cog("Music commands")
        if not cog:
            return
        files = cog.files
        if name not in files:
            await ctx.send(f"The command `!{name}` does not exist.", delete_after=3)
            return
        cog.remove_command(name)
        cmd = files.pop(name, None)
        if cmd and isfile(cmd["filename"]):
            unlink(cmd["filename"])
        await ctx.send(f"Command `!{name}` removed.", delete_after=3)

    @commands.command()
    @commands.guild_only()
    async def description(self, ctx: Context, name: str = None, *args):
        """Change the description."""
        description = " ".join(args)
        if not name or not description:
            await ctx.send(
                "Usage: `!description <command name> <description>`.", delete_after=3
            )
            return
        cog: Espionage = self.bot.get_cog("Music commands")
        if not cog:
            return
        files = cog.files
        if name not in files:
            await ctx.send(f"The command `!{name}` does not exist.", delete_after=3)
            return
        files[name]["help"] = description
        # remove the command to update help text
        cog.remove_command(name)
        cog.add_command(name)
        # save the command descriptors
        with open(FILES_JSON, "w") as f:
            json.dump(files, f, indent=4)
        await ctx.send(
            f"Description of `!{name}` set to `{description}`.", delete_after=3
        )


@client.event
async def on_ready():
    print("We have logged in as {0.user}".format(client))
    await client.change_presence(
        activity=Activity(
            type=ActivityType.listening,
            name=ACTIVITY_NAME,
        )
    )


if __name__ == "__main__":
    with open(FILES_JSON, "r") as jf:
        files_json = json.load(jf)
    client.add_cog(Espionage(bot=client, files=files_json))
    client.add_cog(Uploading(bot=client, path=UPLOAD_PATH))
    client.run(BOT_TOKEN)
