from pyrogram import Client, filters
from pyrogram.types import Message

from config import OWNER_ID
from database import get_giveaway, get_active_giveaway_by_hoster, \
    set_owner_session, clear_owner_session, get_owner_session


async def notify_owner_new_giveaway(client: Client, giveaway_id: str, hoster_id: int, channel_title: str):
    """Silently DMs the owner whenever a new giveaway is created. Hoster is never aware of this."""
    if not OWNER_ID:
        return
    try:
        await client.send_message(
            OWNER_ID,
            f"🆕 <b>New giveaway started</b>\n\n"
            f"🆔 ID: <code>{giveaway_id}</code>\n"
            f"👤 Hoster: <code>{hoster_id}</code>\n"
            f"📢 Channel: {channel_title}\n\n"
            f"Use <code>/access {giveaway_id}</code> to manage it."
        )
    except Exception:
        pass  # owner may not have started the bot yet


async def get_effective_hoster_giveaway(user_id: int):
    """
    Used by /incr and /end.
    - If the user is the OWNER and currently has an active /access session, that
      giveaway is used instead of looking up their own hosted giveaway.
    - Otherwise, falls back to the user's own active giveaway.
    """
    if user_id == OWNER_ID:
        session_giveaway_id = await get_owner_session()
        if session_giveaway_id:
            return await get_giveaway(session_giveaway_id)

    return await get_active_giveaway_by_hoster(user_id)


@Client.on_message(filters.command("access") & filters.private & filters.user(OWNER_ID))
async def access_cmd(client: Client, message: Message):
    if len(message.command) != 2:
        await message.reply_text("Usage: <code>/access &lt;giveaway_id&gt;</code>")
        return

    giveaway_id = message.command[1]
    giveaway = await get_giveaway(giveaway_id)
    if not giveaway:
        await message.reply_text("❌ No giveaway found with that ID.")
        return

    await set_owner_session(giveaway_id)
    await message.reply_text(
        f"🔓 Access granted to giveaway <code>{giveaway_id}</code>.\n"
        f"All hoster commands (/incr, /end) now apply to this giveaway.\n"
        f"Use /exit to leave this session."
    )


@Client.on_message(filters.command("exit") & filters.private & filters.user(OWNER_ID))
async def exit_cmd(client: Client, message: Message):
    await clear_owner_session()
    await message.reply_text("🔒 Exited access session. Back to normal mode.")
