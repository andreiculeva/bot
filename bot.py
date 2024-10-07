import discord
from discord.ext import commands
import pathlib
import aiohttp
import asyncio
import asyncpg
from utils import PaginatedHelpCommand
import lavalink

ANDREI2_ID = 605398335691554827
ANDREI_ID = 393033826474917889


class AndreiBot(commands.Bot):
    def __init__(
        self,
        default_prefix: str,
        activity: discord.Activity,
        status: discord.Status,
        **options,
    ) -> None:
        super().__init__(
            command_prefix=get_prefix,
            help_command=PaginatedHelpCommand(),
            intents=discord.Intents.all(),
            case_insensitive=True,
            status=status,
            activity=activity,
            owner_ids=(ANDREI_ID, ANDREI2_ID),
            max_messages=100000000,
            **options,
        )
        self.default_prefix = default_prefix
        self.deleted_files = {}  # message_id : (filebytes, filename)
        self.case_insensitive = True
        self.launch_time = discord.utils.utcnow()
        self.prefixes = {}
        self.pool: asyncpg.Pool
        self.log_channel: discord.TextChannel

    async def on_ready(self):
        self.log_channel = self.get_channel(865124093999972362)

    async def update_prefixes(self) -> None:
        prefixes = await self.pool.fetch("SELECT * FROM server_prefixes")
        for server_id, prefix in prefixes:
            self.prefixes[server_id] = prefix

    async def setup_hook(self) -> None:
        self.session = aiohttp.ClientSession()
        self.lavalink = lavalink.Client(self.user.id)
        self.lavalink.add_node("lavalink-legacy.jompo.cloud", 2333, "jompo", "eu")
        await self.update_prefixes()
        await self.load_extension("jishaku")
        for file in pathlib.Path("cogs").glob("**/[!_]*.py"):
            ext = ".".join(file.parts).removesuffix(".py")
            await self.load_extension(ext)


async def get_prefix(bot: AndreiBot, message: discord.Message) -> list[str]:
    # return "="
    prefixes = [
        f"<@!{bot.user.id}> ",
        f"<@{bot.user.id}> ",
        f"<@!{bot.user.id}>",
        f"<@{bot.user.id}>",
    ]  # note the space at the end

    if message.guild:
        prefixes.append(bot.prefixes.get(message.guild.id, bot.default_prefix))
    else:
        prefixes.append(bot.default_prefix)
        prefixes += ["", " "]
    return prefixes
