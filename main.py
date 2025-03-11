import discord
import os
import logging
import asyncio
from bot import AndreiBot
import asyncpg
from utils import make_activity
from dotenv import load_dotenv
load_dotenv()


async def main() -> None:
    os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
    os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
    os.environ["JISHAKU_HIDE"] = "True"

    discord.utils.setup_logging(level=logging.INFO)
    db_path = os.getenv("db")
    tk = os.getenv("token")
    
    async with asyncpg.create_pool(db_path) as pool:
        default_prefix = "."
        activity, status = await make_activity(pool)

        bot = AndreiBot(default_prefix, activity, status)
        bot.pool = pool

        while True:
            try:
                async with bot:
                    await bot.start(tk, reconnect=True)
            except Exception as e:
                log = logging.getLogger(__name__)
                log.critical("FAILED TO LOGIN %s", str(e))
                await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
