from os import unlink
from os.path import isfile
from time import time
from typing import Dict

from discord import Attachment, Message
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context

from settings import COG_UPLOADING
from utils import save_files


class Uploading(Cog, name=COG_UPLOADING):
    def __init__(self, bot: Bot, files: Dict[str, dict], path: str):
        self.bot = bot
        self.files = files
        self.path = path

    @commands.command()
    @commands.guild_only()
    async def upload(self, ctx: Context, name: str = None):
        """Upload the attached file as a command."""
        message: Message = ctx.message
        if not name:
            await ctx.send(
                "Usage: `!upload <command name>`. Attach one audio file.",
                delete_after=3,
            )
            return
        if len(message.attachments) != 1:
            await ctx.send("You must add exactly one attachment.", delete_after=3)
            return
        attachment: Attachment = message.attachments[0]

        espionage: Espionage = self.bot.get_cog(COG_ESPIONAGE)
        if not espionage:
            return
        files = espionage.files

        replaced = False
        # delete the already existing file
        if self.bot.get_command(name):
            replaced = True
            unlink(files[name]["filename"])

        # create a safe filename
        filename = f"{self.path}/{int(time())}_{attachment.filename}"

        # save the attachment
        with open(filename, "wb") as f:
            await attachment.save(f)

        # replace the command descriptor
        files[name] = {
            "filename": filename,
            "help": f"Uploaded by {ctx.author}",
            "loop": True,
            "author": {
                "id": ctx.author.id,
                "guild": ctx.guild.id,
            },
        }

        # add the command to the music cog
        espionage.add_command(name)
        # save the command descriptors
        save_files(files)

        await ctx.send(
            f"File **{attachment.filename}** uploaded as `!{name}`."
            if not replaced
            else f"Replaced `!{name}` with **{attachment.filename}**.",
            delete_after=10,
        )

    @commands.command()
    @commands.guild_only()
    async def eloop(self, ctx: Context, name: str = None):
        """Enable looping of the specified audio."""
        if not name:
            await ctx.send("Usage: `!enoloop <command name>`.", delete_after=3)
            return
        if not self.set_loop(name, True):
            await ctx.send(f"The command `!{name}` does not exist.", delete_after=3)
            return
        await ctx.send(f"Looping enabled for `!{name}`.", delete_after=3)

    @commands.command()
    @commands.guild_only()
    async def enoloop(self, ctx: Context, name: str = None):
        """Disable looping of the specified audio."""
        if not name:
            await ctx.send("Usage: `!enoloop <command name>`.", delete_after=3)
            return
        if not self.set_loop(name, False):
            await ctx.send(f"The command `!{name}` does not exist.", delete_after=3)
            return
        await ctx.send(f"Looping disabled for `!{name}`.", delete_after=3)

    def set_loop(self, name: str, loop: bool) -> bool:
        espionage: Espionage = self.bot.get_cog(COG_ESPIONAGE)
        if not espionage:
            return
        files = espionage.files

        if name not in files:
            return False

        if files[name]["loop"] != loop:
            files[name]["loop"] = loop
            # remove the command to update help text
            espionage.remove_command(name)
            espionage.add_command(name)
            # save the command descriptors
            save_files(files)
        return True

    @commands.command()
    @commands.guild_only()
    async def aremove(self, ctx: Context, name: str = None):
        """Remove the specified audio."""
        if not name:
            await ctx.send("Usage: `!aremove <command name>`.", delete_after=3)
            return
        espionage: Espionage = self.bot.get_cog(COG_ESPIONAGE)
        if not espionage:
            return
        files = espionage.files
        if name not in files:
            await ctx.send(f"The command `!{name}` does not exist.", delete_after=3)
            return
        can_remove = (
            ctx.author.guild_permissions.administrator
            and ctx.author.guild.id == files[name]["author"]["guild"]
        )
        can_remove = can_remove or ctx.author.id == files[name]["author"]["id"]
        if not can_remove:
            await ctx.send(
                f"Only the author of the file or an admin can remove it.",
                delete_after=3,
            )
            return
        espionage.remove_command(name)
        cmd = files.pop(name, None)
        if cmd and isfile(cmd["filename"]):
            unlink(cmd["filename"])
        # save the command descriptors
        save_files(files)
        await ctx.send(f"Command `!{name}` removed.", delete_after=3)

    @commands.command()
    @commands.guild_only()
    async def description(self, ctx: Context, name: str = None, *args):
        """Change the description."""
        description = " ".join(args)
        if not name or not description:
            await ctx.send(
                "Usage: `!description <command name> <description>`.", delete_after=3
            )
            return
        espionage: Espionage = self.bot.get_cog(COG_ESPIONAGE)
        if not espionage:
            return
        files = espionage.files
        if name not in files:
            await ctx.send(f"The command `!{name}` does not exist.", delete_after=3)
            return
        files[name]["help"] = description
        # remove the command to update help text
        espionage.remove_command(name)
        espionage.add_command(name)
        # save the command descriptors
        save_files(files)
        await ctx.send(
            f"Description of `!{name}` set to `{description}`.", delete_after=3
        )
