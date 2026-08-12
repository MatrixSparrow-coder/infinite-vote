from pyrogram import Client, filters
from pyrogram.types import Message

from database import (
    get_active_giveaway_by_hoster, get_participant, increment_votes,
    end_giveaway, cancel_giveaway, get_participant_count, get_hoster_giveaways,
    is_banned,
)
from helpers import small_caps, format_ist


@Client.on_message(filters.command("incr") & filters.private)
async def incr_cmd(client: Client, message: Message):
    from plugins.owner import get_effective_hoster_giveaway

    if await is_banned(message.from_user.id):
        await message.reply_text(small_caps("🚫 <b>You are banned from using this bot.</b>"))
        return

    giveaway = await get_effective_hoster_giveaway(message.from_user.id)
    if not giveaway:
        await message.reply_text(small_caps("❌ You don't have an active giveaway to manage."))
        return

    args = message.text.split()
    if len(args) != 3:
        await message.reply_text(small_caps(
            "Usage: <code>/incr &lt;participant_id&gt; &lt;count&gt;</code>\n"
            "Example: <code>/incr 003 5</code>"
        ))
        return

    participant_id, count_str = args[1], args[2]
    try:
        count = int(count_str)
    except ValueError:
        await message.reply_text(small_caps("❌ Count must be a number."))
        return

    participant = await get_participant(giveaway["giveaway_id"], participant_id)
    if not participant:
        await message.reply_text(small_caps(f"❌ No participant found with ID <code>{participant_id}</code>."))
        return

    new_total = await increment_votes(giveaway["giveaway_id"], participant_id, count)
    await message.reply_text(small_caps(
        f"✅ Boosted <b>{participant['name']}</b> (#{participant_id}) by {count} votes.\n"
        f"🗳️ New total: {new_total}"
    ))


@Client.on_message(filters.command("end") & filters.private)
async def end_cmd(client: Client, message: Message):
    from plugins.owner import get_effective_hoster_giveaway
    from scheduler import announce_results, notify_hoster_end

    if await is_banned(message.from_user.id):
        await message.reply_text(small_caps("🚫 <b>You are banned from using this bot.</b>"))
        return

    giveaway = await get_effective_hoster_giveaway(message.from_user.id)
    if not giveaway:
        await message.reply_text(small_caps("❌ You don't have an active giveaway to end."))
        return

    await end_giveaway(giveaway["giveaway_id"])
    await announce_results(client, giveaway)
    await notify_hoster_end(client, giveaway)
    await message.reply_text(small_caps("🛑 Giveaway ended and results have been posted in the channel."))


@Client.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client: Client, message: Message):
    user_id = message.from_user.id

    if await is_banned(user_id):
        await message.reply_text(small_caps("🚫 <b>You are banned from using this bot.</b>"))
        return

    giveaway = await get_active_giveaway_by_hoster(user_id)
    if not giveaway:
        await message.reply_text(small_caps("❌ You don't have an active giveaway to cancel."))
        return

    count = await get_participant_count(giveaway["giveaway_id"])
    if count > 0:
        await message.reply_text(small_caps(
            f"⚠️ You already have {count} participant(s) in this giveaway — it can no longer be cancelled.\n"
            "Use /end instead to close it and announce results."
        ))
        return

    await cancel_giveaway(giveaway["giveaway_id"])
    await message.reply_text(small_caps("🚫 Giveaway cancelled successfully. You can start a new one anytime with /host."))


@Client.on_message(filters.command("mystats") & filters.private)
async def mystats_cmd(client: Client, message: Message):
    user_id = message.from_user.id

    if await is_banned(user_id):
        await message.reply_text(small_caps("🚫 <b>You are banned from using this bot.</b>"))
        return

    giveaways = await get_hoster_giveaways(user_id, limit=15)
    if not giveaways:
        await message.reply_text(small_caps("📊 You haven't hosted any giveaways yet. Use /host to start one!"))
        return

    lines = [small_caps(f"📊 <b>Your Hosting History</b> ({len(giveaways)} shown)"), ""]
    for g in giveaways:
        status_emoji = {"active": "🟢", "ended": "🔴", "cancelled": "⚪"}.get(g["status"], "•")
        total_p = g.get("total_participants")
        if total_p is None:
            total_p = await get_participant_count(g["giveaway_id"])
        lines.append(
            f"{status_emoji} <code>{g['giveaway_id']}</code> — {g['channel_title']}\n"
            f"   👥 {total_p} participants | {g['status'].upper()}"
        )

    await message.reply_text("\n".join(lines))
