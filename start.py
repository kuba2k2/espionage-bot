from asyncio import sleep
from typing import List, Dict

import discord
from discord import (
    VoiceChannel,
    VoiceClient,
    FFmpegOpusAudio,
    User,
    Message,
    Guild,
    Member,
    VoiceState,
)

from settings import BOT_TOKEN, ESPIONAGE_FILE, COMMANDS, FILES

client = discord.Client()

voice_clients: Dict[int, VoiceClient] = {}
voice_channels: Dict[int, VoiceChannel] = {}
voice_files: Dict[int, str] = {}


@client.event
async def on_ready():
    print("We have logged in as {0.user}".format(client))


@client.event
async def on_voice_state_update(member: Member, before: VoiceState, after: VoiceState):
    if member.id != client.user.id and (
        not after.afk or (before.channel and before.afk == after.afk)
    ):
        return
    if before.channel == after.channel:
        return
    guild: Guild = member.guild
    if member.id == client.user.id and not after.channel:
        voice_clients.pop(guild.id, None)
        voice_channels.pop(guild.id, None)
    if member.id == client.user.id and (not before.channel or not after.channel):
        return

    channel: VoiceChannel = after.channel

    # return if the bot is already connected
    if (
        guild.id in voice_channels
        and voice_clients[guild.id].is_connected()
        and voice_channels[guild.id].id == after.channel.id
    ):
        return

    # a user joined the afk channel, reset the file
    if member.id != client.user.id and after.afk and before.afk != after.afk:
        voice_files.pop(guild.id, None)

    file = voice_files[guild.id] if guild.id in voice_files else ESPIONAGE_FILE
    await play(channel, file)


async def play(channel: VoiceChannel, file: str):
    guild: Guild = channel.guild

    if guild.id in voice_clients:
        voice: VoiceClient = voice_clients[guild.id]
        if channel.id != voice.channel.id:
            print(f"+ Moving from {voice.channel} to {channel}")
            await voice.move_to(channel)
        if voice.is_paused():
            print(f"? Paused on {voice.channel}")
            await play_file(voice, file)
            return
    else:
        print(f"+ Joining {channel}")
        voice: VoiceClient = await channel.connect()
    voice_clients[guild.id] = voice
    voice_channels[guild.id] = channel

    members: List[Member] = await guild.query_members(user_ids=[client.user.id])
    if not members:
        return
    member: Member = members[0]
    # unmute self on AFK channel
    if member.voice.mute or member.voice.afk:
        print(f"? Unmuting self on {voice.channel}")
        await member.edit(mute=False)

    await play_file(voice, file)


async def play_file(voice: VoiceClient, file: str):
    voice.resume()
    # not connected - disconnect and play again
    if not voice.is_connected():
        print(f"!! Not connected to {voice.channel}, reconnecting...")
        await disconnect(voice)
        await play(voice.channel, file)
        return

    guild_id: int = voice.guild.id

    current_file = voice_files[guild_id] if guild_id in voice_files else None
    voice_files[guild_id] = file

    while voice.is_connected():
        file = voice_files[guild_id]
        print(f"> Playing {file} on {voice.channel}")
        if voice.is_paused() and file == current_file:
            voice.resume()
        elif not voice.is_playing() or file != current_file:
            voice.stop()
            source = FFmpegOpusAudio(file)
            voice.play(source)
        while voice.is_playing() and voice.is_connected():
            await sleep(0.1)
        # voice.stop()
        if len(voice.channel.voice_states) == 1 and voice.is_connected():
            await disconnect(voice)
    # voice_clients.pop(guild.id, None)
    # voice_channels.pop(guild.id, None)


async def disconnect(voice: VoiceClient):
    print(f"- Disconnecting from {voice.channel}")
    await voice.disconnect(force=True)
    guild: Guild = voice.guild
    voice_clients.pop(guild.id, None)
    voice_channels.pop(guild.id, None)


@client.event
async def on_message(message: Message):
    if message.author == client.user:
        return
    args: List[str] = message.content.split(" ")
    if not args or args[0] not in COMMANDS:
        return

    index = COMMANDS.index(args[0])
    file = FILES[index]

    author: User = message.author
    guild: Guild = message.guild
    members: List[Member] = await guild.query_members(user_ids=[author.id])
    if not members:
        return
    member: Member = members[0]
    state: VoiceState = member.voice
    if not state:
        return
    channel: VoiceChannel = state.channel
    if not channel:
        return

    await play(channel, file)


if __name__ == "__main__":
    client.run(BOT_TOKEN)
