from typing import Dict

from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context

from espionage import Espionage
from settings import COG_ESPIONAGE, COG_MUSIC, RANDOM_FILE
from utils import ensure_command, ensure_voice, save_files


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
            await ctx.send(
                f":v: :white_check_mark: Looping enabled for `!{name}`.", delete_after=3
            )
        else:
            await ctx.send(f":v: :x: Looping disabled for `!{name}`.", delete_after=3)

    @commands.command()
    async def speed(self, ctx: Context, name: str = None, speed: str = None):
        """Set the playing speed (percent)."""
        if ctx.guild and ctx.channel.guild.voice_client:
            replay_info = self.espionage.replay_info.get(ctx.channel.guild.id, None)
            if replay_info and name and not speed:
                speed = name
                _, _, name, _, _ = replay_info

        if not speed:
            if name and name in self.files:
                await ctx.send(
                    ":question: Usage: `!speed [command name] <speed%>`.",
                    delete_after=3,
                )
            else:
                await ctx.send(
                    ":question: Usage: `!speed <command name> <speed%>`.",
                    delete_after=3,
                )
            return

        is_percent = False
        if speed.endswith("%"):
            is_percent = True

        speed = speed.rstrip("%")
        try:
            speed = float(speed)
        except ValueError:
            await ctx.send(f":x: `{speed}` is not a valid number.", delete_after=3)
            return

        # 0.0-5.0 -> 0%-500%
        if not is_percent and speed <= 5.0:
            speed *= 100
        speed = int(speed)

        if speed not in range(1, 10001):
            await ctx.send(f":x: Speed must be in [1,10000]% range.", delete_after=3)
            return

        cmd = await ensure_command(ctx, name, self.files)
        pack = "pack" in cmd and cmd["pack"]
        midi = "midi" in cmd and cmd["midi"]
        if pack:
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

        await ctx.send(f":v: Speed of `!{name}` set to {speed}%.", delete_after=3)

        if ctx.guild and ctx.guild.voice_client:
            self.espionage.reload(guild=ctx.guild, rewind=False)

    @commands.command()
    async def sf(self, ctx: Context, name: str = None, *sf2_names):
        """List or set SoundFonts for MIDI files."""
        if not name:
            lines = [
                ":v: Available SoundFonts:",
            ]
            max_length = max(len(name) for name in self.sf2s.keys())
            for name, sf2 in self.sf2s.items():
                padding = " " * (max_length - len(name) + 2)
                lines.append(f"  {name} {padding} {sf2['help']}")
            lines.append(
                "\n:question: Use !sf <midi name> <sf name> to apply a SoundFont to a file."
            )
            lines = "\n".join(lines)
            await ctx.send(f"```\n{lines}```")
            return

        cmd = await ensure_command(ctx, name, self.files)
        midi = "midi" in cmd and cmd["midi"]
        if not midi:
            await ctx.send(
                f":x: `!{name}` is not and doesn't contain MIDI files.", delete_after=3
            )
            return

        if not sf2_names:
            sf2s = cmd["sf2s"]
            sf2s = "\n".join(sf2s)
            await ctx.send(
                f":v: `!{name}` is currently using these SoundFonts:\n```{sf2s}```"
            )
            return

        for sf2 in sf2_names:
            if sf2 not in self.sf2s:
                await ctx.send(f"SoundFont {sf2} does not exist.", delete_after=3)
                return

        cmd["sf2s"] = sf2_names
        save_files(self.files)
        await ctx.send(f":v: Updated SoundFonts for `!{name}`.", delete_after=3)
