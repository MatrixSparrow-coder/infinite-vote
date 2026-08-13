import asyncio
from pyrogram import Client, filters
from config import API_ID, API_HASH, BOT_TOKEN
from web import run_web_server

app = Client("test", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message(filters.command("start"))
async def start(client, message):
    print("GOT START!!!", flush=True)
    await message.reply_text("Test working!")

async def main():
    await app.start()
    print("Test bot started.", flush=True)
    await run_web_server()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())