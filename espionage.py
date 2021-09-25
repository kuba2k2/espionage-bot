from glob import glob
from random import choice as random_choice
from typing import Dict, Union

from discord import Member, User, VoiceChannel, VoiceClient, VoiceState
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Command, Context

from settings import ESPIONAGE_FILE, MIDI_IMPL, MIDI_IMPL_NONE, RANDOM_FILE
from utils import (
    FFmpegFileOpusAudio,
    FFmpegMidiOpusAudio,
    connect_to,
    disconnect,
    ensure_voice,
    is_alone,
    real_filename,
)


class Espionage(Cog, name="Music commands"):
    def __init__(self, bot: Bot, files: Dict[str, dict], sf2s: Dict[str, str]):
        self.bot = bot
        self.files = files
        self.sf2s = sf2s
        self.bot.event(self.on_voice_state_update)
        for name in files.keys():
            self.add_command(name)
        print(f"Loaded {len(files)} audio commands.")

    def add_command(self, name: str):
        if self.bot.get_command(name):
            return
        cmd = self.files[name]
        description = cmd["help"]
        if "pack" in cmd and cmd["pack"]:
            description = f"\ud83d\udcc1 {description}"
        if not description:
            description = (
                f"Loop {cmd['filename']}" if cmd["loop"] else f"Play {cmd['filename']}"
            )
        command: Command = self.bot.command(
            name=name,
            brief=description,
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
            cmd=cmd,
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
                cmd=ESPIONAGE_FILE if not member.guild.voice_client else None,
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
                cmd=None,
            )

    async def play(self, channel: VoiceChannel, cmd: Union[str, dict]):
        # connect to the specified voice channel
        await connect_to(channel)
        # repeat the file
        self.repeat(channel, cmd)

    def repeat(
        self,
        channel: VoiceChannel,
        cmd: Union[str, dict],
        repeated: bool = False,
    ):
        # get the currently connected voice client
        voice: VoiceClient = channel.guild.voice_client

        # the bot is no longer connected
        if not voice:
            return

        # store cmd for usage in repeat(e)
        cmd_orig = cmd
        # to simplify the checks below
        random = cmd == RANDOM_FILE
        # "random" specified as cmd, change to a random command dict
        if random:
            cmd = random_choice(list(self.files.values()))

        # set the appropriate filename and loop mode
        if isinstance(cmd, dict):
            # filename is a basename
            filename = real_filename(cmd)
            pack = "pack" in cmd and cmd["pack"]
            if pack:
                filename = random_choice(glob(f"{filename}/*"))
            loop = cmd["loop"] or random or pack
        else:
            # only for ESPIONAGE_FILE as cmd - already absolute or relative to cwd
            filename = cmd
            loop = True

        def leave(e):
            self.bot.loop.create_task(disconnect(voice))

        def repeat(e):
            self.repeat(channel, cmd=cmd_orig, repeated=True)

        # fix for disabling !loop while playing
        if repeated and not loop:
            leave(None)
            return

        # the current source differs from the desired source
        if voice.source and cmd and (voice.source.filename != filename or random):
            # avoid going back to the previous file again when repeat() is called
            # from after= in voice.play()
            if repeated and voice.is_playing():
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
        # this line is not above probably to voice.resume() if paused
        if not cmd:
            return

        midi = "midi" in cmd and cmd["midi"]

        rate = None
        speed = cmd["speed"] if "speed" in cmd else 100
        if speed != 100 and "info" in cmd:
            rate = cmd["info"]["sample_rate"]
            rate = rate * speed / 100
            rate = int(rate)
        elif speed != 100 and midi:
            rate = 44100 * speed / 100
            rate = int(rate)

        if midi:
            sf2s = cmd["sf2s"]
            sf2 = random_choice(sf2s) if sf2s else None
            sf2s = list(self.sf2s.values())
            if not sf2s or MIDI_IMPL == MIDI_IMPL_NONE:
                return
            sf2 = self.sf2s[sf2] if sf2 in self.sf2s else random_choice(sf2s)
            sf2_name = real_filename(sf2)
            print(f"Playing '{filename}' with SF2 '{sf2_name}' ...")
            source = FFmpegMidiOpusAudio(filename, sf2_name, rate)
        else:
            print(f"Playing '{filename}' ...")
            source = FFmpegFileOpusAudio(filename, rate)
        voice.play(source, after=loop and repeat or leave)
