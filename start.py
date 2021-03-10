import json
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
)
from discord.ext import commands
from discord.ext.commands import Cog, Context, Bot, CommandError

from settings import BOT_TOKEN, ESPIONAGE_FILE, FILES_JSON, ACTIVITY_NAME

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
    def __init__(self, bot: Bot, files: Dict[str, str]):
        self.bot = bot
        self.files = files
        self.bot.event(self.on_voice_state_update)
        for name in files.keys():
            cmd = self.files[name]
            command = self.bot.command(
                name=name,
                brief=cmd["help"] or f"Play {cmd['filename']}",
            )(self.play_command)
            command.before_invoke(ensure_voice)
            command.cog = self

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
            else:
                return
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
    with open(FILES_JSON, "r") as f:
        files_json = json.load(f)
    client.add_cog(Espionage(bot=client, files=files_json))
    client.run(BOT_TOKEN)
