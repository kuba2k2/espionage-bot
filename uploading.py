from os import mkdir, replace, unlink
from os.path import basename, isdir, isfile, join
from pathlib import Path
from shutil import rmtree
from time import time
from typing import Dict

import patoolib
from discord import Message
from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context
from sf2utils.sf2parse import Sf2File

from settings import CMD_VERSION, COG_ESPIONAGE, COG_UPLOADING, UPLOAD_PATH
from utils import (
    check_file,
    ensure_can_modify,
    ensure_command,
    fill_audio_info,
    pack_dirname,
    real_filename,
    save_files,
    save_sf2s,
)


class Uploading(Cog, name=COG_UPLOADING):
    def __init__(self, bot: Bot, files: Dict[str, dict], sf2s: Dict[str, str]):
        self.bot = bot
        self.files = files
        self.sf2s = sf2s
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

        if pack := "pack" in cmd and cmd["pack"]:
            await ctx.send(f"`!{name}` is already a music pack.", delete_after=3)
            return

        # TODO handle situation when the file is currently playing
        # thus used by FFmpeg and may be locked

        dirname = pack_dirname(join(UPLOAD_PATH, f"{int(time())}_{name}"))
        old_filename = real_filename(cmd)
        old_basename = basename(cmd["filename"])
        new_filename = join(dirname, old_basename)
        replace(old_filename, new_filename)

        cmd["filename"] = basename(dirname)
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
        # to make lint happy
        filename = ""

        # helper variables for the process
        pack = False
        existing = False
        count = len(message.attachments)
        single = count == 1
        midi = False
        video = False

        saved_count = 0
        saved_name = ""
        invalid_count = 0
        invalid_name = ""

        # replace the command or add to a pack
        if name in self.files:
            cmd = self.files[name]
            pack = "pack" in cmd and cmd["pack"]
            midi = "midi" in cmd and cmd["midi"]
            video = "video" in cmd and cmd["video"]
            existing = True
            if not pack:
                # require permissions to replace a file
                await ensure_can_modify(ctx, cmd)
                # cannot replace single with multiple files
                if not single:
                    await ctx.send(f"Use `!pack {name}` first.", delete_after=3)
                    return

        # enable pack for multiple attachments
        pack = pack or not single

        if pack:
            if existing:
                # store to an existing pack
                dirname = real_filename(cmd)
            else:
                # create a new pack
                dirname = pack_dirname(join(UPLOAD_PATH, f"{int(time())}_{name}"))
        else:
            # single file - store directly to uploads
            dirname = UPLOAD_PATH

        # save all attachments
        for attachment in message.attachments:
            # create a safe filename
            filename = join(dirname, f"{int(time())}_{attachment.filename}")
            # save the attachment
            with open(filename, "wb") as f:
                await attachment.save(f)

            (audvid, archive, soundfont, midi1, video1) = check_file(filename)
            midi = midi or midi1
            video = video or video1

            # save all files from the archive
            if archive:
                if not pack:
                    # cannot replace single with multiple files
                    if existing:
                        await ctx.send(f"Use `!pack {name}` first.", delete_after=3)
                        unlink(filename)
                        return
                    # create a new pack
                    pack = True
                    dirname = pack_dirname(filename)
                # prepare a temporary directory
                dirname_tmp = f"{dirname}_tmp"
                if not isdir(dirname_tmp):
                    mkdir(dirname_tmp)
                # unpack the archive
                patoolib.extract_archive(filename, outdir=dirname_tmp)
                unlink(filename)
                # search for compatible files
                for path in Path(dirname_tmp).rglob("*"):
                    path = str(path)
                    filename = basename(path)
                    if not isfile(path):
                        continue

                    (audvid, archive, soundfont, midi1, video1) = check_file(path)
                    midi = midi or midi1
                    video = video or video1

                    if audvid:
                        saved_count += 1
                        saved_name = filename
                        filename = join(dirname, filename)
                        replace(path, filename)
                    # elif soundfont:
                    #     pass
                    else:
                        invalid_count += 1
                        invalid_name = filename
                # delete the temporary directory
                rmtree(dirname_tmp)

            # save audio/video files
            elif audvid:
                saved_count += 1
                saved_name = attachment.filename

            # save soundfonts only with single file
            elif soundfont and single and not existing:
                # find a soundfont with this name
                if name in self.sf2s:
                    sf2 = self.sf2s[name]
                    await ensure_can_modify(ctx, sf2)
                    # unlink to replace with another
                    unlink(real_filename(sf2))

                with open(filename, "rb") as f:
                    sf2 = Sf2File(f)

                sf2_name = (
                    sf2.raw.info[b"INAM"]
                    if b"INAM" in sf2.raw.info
                    else attachment.filename
                )
                if isinstance(sf2_name, bytes):
                    sf2_name = sf2_name.replace(b"\x00", b"").decode().strip()

                sf2 = {
                    "filename": basename(filename),
                    "help": sf2_name,
                    "author": {
                        "id": ctx.author.id,
                        "guild": ctx.guild.id,
                    },
                    "version": CMD_VERSION,
                }

                self.sf2s[name] = sf2
                save_sf2s(self.sf2s)
                await ctx.send(
                    f"Added **{sf2_name}**! Use `!sf <midi name> {name}` to apply the SoundFont.",
                    delete_after=10,
                )
                return

            # discard everything else
            else:
                invalid_count += 1
                invalid_name = attachment.filename
                unlink(filename)

        # raise an error if no files saved
        if not saved_count:
            await ctx.send(f"Unrecognized file: **{invalid_name}**", delete_after=3)
            # to be safe
            if isfile(filename):
                unlink(filename)
            return

        # delete the replaced file
        if not pack and existing:
            unlink(real_filename(cmd))

        # save cmd for new pack or replaced file
        if not pack or not existing:
            cmd = {
                "filename": basename(dirname if pack else filename),
                "help": f"Uploaded by {ctx.author}",
                "loop": True,
                "author": {
                    "id": ctx.author.id,
                    "guild": ctx.guild.id,
                },
                "version": CMD_VERSION,
            }

            fill_audio_info(cmd)

        # save filtering flags
        if pack:
            cmd["pack"] = True
        if midi:
            cmd["midi"] = True
            if "sf2s" not in cmd:
                cmd["sf2s"] = []
        if video:
            cmd["video"] = True
        self.files[name] = cmd

        # add the command to the music cog
        self.espionage.add_command(name)
        # save the command descriptors
        save_files(self.files)

        if pack and existing and saved_count == 1:
            text = f"Added **{saved_name}** to `!{name}`."
        elif saved_count > 1:
            text = f"Uploaded **{saved_count}** file(s) to `!{name}`."
        elif not existing:
            text = f"File **{saved_name}** uploaded as `!{name}`."
        else:
            text = f"Replaced `!{name}` with **{saved_name}**."

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
        filename = real_filename(cmd)
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
