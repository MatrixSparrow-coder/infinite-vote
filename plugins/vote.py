import re
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import (
    get_giveaway, get_participant, get_vote, cast_vote, remove_vote,
    increment_votes, is_banned,
)
from helpers import is_subscribed


@Client.on_callback_query(filters.regex(r"^vote_"))
async def vote_cb(client: Client, cq: CallbackQuery):
    _, giveaway_id, participant_id = cq.data.split("_", 2)
    voter_id = cq.from_user.id

    if await is_banned(voter_id):
        await cq.answer("You are banned from using this bot.", show_alert=True)
        return

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

    participant = await get_participant(giveaway_id, participant_id)
    if not participant:
        await cq.answer("This participant no longer exists.", show_alert=True)
        return

    existing_vote = await get_vote(giveaway_id, voter_id)

    if existing_vote and existing_vote["participant_id"] == participant_id:
        # ---- toggle OFF: clicking the same participant's vote again removes it ----
        await remove_vote(giveaway_id, voter_id)
        new_count = await increment_votes(giveaway_id, participant_id, -1)
        await _update_post(cq, giveaway_id, participant_id, new_count)
        await cq.answer("🔄 Vote removed.")
        return

    if existing_vote and existing_vote["participant_id"] != participant_id:
        # ---- blocked: must remove existing vote elsewhere first ----
        other = await get_participant(giveaway_id, existing_vote["participant_id"])
        other_name = other["name"] if other else "another participant"
        await cq.answer(
            f"You've already voted for {other_name}! Remove your vote there first before voting elsewhere.",
            show_alert=True
        )
        return

    # ---- fresh vote ----
    await cast_vote(giveaway_id, voter_id, participant_id)
    new_count = await increment_votes(giveaway_id, participant_id, 1)
    await _update_post(cq, giveaway_id, participant_id, new_count)
    await cq.answer("✅ Vote counted! Thanks for voting 🔥")


async def _update_post(cq: CallbackQuery, giveaway_id: str, participant_id: str, new_count: int):
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
        pass  # editing might fail if content is unchanged - safe to ignore


def _replace_vote_count(text: str, new_count: int) -> str:
    return re.sub(r"Total Votes:</b> \d+", f"Total Votes:</b> {new_count}", text)
