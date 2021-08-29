import os
from os import unlink
from os.path import isdir, isfile
from shutil import rmtree
from time import time
from typing import Dict

import patoolib
from discord import Attachment, Message
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context

from settings import COG_ESPIONAGE, COG_UPLOADING
from utils import (
    archive_mimetypes,
    ensure_can_modify,
    ensure_command,
    filetype,
    pack_dirname,
    save_files,
)


class Uploading(Cog, name=COG_UPLOADING):
    def __init__(self, bot: Bot, files: Dict[str, dict], path: str):
        self.bot = bot
        self.files = files
        self.path = path
        self.espionage = self.bot.get_cog(COG_ESPIONAGE)

    @commands.command()
    @commands.guild_only()
    async def pack(self, ctx: Context, name: str = None):
        """Change the command to be a music pack."""
        if not name:
            await ctx.send("Usage: `!pack <command name>`.", delete_after=3)
            return

        # get the command or raise an error
        cmd = await ensure_command(ctx, name, self.files)
        await ensure_can_modify(ctx, cmd)

        pack = "pack" in cmd and cmd["pack"]
        if pack:
            await ctx.send(f"`!{name}` is already a music pack.", delete_after=3)
            return

        # TODO handle situation when the file is currently playing
        # thus used by FFmpeg and may be locked

        dirname = pack_dirname(f"{self.path}/{int(time())}_{name}")
        filename = cmd["filename"].rpartition("/")[2]
        filename = f"{dirname}/{filename}"
        os.replace(cmd["filename"], filename)

        cmd["filename"] = dirname
        cmd["pack"] = True

        # remove the command to update help text
        self.espionage.remove_command(name)
        self.espionage.add_command(name)

        # save the command descriptors
        save_files(self.files)
        await ctx.send(
            f"Converted `!{name}` as a music pack. Try uploading more files with `!upload {name}`.",
            delete_after=10,
        )

    @commands.command()
    @commands.guild_only()
    async def upload(self, ctx: Context, name: str = None):
        """Upload the attached file(s) as a command."""
        message: Message = ctx.message
        if not name:
            await ctx.send(
                "Usage: `!upload <command name>`. Attach at least one audio file.",
                delete_after=3,
            )
            return

        if len(message.attachments) == 0:
            await ctx.send("You must add at least one attachment.", delete_after=3)
            return

        cmd = None
        pack = False
        existing = False
        count = len(message.attachments)
        extracted_count = 0
        invalid_count = 0
        invalid_name = ""

        # replace the command or add to a pack
        if name in self.files:
            cmd = self.files[name]
            pack = "pack" in cmd and cmd["pack"]
            existing = True
            if not pack:
                ensure_can_modify(ctx, cmd)
                unlink(cmd["filename"])

        pack = pack or len(message.attachments) > 1

        if pack:
            if cmd:
                # store to an existing pack
                dirname = cmd["filename"]
            else:
                # create a new pack
                dirname = pack_dirname(f"{self.path}/{int(time())}_{name}")
        else:
            # store directly to uploads
            dirname = self.path

        # save all attachments
        for attachment in message.attachments:
            # create a safe filename
            filename = f"{dirname}/{int(time())}_{attachment.filename}"
            # save the attachment
            with open(filename, "wb") as f:
                await attachment.save(f)

            mime_type, mime_text = filetype(filename)
            audio = mime_type.startswith("audio/")
            video = mime_type.startswith("video/")
            archive = mime_type in archive_mimetypes

            if archive:
                # create a new pack
                if not pack:
                    dirname = pack_dirname(filename)
                    pack = True
                # unpack the archive
                # TODO count extracted files
                # extracted_count += len(patoolib.list_archive(filename))
                patoolib.extract_archive(filename, outdir=dirname)
                # delete the archive
                unlink(filename)
            elif not audio and not video:
                invalid_count += 1
                invalid_name = attachment.filename
                if count == 1:
                    await ctx.send(
                        f"Unrecognized file: **{attachment.filename}**", delete_after=3
                    )
                    unlink(filename)
                    return

        if not pack or not existing:
            # store/replace the command descriptor
            cmd = {
                "filename": filename if not pack else dirname,
                "help": f"Uploaded by {ctx.author}",
                "loop": True,
                "author": {
                    "id": ctx.author.id,
                    "guild": ctx.guild.id,
                },
            }
            if pack:
                cmd["pack"] = True
            self.files[name] = cmd

        # add the command to the music cog
        self.espionage.add_command(name)
        # save the command descriptors
        save_files(self.files)

        count += extracted_count
        count -= invalid_count
        if pack and existing and count == 1:
            text = f"Added **{attachment.filename}** to `!{name}`."
        elif count > 1:
            text = f"Uploaded **{count}** file(s) to `!{name}`."
        elif not existing:
            text = f"File **{attachment.filename}** uploaded as `!{name}`."
        else:
            text = f"Replaced `!{name}` with **{attachment.filename}**."

        if invalid_count == 1:
            text += f"\nFile **{invalid_name}** was unrecognized."
        elif invalid_count:
            text += f"\n**{invalid_count}** file(s) were unrecognized."

        await ctx.send(text, delete_after=10)

    @commands.command()
    @commands.guild_only()
    async def aremove(self, ctx: Context, name: str = None):
        """Remove the specified audio."""
        if not name:
            await ctx.send("Usage: `!aremove <command name>`.", delete_after=3)
            return

        # get the command or raise an error
        cmd = await ensure_command(ctx, name, self.files)
        await ensure_can_modify(ctx, cmd)
        # remove the command
        self.espionage.remove_command(name)
        self.files.pop(name, None)
        filename = cmd["filename"]
        if isfile(filename):
            unlink(filename)
        elif isdir(filename):
            rmtree(filename)

        # save the command descriptors
        save_files(self.files)
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

        # get the command or raise an error
        cmd = await ensure_command(ctx, name, self.files)
        await ensure_can_modify(ctx, cmd)
        # remove the command to update help text
        self.espionage.remove_command(name)
        cmd["help"] = description
        self.espionage.add_command(name)

        # save the command descriptors
        save_files(self.files)
        await ctx.send(
            f"Description of `!{name}` set to `{description}`.", delete_after=3
        )
