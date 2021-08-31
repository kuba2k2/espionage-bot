import json
import subprocess
import sys
from os import mkdir
from os.path import isdir, isfile
from shlex import quote
from typing import Dict, Tuple

from discord import (
    ClientException,
    FFmpegOpusAudio,
    Guild,
    Member,
    VoiceChannel,
    VoiceClient,
)
from discord.ext.commands import CommandError, Context

from magic import Magic
from settings import FILES_JSON, SF2S_JSON

if sys.platform != "win32":
    CREATE_NO_WINDOW = 0
else:
    CREATE_NO_WINDOW = 0x08000000

archive_mimetypes = [
    "application/zip",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
    "application/x-tar",
    "application/gzip",
    "application/x-gtar",
]

magic_mime = Magic(mime=True)
magic_text = Magic(mime=False)


class FFmpegFileOpusAudio(FFmpegOpusAudio):
    def __init__(self, filename: str, *args, **kwargs):
        self.filename = filename
        super().__init__(filename, *args, **kwargs)


class FFmpegMidiOpusAudio(FFmpegOpusAudio):
    def __init__(self, filename: str, soundfont: str, *args, **kwargs):
        self.filename = filename.replace("\\", "/")
        self.soundfont = soundfont.replace("\\", "/")
        super().__init__("-", before_options="-f s32le", *args, **kwargs)

    def _spawn_process(self, args, **subprocess_kwargs):
        process = None
        try:
            cmdline = " ".join(args)
            cmdline = f"fluidsynth -a alsa -T raw -F - {quote(self.soundfont)} {quote(self.filename)} | {cmdline}"
            process = subprocess.Popen(
                cmdline, creationflags=CREATE_NO_WINDOW, shell=True, **subprocess_kwargs
            )
        except FileNotFoundError:
            executable = args.partition(" ")[0] if isinstance(args, str) else args[0]
            raise ClientException(executable + " was not found.") from None
        except subprocess.SubprocessError as exc:
            raise ClientException(
                "Popen failed: {0.__class__.__name__}: {0}".format(exc)
            ) from exc
        else:
            return process


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


def is_alone(voice: VoiceClient) -> bool:
    if not voice:
        return False
    return len(voice.channel.voice_states) <= 1


async def disconnect(voice: VoiceClient):
    await voice.disconnect()


async def ensure_voice(_, ctx: Context):
    member: Member = len(ctx.args) > 2 and ctx.args[2] or ctx.author
    if not member.voice:
        await ctx.send(f"User is not connected to a voice channel.", delete_after=3)
        raise CommandError(f"{ctx.author} not connected to a voice channel.")
    await connect_to(member.voice.channel)


async def ensure_can_modify(ctx: Context, cmd: dict):
    can_remove = ctx.author.id == cmd["author"]["id"]
    can_remove = (
        can_remove
        or ctx.author.guild.id == cmd["author"]["guild"]
        and ctx.author.guild_permissions.administrator
    )
    if not can_remove:
        await ctx.send(
            f"Only the author of the file or an admin can modify/remove it.",
            delete_after=3,
        )
        raise CommandError(f"File {cmd} is not modifiable by {ctx.author}")


async def ensure_command(ctx: Context, name: str, files: Dict[str, dict]) -> dict:
    if name not in files:
        await ctx.send(f"The command `!{name}` does not exist.", delete_after=3)
        raise CommandError(f"No such command: {name}")
    return files[name]


def pack_dirname(filename: str) -> str:
    dirname = filename.rpartition(".")[0] or filename
    if dirname == filename:
        dirname += "_pack"
    if not isdir(dirname):
        mkdir(dirname)
    return dirname


def filetype(filename: str) -> str:
    mime = magic_mime.from_file(filename)
    text = magic_text.from_file(filename)
    return mime, text


def check_file(filename: str) -> Tuple[bool, bool, bool, bool, bool]:
    mime_type, mime_text = filetype(filename)
    audio = mime_type.startswith("audio/")
    video = mime_type.startswith("video/")
    archive = mime_type in archive_mimetypes
    soundfont = "SoundFont/Bank" in mime_text
    midi = "audio/midi" == mime_type
    return audio or video, archive, soundfont, midi, video


def load_files() -> Dict[str, dict]:
    if not isfile(FILES_JSON):
        return {}
    with open(FILES_JSON, "r") as f:
        files = json.load(f)
    return files


def save_files(files: Dict[str, dict]):
    with open(FILES_JSON, "w") as f:
        json.dump(files, f, indent=4)


def load_sf2s() -> Dict[str, dict]:
    if not isfile(SF2S_JSON):
        return {}
    with open(SF2S_JSON, "r") as f:
        sf2s = json.load(f)
    return sf2s


def save_sf2s(sf2s: Dict[str, dict]):
    with open(SF2S_JSON, "w") as f:
        json.dump(sf2s, f, indent=4)
