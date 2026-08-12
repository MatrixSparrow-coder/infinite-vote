import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message

from config import OWNER_ID
from database import (
    is_admin, add_admin, remove_admin, is_banned, ban_user, unban_user,
    get_bot_stats, set_start_pic, get_all_user_ids,
)
from helpers import small_caps

# in-memory state for multi-step admin flows: {user_id: {"action": "startpic" | "broadcast"}}
admin_states: dict[int, dict] = {}


def _parse_target_id(message: Message) -> int | None:
    args = message.text.split()
    if len(args) != 2:
        return None
    try:
        return int(args[1])
    except ValueError:
        return None


@Client.on_message(filters.command("addadmin") & filters.private & filters.user(OWNER_ID))
async def addadmin_cmd(client: Client, message: Message):
    target = _parse_target_id(message)
    if target is None:
        await message.reply_text("Usage: <code>/addadmin &lt;user_id&gt;</code>")
        return
    await add_admin(target)
    await message.reply_text(f"✅ <code>{target}</code> is now an admin.")


@Client.on_message(filters.command("removeadmin") & filters.private & filters.user(OWNER_ID))
async def removeadmin_cmd(client: Client, message: Message):
    target = _parse_target_id(message)
    if target is None:
        await message.reply_text("Usage: <code>/removeadmin &lt;user_id&gt;</code>")
        return
    await remove_admin(target)
    await message.reply_text(f"✅ <code>{target}</code> is no longer an admin.")


@Client.on_message(filters.command("stats") & filters.private)
async def stats_cmd(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return  # silently ignore for non-admins

    stats = await get_bot_stats()
    await message.reply_text(
        "📊 <b>BOT STATS</b>\n\n"
        f"👥 Total bot users: {stats['total_users']}\n"
        f"🏆 Unique hosters: {stats['total_hosters']}\n"
        f"🎯 Total giveaways: {stats['total_giveaways']} ({stats['active_giveaways']} active)\n"
        f"🙋 Total participants (all-time): {stats['total_participants']}\n"
        f"🗳️ Total votes cast (all-time): {stats['total_votes']}"
    )


@Client.on_message(filters.command("ban") & filters.private)
async def ban_cmd(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return

    target = _parse_target_id(message)
    if target is None:
        await message.reply_text("Usage: <code>/ban &lt;user_id&gt;</code>")
        return

    if target == OWNER_ID:
        await message.reply_text("❌ Can't ban the owner.")
        return

    await ban_user(target)
    await message.reply_text(f"🚫 <code>{target}</code> has been banned from using the bot.")


@Client.on_message(filters.command("unban") & filters.private)
async def unban_cmd(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return

    target = _parse_target_id(message)
    if target is None:
        await message.reply_text("Usage: <code>/unban &lt;user_id&gt;</code>")
        return

    await unban_user(target)
    await message.reply_text(f"✅ <code>{target}</code> has been unbanned.")


@Client.on_message(filters.command("startpic") & filters.private)
async def startpic_cmd(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return

    admin_states[message.from_user.id] = {"action": "startpic"}
    await message.reply_text("📸 Send me the image you want to set as the /start banner.")


async def handle_startpic_photo(client: Client, message: Message):
    """Called by router.py when an admin is mid startpic-upload flow and sends a photo."""
    await set_start_pic(message.photo.file_id)
    await message.reply_text("✅ Start banner image updated! It'll now show on every /start.")
    admin_states.pop(message.from_user.id, None)


@Client.on_message(filters.command("broadcast") & filters.private)
async def broadcast_cmd(client: Client, message: Message):
    if not await is_admin(message.from_user.id):
        return

    admin_states[message.from_user.id] = {"action": "broadcast"}
    await message.reply_text(
        "📢 Send me the message you want to broadcast to all bot users.\n"
        "(Text, photo, or any message type — it'll be copied as-is.)"
    )


async def handle_broadcast_message(client: Client, message: Message):
    """Called by router.py when an admin is mid broadcast flow and sends the content to broadcast."""
    admin_states.pop(message.from_user.id, None)

    user_ids = await get_all_user_ids()
    status_msg = await message.reply_text(f"📤 Broadcasting to {len(user_ids)} users, this may take a while...")

    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await message.copy(uid)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # ~20 messages/sec, safely under Telegram's rate limits

    await status_msg.edit_text(f"✅ Broadcast complete!\n\nSent: {sent}\nFailed: {failed}")
