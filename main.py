import asyncio
import logging

from pyrogram import Client

from config import API_ID, API_HASH, BOT_TOKEN
from web import run_web_server
from scheduler import giveaway_end_loop, reminder_loop, cleanup_loop

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

    asyncio.create_task(giveaway_end_loop(app))
    asyncio.create_task(reminder_loop(app))
    asyncio.create_task(cleanup_loop(app))
    logger.info("Background schedulers running (end/reminder/cleanup).")

    await asyncio.Event().wait()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
