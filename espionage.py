from glob import glob
from os.path import relpath
from random import choice as random_choice
from time import time
from typing import Dict, Optional, Set

from discord import Member, User, VoiceChannel, VoiceClient, VoiceState
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Command, Context

from settings import (
    ESPIONAGE_FILE,
    LOG_CSV,
    MIDI_IMPL,
    MIDI_IMPL_NONE,
    RANDOM_FILE,
    UPLOAD_PATH,
)
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
    random_queue: Dict[int, Set[str]]

    def __init__(self, bot: Bot, files: Dict[str, dict], sf2s: Dict[str, str]):
        self.bot = bot
        self.files = files
        self.sf2s = sf2s
        self.bot.event(self.on_voice_state_update)
        for name in files.keys():
            self.add_command(name)
        self.random_queue = {}
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
        # force playing the specified file
        await self.play(
            channel=ctx.voice_client.channel,
            member=ctx.message.author,
            cmd=cmd,
        )

    async def on_voice_state_update(
        self,
        member: Member,
        before: VoiceState,
        after: VoiceState,
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
                channel=member.voice.channel,
                member=member.user,
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
                channel=after.channel,
                member=member,
                cmd=None,
            )

    def safe_random(self, guild_id: int, items: list):
        if guild_id not in self.random_queue:
            queue = self.random_queue[guild_id] = set()
        else:
            queue = self.random_queue[guild_id]

        def key(item) -> str:
            if isinstance(item, dict):
                return item["filename"]
            return item

        # reset the queue if all choices were played
        if all(key(item) in queue for item in items):
            for item in items:
                queue.remove(key(item))

        # pick a random item that wasn't used before
        tries = 0
        while tries < len(items):
            item = random_choice(items)
            if key(item) not in queue:
                queue.add(key(item))
                return item
            tries += 1

    async def play(self, channel: VoiceChannel, member: Member, cmd: str):
        # connect to the specified voice channel
        await connect_to(channel)
        # repeat the file
        self.repeat(channel, member, cmd)

    def repeat(
        self,
        channel: VoiceChannel,
        member: Member,
        cmd: Optional[str],
        repeated: bool = False,
    ):
        # get the currently connected voice client
        voice: VoiceClient = channel.guild.voice_client

        # the bot is no longer connected
        if not voice:
            return
        guild_id = channel.guild.id

        # store cmd for usage in repeat(e)
        cmd_orig = cmd
        # to simplify the checks below
        random = cmd == RANDOM_FILE

        if random:
            # "random" specified as cmd, change to a random command dict
            cmd = self.safe_random(guild_id, list(self.files.values()))
        elif cmd and cmd != ESPIONAGE_FILE:
            # retrieve command info dict
            cmd = self.files[cmd]
        else:
            # cmd is ESPIONAGE_FILE or None (do not change playing file)
            pass

        # set the appropriate filename and loop mode
        if isinstance(cmd, dict):
            # filename is a basename
            filename = real_filename(cmd)
            pack = "pack" in cmd and cmd["pack"]
            if pack:
                filename = self.safe_random(guild_id, glob(f"{filename}/*"))
            loop = cmd["loop"] or random or pack
        else:
            # only for ESPIONAGE_FILE as cmd - already absolute or relative to cwd
            filename = cmd
            loop = True

        def leave(e):
            self.bot.loop.create_task(disconnect(voice))

        def repeat(e):
            self.repeat(channel, member, cmd=cmd_orig, repeated=True)

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
                # forcefully disable repeating of the previous player
                if voice._player:
                    voice._player.after = None
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

        if LOG_CSV:
            with open(LOG_CSV, "a+") as f:
                fields = [
                    str(int(time())),
                    str(guild_id),
                    channel.guild.name,
                    str(member.id),
                    f"{member.name}#{member.discriminator}",
                    cmd_orig or "None",
                    relpath(filename, UPLOAD_PATH),
                ]
                f.write(";".join(fields) + "\n")

        if midi:
            sf2s = cmd["sf2s"]
            sf2 = random_choice(sf2s) if sf2s else None
            sf2s = list(self.sf2s.values())
            if not sf2s or MIDI_IMPL == MIDI_IMPL_NONE:
                return
            sf2 = self.sf2s[sf2] if sf2 in self.sf2s else random_choice(sf2s)
            sf2_name = real_filename(sf2)
            print(f"Playing on {channel.guild}: '{filename}' with SF2 '{sf2_name}' ...")
            source = FFmpegMidiOpusAudio(filename, sf2_name, rate)
        else:
            print(f"Playing on {channel.guild}: '{filename}' ...")
            source = FFmpegFileOpusAudio(filename, rate)

        voice.play(source, after=loop and repeat or leave)
