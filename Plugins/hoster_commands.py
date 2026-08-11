from pyrogram import Client, filters
from pyrogram.types import Message

from database import get_active_giveaway_by_hoster, get_participant, increment_votes, \
    end_giveaway, get_giveaway
from config import OWNER_ID


async def resolve_giveaway_for_command(user_id: int):
    """
    Returns the giveaway a user is allowed to act on:
    - Normal hoster -> their own active giveaway
    - Owner (if in an /access session) -> that giveaway, handled separately in owner.py
    """
    return await get_active_giveaway_by_hoster(user_id)


@Client.on_message(filters.command("incr") & filters.private)
async def incr_cmd(client: Client, message: Message):
    from plugins.owner import get_effective_hoster_giveaway

    giveaway = await get_effective_hoster_giveaway(message.from_user.id)
    if not giveaway:
        await message.reply_text("❌ You don't have an active giveaway to manage.")
        return

    args = message.text.split()
    if len(args) != 3:
        await message.reply_text(
            "Usage: <code>/incr &lt;participant_id&gt; &lt;count&gt;</code>\n"
            "Example: <code>/incr 003 5</code>"
        )
        return

    participant_id, count_str = args[1], args[2]
    try:
        count = int(count_str)
    except ValueError:
        await message.reply_text("❌ Count must be a number.")
        return

    participant = await get_participant(giveaway["giveaway_id"], participant_id)
    if not participant:
        await message.reply_text(f"❌ No participant found with ID <code>{participant_id}</code>.")
        return

    new_total = await increment_votes(giveaway["giveaway_id"], participant_id, count)
    await message.reply_text(
        f"✅ Boosted <b>{participant['name']}</b> (#{participant_id}) by {count} votes.\n"
        f"🗳️ New total: {new_total}"
    )


@Client.on_message(filters.command("end") & filters.private)
async def end_cmd(client: Client, message: Message):
    from plugins.owner import get_effective_hoster_giveaway
    from scheduler import announce_results

    giveaway = await get_effective_hoster_giveaway(message.from_user.id)
    if not giveaway:
        await message.reply_text("❌ You don't have an active giveaway to end.")
        return

    await end_giveaway(giveaway["giveaway_id"])
    await announce_results(client, giveaway)
    await message.reply_text("🛑 Giveaway ended and results have been posted in the channel.")
