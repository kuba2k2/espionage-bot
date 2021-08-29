from typing import Dict

from discord.ext import commands
from discord.ext.commands import Bot, Cog, Context

from settings import COG_ESPIONAGE, COG_MUSIC, RANDOM_FILE
from utils import ensure_voice


class Music(Cog, name=COG_MUSIC):
    def __init__(self, bot: Bot, files: Dict[str, dict]):
        self.bot = bot
        self.files = files
        self.espionage = self.bot.get_cog(COG_ESPIONAGE)

    @commands.command()
    @commands.guild_only()
    @commands.before_invoke(ensure_voice)
    async def random(self, ctx: Context):
        """Randomly play files from the global directory."""
        await self.espionage.play(
            ctx.voice_client.channel,
            file=RANDOM_FILE,
            loop=True,
        )
