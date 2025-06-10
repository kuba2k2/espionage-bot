import re
from math import log
from typing import Dict, List

from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context

from espionage import Espionage
from settings import COG_EQUALIZER, COG_ESPIONAGE
from utils import (
    check_playing_cmd,
    ensure_command,
    ensure_playing,
    normalize_percent,
    save_files,
)


class Equalizer(Cog, name=COG_EQUALIZER):
    def __init__(self, bot: Bot, files: Dict[str, dict], sf2s: Dict[str, str]):
        self.bot = bot
        self.files = files
        self.espionage: Espionage = self.bot.get_cog(COG_ESPIONAGE)

    @commands.group(invoke_without_command=True)
    @commands.before_invoke(ensure_playing)
    async def eq(self, ctx: Context):
        """Adjust audio filters (effects)."""
        (name,) = await check_playing_cmd(ctx, self.espionage, None)
        cmd = await ensure_command(ctx, name, self.files)

        if "filters" not in cmd and "speed" not in cmd:
            await ctx.send(
                f":question: No filters added to `!{name}`.\n"
                "Use `!eq help` to see available filters.",
                delete_after=3,
            )
            return
        lines = [
            f":v: Filters added to `!{name}`:",
        ]
        if "speed" in cmd:
            lines.append(f"- {cmd['speed']}% Speed")
        eq: List[str] = cmd.get("filters", [])
        for line in eq:
            title, _, _ = line.partition("#")
            lines.append(f"- {title}")
        lines.append("Use `!eq help` to see available filters.")
        lines.append("Use `!eq reset` to clear all filters.")
        await ctx.send("\n".join(lines))

    async def add_filter(self, ctx: Context, title: str, value: str):
        (name,) = await check_playing_cmd(ctx, self.espionage, None)
        cmd = await ensure_command(ctx, name, self.files)
        # add the filter
        if "filters" not in cmd:
            cmd["filters"] = []
        cmd["filters"].append(f"{title}#{value}")
        # save the command descriptors
        save_files(self.files)

        await ctx.send(
            f":v: Filter `{title}` added to `!{name}`.\n"
            "Use `!eq reset` to clear all filters.",
        )

        if ctx.guild and ctx.guild.voice_client:
            self.espionage.reload(guild=ctx.guild)

    @eq.command()
    async def help(self, ctx: Context):
        """See available filters."""
        await ctx.send_help(self.eq)

    @eq.command()
    @commands.before_invoke(ensure_playing)
    async def reset(self, ctx: Context):
        """Reset all filters (effects)."""
        (name,) = await check_playing_cmd(ctx, self.espionage, None)
        cmd = await ensure_command(ctx, name, self.files)
        # clear all filters
        cmd.pop("filters", None)
        # save the command descriptors
        save_files(self.files)

        await ctx.send(
            f":v: Cleared all filters of `!{name}`.\n"
            "Use `!help eq` to see available filters.",
        )

        if ctx.guild and ctx.guild.voice_client:
            self.espionage.reload(guild=ctx.guild)

    @eq.command()
    @commands.before_invoke(ensure_playing)
    async def raw(self, ctx: Context, name: str = None, *opts: str):
        """Add raw ffmpeg audio filter."""
        if not name:
            await ctx.send(
                ":question: Usage: `!eq raw <filter name> [...option=value]`.",
                delete_after=3,
            )
            return
        for s in [name, *opts]:
            if not re.match(r"^[A-Za-z0-9:=._ -]+$", s):
                await ctx.send(
                    ":x: Illegal characters in filter string.",
                    delete_after=3,
                )
                return
        if opts:
            value = f"{name}={':'.join(opts)}"
        else:
            value = name
        await self.add_filter(ctx, f"Raw: {value}", value)

    @eq.command()
    @commands.before_invoke(ensure_playing)
    async def volume(self, ctx: Context, volume: str = None):
        """Change audio volume (percent)."""
        if not volume:
            await ctx.send(":question: Usage: `!eq volume <volume%>`.", delete_after=3)
            return
        volume = await normalize_percent(ctx, volume)
        await self.add_filter(ctx, f"{volume}% Volume", f"volume={volume / 100.0:.02f}")

    @eq.command()
    @commands.before_invoke(ensure_playing)
    async def pitch(self, ctx: Context, pitch: str = None):
        """Change audio pitch (percent)."""
        if not pitch:
            await ctx.send(":question: Usage: `!eq pitch <pitch%>`.", delete_after=3)
            return
        pitch = await normalize_percent(ctx, pitch)
        await self.add_filter(
            ctx,
            f"{pitch}% Pitch",
            f"asetrate=44100*{pitch / 100.0:.02f},"
            f"aresample=44100,"
            f"atempo=1/{pitch / 100.0:.02f}",
        )

    @eq.command()
    @commands.before_invoke(ensure_playing)
    async def bass(self, ctx: Context, gain: str = None, freq: int = 100):
        """Change bass gain (percent)."""
        if not gain:
            await ctx.send(
                ":question: Usage: `!eq bass <gain%> [freqHz]`.",
                delete_after=3,
            )
            return
        gain = await normalize_percent(ctx, gain)
        gain_db = 10 * log(gain / 100.0, 10)
        await self.add_filter(
            ctx,
            f"{gain}% Bass {freq} Hz",
            f"bass=g={gain_db:.02f}",
        )

    @eq.command()
    @commands.before_invoke(ensure_playing)
    async def treble(self, ctx: Context, gain: str = None, freq: int = 8000):
        """Change treble gain (percent)."""
        if not gain:
            await ctx.send(
                ":question: Usage: `!eq treble <gain%> [freqHz]`.",
                delete_after=3,
            )
            return
        gain = await normalize_percent(ctx, gain)
        gain_db = 10 * log(gain / 100.0, 10)
        await self.add_filter(
            ctx,
            f"{gain}% Treble {freq} Hz",
            f"treble=g={gain_db:.02f}",
        )

    @eq.command()
    @commands.before_invoke(ensure_playing)
    async def vibrato(self, ctx: Context, freq: int = 10):
        """Apply vibrato effect."""
        if not freq:
            await ctx.send(
                ":question: Usage: `!eq vibrato [freqHz=10]`.",
                delete_after=3,
            )
            return
        await self.add_filter(
            ctx,
            f"Vibrato {freq} Hz",
            f"vibrato=f={freq}",
        )

    @eq.command()
    @commands.before_invoke(ensure_playing)
    async def bitrate(self, ctx: Context, bitrate: str = None):
        """Apply vibrato effect."""
        if not bitrate:
            await ctx.send(
                ":question: Usage: `!eq bitrate <bitrate>k`.",
                delete_after=3,
            )
            return
        bitrate = re.sub(r"[^0-9]", "", bitrate)
        await self.add_filter(
            ctx,
            f"{bitrate} kb/s",
            f"-b:a {bitrate}k",
        )
