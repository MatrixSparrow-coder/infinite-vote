from aiohttp import web
from config import PORT


async def handle_root(request):
    return web.Response(text="Infinite Bot is alive!")


async def run_web_server():
    app = web.Application()
    app.router.add_get("/", handle_root)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
