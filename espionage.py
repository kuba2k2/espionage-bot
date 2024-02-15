from glob import glob
from os.path import isfile, relpath
from random import choice as random_choice
from time import time
from typing import Dict, Optional, Set, Tuple

from discord import Guild, Member, User, VoiceChannel, VoiceClient, VoiceState
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Command, Context

from settings import (
    ESPIONAGE_FILE,
    LOG_CSV,
    MIDI_IMPL,
    MIDI_IMPL_NONE,
    PACK_ICON,
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
    random_queue: Dict[int, Set[str]]  # {guild_id: {...filename}}
    # {guild_id: (channel, member, cmd, timestamp, speed)}
    replay_info: Dict[int, Tuple[VoiceChannel, Member, Optional[str], float, int]]

    def __init__(self, bot: Bot, files: Dict[str, dict], sf2s: Dict[str, str]):
        self.bot = bot
        self.files = files
        self.sf2s = sf2s
        self.bot.event(self.on_voice_state_update)
        for name in files.keys():
            self.add_command(name)
        self.random_queue = {}
        self.replay_info = {}
        print(f"Loaded {len(files)} audio commands.")

    def add_command(self, name: str):
        if self.bot.get_command(name):
            return
        cmd = self.files[name]
        description = cmd["help"]
        if "pack" in cmd and cmd["pack"]:
            description = f"{PACK_ICON} {description}"
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
            if after.mute or after.afk:
                # the bot was moved to (or joined) the AFK channel
                await member.edit(mute=False)
            if not after.channel:
                # the bot has been disconnected from a channel
                await self.update_nickname(member.guild, None)
            return

        # the bot is the only connected user
        if is_alone(member.guild.voice_client):
            await disconnect(member.guild.voice_client)
            await self.update_nickname(member.guild, None)

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
                member=member,
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

    @staticmethod
    async def update_nickname(guild: Guild, name: str):
        me = guild.me
        current_nick = me.nick or me.name
        base_name = (
            current_nick.partition("|")[2].strip()
            if "|" in current_nick
            else current_nick
        )
        new_nick = base_name
        if name:
            suffix = f" | {base_name}"
            max_len = 32 - len(suffix)
            if max_len > 0:
                if len(name) > max_len:
                    name = name[0 : max_len - 3] + "..."
                new_nick = name[0:max_len] + suffix
        if current_nick == new_nick:
            return
        print(f"Updating nickname on '{guild.name}': '{current_nick}' -> '{new_nick}'")
        await me.edit(nick=new_nick)

    def safe_random(self, guild_id: int, items: list):
        if guild_id not in self.random_queue:
            queue = self.random_queue[guild_id] = set()
        else:
            queue = self.random_queue[guild_id]

        def key(item) -> str:
            if isinstance(item, dict):
                return item["filename"]
            if isinstance(item, tuple):
                return item[1]["filename"]
            return item

        # reset the queue if all choices were played
        if all(key(item) in queue for item in items):
            for item in items:
                queue.remove(key(item))

        # failsafe
        random_item = random_choice(items)
        # pick a random item that wasn't used before
        while len(items) > 0:
            item = random_choice(items)
            items.remove(item)
            if key(item) not in queue:
                queue.add(key(item))
                return item
        # failsafe
        return random_item

    async def play(self, channel: VoiceChannel, member: Member, cmd: str):
        # connect to the specified voice channel
        await connect_to(channel)
        # repeat the file
        self.repeat(channel, member, cmd)

    def reload(self, guild: Guild, rewind: bool = True):
        if guild.id in self.replay_info:
            # restart the currently playing file
            channel, member, cmd, timestamp, speed = self.replay_info.pop(guild.id)
            if rewind:
                start = 0.0
            else:
                # 'timestamp' is calculated starting timestamp at previous rate
                # 'start' is new starting offset in the file at normal rate
                rate = 100.0 / speed
                played = time() - timestamp
                start = played / rate
                print(
                    f"Reloading playback on '{guild.name}' - "
                    f"was playing for {played:.02f} s "
                    f"at {speed}%, now starting at {start:.02f} s"
                )
            self.repeat(channel, member, cmd, repeated=False, start=start)

    def repeat(
        self,
        channel: VoiceChannel,
        member: Member,
        cmd: Optional[str],
        repeated: bool = False,
        start: float = 0.0,
    ):
        # get the currently connected voice client
        voice: VoiceClient = channel.guild.voice_client

        # the bot is no longer connected
        if not voice:
            return
        guild_id = channel.guild.id

        # store cmd for usage in repeat(e)
        cmd_orig = cmd
        # for showing playing status (default to ESPIONAGE_FILE - no status)
        cmd_name = None
        # to simplify the checks below
        random = cmd == RANDOM_FILE
        # default value
        pack = False

        if random:
            # "random" specified as cmd, change to a random command dict
            cmd_name, cmd = self.safe_random(guild_id, list(self.files.items()))
        elif cmd and cmd != ESPIONAGE_FILE:
            # retrieve command info dict
            cmd_name = cmd
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
            self.bot.loop.create_task(self.update_nickname(voice.guild, None))
            self.replay_info.pop(voice.guild.id, None)

        def repeat(e):
            self.repeat(channel, member, cmd=cmd_orig, repeated=True)

        if not isfile(filename):
            print("FILE DOES NOT EXIST", filename)
            leave(None)
            return

        # fix for disabling !loop while playing
        if repeated and not loop:
            leave(None)
            return

        # the current source differs from the desired source:
        # if voice.source and cmd and (voice.source.filename != filename or random):

        # something is currently playing, just restart it:
        if voice.source and cmd:
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

        # file not specified - not changing the already playing file
        # this line is here to call voice.resume() if paused
        if not cmd:
            return

        midi = "midi" in cmd and cmd["midi"]

        rate = None
        speed: int
        speed = cmd["speed"] if "speed" in cmd else 100
        if speed != 100 and "info" in cmd:
            rate = cmd["info"]["sample_rate"]
            rate = rate * speed / 100
            rate = int(rate)
        elif speed != 100 and midi:
            rate = 44100 * speed / 100
            rate = int(rate)
        if speed != 100 and start:
            # adjust starting position for the current playback speed
            start = start / (speed / 100.0)

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
                    f"{speed}%",
                ]
                f.write(";".join(fields) + "\n")

        extra_info = ""
        if midi:
            sf2s = cmd["sf2s"]
            sf2 = random_choice(sf2s) if sf2s else None
            sf2s = list(self.sf2s.values())
            if not sf2s or MIDI_IMPL == MIDI_IMPL_NONE:
                return
            sf2 = self.sf2s[sf2] if sf2 in self.sf2s else random_choice(sf2s)
            sf2_name = real_filename(sf2)
            extra_info = f"with SF2 '{sf2_name}' "
            source = FFmpegMidiOpusAudio(filename, sf2_name, rate, start)
        else:
            source = FFmpegFileOpusAudio(filename, rate, start)

        # print log info
        print(
            f"Playing command '{cmd_name}' "
            f"on {channel.guild} "
            f"{extra_info}- "
            f"start: {start:.02f} s, "
            f"speed: {speed}%"
        )
        # update playback info for replays
        self.replay_info[channel.guild.id] = (
            channel,
            member,
            cmd_orig,
            # calculate starting timestamp according to current playback speed
            time() - start,
            speed,
        )

        if cmd_name:
            new_nick = f"!{cmd_name}"
            if pack:
                new_nick = f"{PACK_ICON} {new_nick}"
        else:
            new_nick = None
        self.bot.loop.create_task(self.update_nickname(channel.guild, new_nick))
        voice.play(source, after=loop and repeat or leave)
