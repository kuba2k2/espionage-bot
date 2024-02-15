import json
import subprocess
import sys
from os import mkdir
from os.path import isabs, isdir, isfile, join
from shlex import quote, split
from typing import Dict, List, Tuple, Union

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

from settings import (
    FILES_JSON,
    MIDI_IMPL,
    MIDI_IMPL_FLUIDSYNTH,
    MIDI_IMPL_TIMIDITY,
    MIDI_MUTE_124,
    MIDI_MUTE_124_FILE,
    SF2S_JSON,
    UPLOAD_PATH,
)

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
    def __init__(
        self,
        filename: str,
        rate: int,
        start: float,
        *args,
        **kwargs,
    ):
        self.filename = filename

        if rate:
            opts = f"-af asetrate={rate}"
        else:
            opts = ""

        if start:
            opts += f" -ss {start:.02f}"

        super().__init__(filename, options=opts, *args, **kwargs)


class FFmpegMidiOpusAudio(FFmpegOpusAudio):
    def __init__(
        self,
        filename: str,
        soundfont: str,
        rate: int,
        start: float,
        *args,
        **kwargs,
    ):
        self.filename = filename.replace("\\", "/")
        self.soundfont = soundfont.replace("\\", "/")
        self.impl = MIDI_IMPL
        self.rate = rate

        if self.impl == MIDI_IMPL_FLUIDSYNTH:
            before_opts = [
                "-f s32le",
                "-ac 2",
                "-guess_layout_max 0",
            ]
        else:
            before_opts = []

        if rate:
            opts = f"-af asetrate={rate},aformat=channel_layouts=2"
        else:
            opts = ""

        super().__init__(
            "-", before_options=" ".join(before_opts), options=opts, *args, **kwargs
        )

    def _get_cmd(self, super_args) -> str:
        if self.impl == MIDI_IMPL_FLUIDSYNTH:
            args = self._get_args_fs()
        elif self.impl == MIDI_IMPL_TIMIDITY:
            args = self._get_args_tm()
        else:
            return " ".join(super_args)
        args.append("|")
        args.extend(super_args)
        return " ".join(args)

    def _get_args_fs(self) -> List[str]:
        args = [
            "fluidsynth",
            "-a alsa",  # The audio driver to use
            "-T raw",  # Audio file type for fast rendering or aufile driver
            "-O s32",  # Audio file format for fast rendering or aufile driver
            "-E little",  # Audio file endian for fast rendering or aufile driver
            "-r 44100",  # Set the sample rate
            "-L 1",  # The number of stereo audio channels
            "-g 1.0",  # Set the master gain
            "-F -",  # Render MIDI file to raw audio data and store in [file]
            "-q",  # Do not print welcome message or other informational output
            quote(self.soundfont),
            quote(self.filename),
        ]
        if MIDI_MUTE_124:
            args.append(MIDI_MUTE_124_FILE)
        return args

    def _get_args_tm(self) -> List[str]:
        opts = [
            f"soundfont {quote(self.soundfont)}",
            "opt EFchorus=d",
            "opt EFreverb=d",
            "opt EFdelay=d",
        ]
        if MIDI_MUTE_124:
            opts.append("font exclude 0 124")
        opts = "\\n".join(opts)
        args = [
            "timidity",
            f'-x "{opts}"',  # Configure TiMidity++ with str
            "-Ow",  # Generate RIFF WAVE format output
            "-o -",  # Place output on file
            quote(self.filename),
        ]
        return args

    def _spawn_process(self, args, **subprocess_kwargs):
        process = None
        try:
            cmdline = self._get_cmd(args)
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
    if ctx.author.guild:
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


def real_filename(cmd: dict) -> str:
    filename = cmd["filename"]
    if not isabs(filename):
        filename = join(UPLOAD_PATH, filename)
    return filename


def filetype(filename: str) -> str:
    mime = magic_mime.from_file(filename)
    text = magic_text.from_file(filename)
    return mime, text


def check_file(filename: str) -> Tuple[bool, bool, bool, bool, bool]:
    mime_type, mime_text = filetype(filename)
    soundfont = "audio/x-sfbk" == mime_type or "SoundFont/Bank" in mime_text
    if soundfont:
        return False, False, True, False, False
    audio = mime_type.startswith("audio/")
    video = mime_type.startswith("video/")
    archive = mime_type in archive_mimetypes
    midi = "audio/midi" == mime_type
    return audio or video, archive, soundfont, midi, video


def get_audio_info(filename: str) -> Union[dict, None]:
    cmd = [
        "ffprobe",
        "-show_streams",
        "-of json",
        quote(filename),
    ]
    cmd = " ".join(cmd)
    result = subprocess.run(split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    data = result.stdout.decode()
    data = json.loads(data)
    if not "streams" in data:
        return None
    data = [s for s in data["streams"] if s["codec_type"] == "audio"]
    if not data:
        return None
    return data[0]


def fill_audio_info(cmd: dict):
    pack = "pack" in cmd and cmd["pack"]
    midi = "midi" in cmd and cmd["midi"]
    if pack or midi:
        return
    filename = real_filename(cmd)
    info = get_audio_info(filename)
    if not info:
        return
    cmd["info"] = {
        "sample_rate": int(info["sample_rate"]),
        "duration": float(info.get("duration") or 0),
        "channels": int(info["channels"]),
        "codec": info["codec_name"],
    }


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
