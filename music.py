from typing import Dict

from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context

from espionage import Espionage
from settings import COG_ESPIONAGE, COG_MUSIC, RANDOM_FILE
from utils import (
    check_playing_cmd,
    ensure_command,
    ensure_voice,
    normalize_percent,
    save_files,
)


class Music(Cog, name=COG_MUSIC):
    def __init__(self, bot: Bot, files: Dict[str, dict], sf2s: Dict[str, str]):
        self.bot = bot
        self.files = files
        self.sf2s = sf2s
        self.espionage: Espionage = self.bot.get_cog(COG_ESPIONAGE)

    @commands.command()
    @commands.guild_only()
    @commands.before_invoke(ensure_voice)
    async def random(self, ctx: Context):
        """Randomly play files from the global directory."""
        await self.espionage.play(
            channel=ctx.voice_client.channel,
            member=ctx.message.author,
            cmd=RANDOM_FILE,
        )

    @commands.command()
    async def loop(self, ctx: Context, name: str = None):
        """Enable/disable looping of the specified audio."""
        if not name:
            await ctx.send(":question: Usage: `!loop <command name>`.", delete_after=3)
            return

        cmd = await ensure_command(ctx, name, self.files)
        pack = "pack" in cmd and cmd["pack"]
        if pack:
            await ctx.send(
                f":x: :file_folder: `!{name}` is a music pack; try using `!random {name}` to toggle its random playback.",
                delete_after=10,
            )
            return

        cmd["loop"] = not cmd["loop"]

        # remove the command to update help text
        self.espionage.remove_command(name)
        self.espionage.add_command(name)
        # save the command descriptors
        save_files(self.files)

        if cmd["loop"]:
            await ctx.send(f":v: :white_check_mark: Looping enabled for `!{name}`.")
        else:
            await ctx.send(f":v: :x: Looping disabled for `!{name}`.")

    @commands.command()
    async def speed(self, ctx: Context, name: str = None, speed: str = None):
        """Set the playing speed (percent)."""
        name, speed = await check_playing_cmd(ctx, self.espionage, name, speed)
        if not name:
            await ctx.send(
                ":question: Usage: `!speed <command name> <speed%>`.",
                delete_after=3,
            )
            return
        if not speed:
            await ctx.send(
                ":question: Usage: `!speed [command name] <speed%>`.",
                delete_after=3,
            )
            return

        speed = await normalize_percent(ctx, speed)
        if speed not in range(1, 10001):
            await ctx.send(f":x: Speed must be in [1,10000]% range.", delete_after=3)
            return

        cmd = await ensure_command(ctx, name, self.files)
        pack = "pack" in cmd and cmd["pack"]
        midi = "midi" in cmd and cmd["midi"]
        if pack and not midi:
            await ctx.send(
                f":x: :file_folder: `!{name}` is a music pack. Speed changing is not possible.",
                delete_after=10,
            )
            return
        if not midi and "info" not in cmd:
            await ctx.send(
                f":x: Speed changing is not possible - missing file metadata.",
                delete_after=10,
            )
            return

        if speed != 100:
            cmd["speed"] = speed
        else:
            cmd.pop("speed", None)

        # save the command descriptors
        save_files(self.files)

        await ctx.send(f":v: Speed of `!{name}` set to {speed}%.")

        if ctx.guild and ctx.guild.voice_client:
            self.espionage.reload(guild=ctx.guild)

    @commands.command()
    async def sf(self, ctx: Context, name: str = None, sf2: str = None):
        """List or set SoundFonts for MIDI files."""
        name, sf2 = await check_playing_cmd(ctx, self.espionage, name, sf2)
        if not name or not sf2:
            lines = [
                ":v: Available SoundFonts:",
            ]
            max(len(name) for name in self.sf2s.keys())
            for name, sf2 in self.sf2s.items():
                lines.append(f"- `{name}` - {sf2['help']}")
            lines.append(
                "\n:question: Use `!sf <sf name>` to apply a SoundFont to a file."
            )
            lines = "\n".join(lines)
            await ctx.send(f"{lines}")
            return

        if sf2 not in self.sf2s:
            await ctx.send(f"SoundFont {sf2} does not exist.", delete_after=3)
            return

        cmd = await ensure_command(ctx, name, self.files)
        midi = "midi" in cmd and cmd["midi"]
        if not midi:
            await ctx.send(
                f":x: `!{name}` is not a MIDI file and doesn't contain any.",
                delete_after=3,
            )
            return

        cmd["sf2s"] = [sf2]
        save_files(self.files)

        await ctx.send(f":v: Updated SoundFonts for `!{name}`.")

        if ctx.guild and ctx.guild.voice_client:
            self.espionage.reload(guild=ctx.guild)
