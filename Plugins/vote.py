from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_giveaway, get_participant, has_voted, cast_vote, increment_votes
from helpers import is_subscribed


@Client.on_callback_query(filters.regex(r"^vote_"))
async def vote_cb(client: Client, cq: CallbackQuery):
    _, giveaway_id, participant_id = cq.data.split("_", 2)
    voter_id = cq.from_user.id

    giveaway = await get_giveaway(giveaway_id)
    if not giveaway or giveaway["status"] != "active":
        await cq.answer("This giveaway has ended.", show_alert=True)
        return

    channel_id = giveaway["channel_id"]

    if not await is_subscribed(client, voter_id, channel_id):
        await cq.answer(
            "⚠️ Please join the channel first to be eligible for voting!",
            show_alert=True
        )
        return

    if await has_voted(giveaway_id, voter_id):
        await cq.answer("You've already used your vote in this giveaway!", show_alert=True)
        return

    participant = await get_participant(giveaway_id, participant_id)
    if not participant:
        await cq.answer("This participant no longer exists.", show_alert=True)
        return

    await cast_vote(giveaway_id, voter_id, participant_id)
    new_count = await increment_votes(giveaway_id, participant_id, 1)

    # update the button + caption/text live
    new_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔥 Vote ({new_count})", callback_data=f"vote_{giveaway_id}_{participant_id}")]
    ])

    try:
        if cq.message.photo:
            new_caption = _replace_vote_count(cq.message.caption or "", new_count)
            await cq.message.edit_caption(new_caption, reply_markup=new_keyboard)
        else:
            new_text = _replace_vote_count(cq.message.text or "", new_count)
            await cq.message.edit_text(new_text, reply_markup=new_keyboard)
    except Exception:
        # editing might fail (e.g. message unchanged), safe to ignore
        pass

    await cq.answer("✅ Vote counted! Thanks for voting 🔥")


def _replace_vote_count(text: str, new_count: int) -> str:
    import re
    return re.sub(r"Total Votes:</b> \d+", f"Total Votes:</b> {new_count}", text)
