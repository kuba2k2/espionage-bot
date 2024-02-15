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

        if "filters" not in cmd:
            await ctx.send(
                f":question: No filters added to `!{name}`.\n"
                "Use `!help eq` to see available filters.",
                delete_after=3,
            )
            return
        lines = [
            f":v: Filters added to `!{name}`:",
        ]
        eq: List[str] = cmd["filters"]
        for line in eq:
            title, _, _ = line.partition("#")
            lines.append(f"- `{title}`")
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
            delete_after=10,
        )

        if ctx.guild and ctx.guild.voice_client:
            self.espionage.reload(guild=ctx.guild)

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
            delete_after=3,
        )

        if ctx.guild and ctx.guild.voice_client:
            self.espionage.reload(guild=ctx.guild)

    @eq.command()
    @commands.before_invoke(ensure_playing)
    async def volume(self, ctx: Context, volume: str = None):
        """Change audio volume (percent)."""
        if not volume:
            await ctx.send(":question: Usage: `!eq volume <volume%>`.", delete_after=3)
            return
        volume = await normalize_percent(ctx, volume)
        await self.add_filter(ctx, f"{volume}% Volume", f"volume={volume / 100.0:.02f}")
