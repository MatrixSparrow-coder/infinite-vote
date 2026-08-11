import asyncio
import logging

from pyrogram import Client

from config import API_ID, API_HASH, BOT_TOKEN
from web import run_web_server
from scheduler import giveaway_scheduler_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Infinite")

app = Client(
    "InfiniteBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="plugins"),
)


async def main():
    await app.start()
    logger.info("Infinite Bot started.")

    await run_web_server()
    logger.info("Health-check web server running.")

    # background loop that watches giveaways and auto-ends them at end_time
    asyncio.create_task(giveaway_scheduler_loop(app))

    await asyncio.Event().wait()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
