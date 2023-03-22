from typing import Dict

from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context

from settings import COG_ESPIONAGE, COG_MUSIC, RANDOM_FILE
from utils import ensure_command, ensure_voice, save_files


class Music(Cog, name=COG_MUSIC):
    def __init__(self, bot: Bot, files: Dict[str, dict], sf2s: Dict[str, str]):
        self.bot = bot
        self.files = files
        self.sf2s = sf2s
        self.espionage = self.bot.get_cog(COG_ESPIONAGE)

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
    @commands.guild_only()
    async def loop(self, ctx: Context, name: str = None):
        """Enable/disable looping of the specified audio."""
        if not name:
            await ctx.send("Usage: `!loop <command name>`.", delete_after=3)
            return

        cmd = await ensure_command(ctx, name, self.files)
        pack = "pack" in cmd and cmd["pack"]
        if pack:
            await ctx.send(
                f":file_folder: `!{name}` is a music pack; try using `!random {name}` to toggle its random playback.",
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
            await ctx.send(
                f":white_check_mark: Looping enabled for `!{name}`.", delete_after=3
            )
        else:
            await ctx.send(f":x: Looping disabled for `!{name}`.", delete_after=3)

    @commands.command()
    @commands.guild_only()
    async def speed(self, ctx: Context, name: str = None, speed: str = None):
        """Set the playing speed (percent)."""
        if not name or not speed:
            await ctx.send("Usage: `!speed <command name> <speed>`.", delete_after=3)
            return

        speed = speed.rstrip("%")
        try:
            speed = float(speed)
        except ValueError:
            await ctx.send(f"`{speed}` is not a valid number.", delete_after=3)
            return

        # 0.0-10.0 -> 0%-1000%
        if speed <= 10.0:
            speed *= 100
        speed = int(speed)

        cmd = await ensure_command(ctx, name, self.files)
        pack = "pack" in cmd and cmd["pack"]
        midi = "midi" in cmd and cmd["midi"]
        if pack:
            await ctx.send(
                f":file_folder: `!{name}` is a music pack. Speed changing is not possible.",
                delete_after=10,
            )
            return
        if not midi and "info" not in cmd:
            await ctx.send(
                f"Speed changing is not possible - missing file metadata.",
                delete_after=10,
            )
            return

        if speed != 100:
            cmd["speed"] = speed
        else:
            cmd.pop("speed", None)

        # save the command descriptors
        save_files(self.files)

        await ctx.send(f"Speed of `!{name}` set to {speed}%.", delete_after=3)

    @commands.command()
    @commands.guild_only()
    async def sf(self, ctx: Context, name: str = None, *sf2_names):
        """List or set SoundFonts for MIDI files."""
        if not name:
            lines = [
                "Available SoundFonts:",
            ]
            max_length = max(len(name) for name in self.sf2s.keys())
            for name, sf2 in self.sf2s.items():
                padding = " " * (max_length - len(name) + 2)
                lines.append(f"  {name} {padding} {sf2['help']}")
            lines.append(
                "\nUse !sf <midi name> <sf name> to apply a SoundFont to a file."
            )
            lines = "\n".join(lines)
            await ctx.send(f"```\n{lines}```")
            return

        cmd = await ensure_command(ctx, name, self.files)
        midi = "midi" in cmd and cmd["midi"]
        if not midi:
            await ctx.send(
                f"`!{name}` is not and doesn't contain MIDI files.", delete_after=3
            )
            return

        if not sf2_names:
            sf2s = cmd["sf2s"]
            sf2s = "\n".join(sf2s)
            await ctx.send(
                f"`!{name}` is currently using these SoundFonts:\n```{sf2s}```"
            )
            return

        for sf2 in sf2_names:
            if sf2 not in self.sf2s:
                await ctx.send(f"SoundFont {sf2} does not exist.", delete_after=3)
                return

        cmd["sf2s"] = sf2_names
        save_files(self.files)
        await ctx.send(f"Updated SoundFonts for `!{name}`.", delete_after=3)
