import json
from typing import Dict

from discord import FFmpegOpusAudio, Guild, Member, VoiceChannel, VoiceClient
from discord.ext.commands import CommandError, Context

from settings import FILES_JSON


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
    member: Member = len(ctx.args) > 2 and ctx.args[2] or ctx.author
    if not member.voice:
        await ctx.send(f"User is not connected to a voice channel.", delete_after=3)
        raise CommandError(f"{ctx.author} not connected to a voice channel.")
    await connect_to(member.voice.channel)


def load_files() -> Dict[str, dict]:
    with open(FILES_JSON, "r") as f:
        files = json.load(f)
    return files


def save_files(files: Dict[str, dict]):
    with open(FILES_JSON, "w") as f:
        json.dump(files, f, indent=4)
