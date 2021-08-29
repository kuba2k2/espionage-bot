from random import choice as random_choice
from typing import Dict

from discord import Member, User, VoiceChannel, VoiceClient, VoiceState
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Command, Context

from settings import ESPIONAGE_FILE, RANDOM_FILE
from utils import (
    FFmpegFileOpusAudio,
    FFmpegMidiOpusAudio,
    connect_to,
    disconnect,
    ensure_voice,
    is_alone,
)


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
        file: str,
        loop: bool,
        repeated: bool = False,
    ):
        # get the currently connected voice client
        voice: VoiceClient = channel.guild.voice_client

        # the bot is no longer connected
        if not voice:
            return

        # the current source differs from the desired source
        if voice.source and file and voice.source.filename != file:
            # avoid going back to the previous file again when repeat() is called
            # from after= in voice.play()
            if repeated and voice.is_playing():
                return
            if voice.is_playing() or voice.is_paused():
                print(f"Stopping file={file}")
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

        random = file == RANDOM_FILE
        filename = file
        if random:
            cmd = random_choice(list(self.files.values()))
            filename = cmd["filename"]

        def leave(e):
            print(f"Leave file={file}, loop={loop}, e={e}")

        def repeat(e):
            print(f"Repeat file={file}, loop={loop}, e={e}")
            self.repeat(channel, file=file, loop=loop, repeated=True)

        if filename[-4:] == ".mid":
            source = FFmpegMidiOpusAudio(filename, "soundfont.sf2")
        else:
            source = FFmpegFileOpusAudio(filename)
        voice.play(source, after=loop and repeat or leave)
