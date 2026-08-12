import logging
from pyrogram import Client

from database import (
    get_giveaway_by_channel, get_vote, remove_vote, increment_votes,
    get_participant, delete_giveaway_completely,
)

logger = logging.getLogger("Infinite.ChatEvents")

LEFT_STATUSES = ("left", "kicked", "banned")
_bot_id_cache: dict[str, int] = {}


async def _get_bot_id(client: Client) -> int:
    if "id" not in _bot_id_cache:
        me = await client.get_me()
        _bot_id_cache["id"] = me.id
    return _bot_id_cache["id"]


@Client.on_chat_member_updated()
async def on_chat_member_updated(client: Client, update):
    try:
        new_member = update.new_chat_member
        if not new_member or not new_member.user:
            return

        user_id = new_member.user.id
        new_status = new_member.status
        channel_id = update.chat.id

        bot_id = await _get_bot_id(client)

        # ---- Case 1: the bot itself was removed/demoted from the channel ----
        if user_id == bot_id:
            if new_status in LEFT_STATUSES or new_status == "restricted":
                giveaway = await get_giveaway_by_channel(channel_id)
                if giveaway:
                    hoster_id = giveaway["hoster_id"]
                    giveaway_id = giveaway["giveaway_id"]
                    await delete_giveaway_completely(giveaway_id)
                    logger.info(f"Bot removed from channel {channel_id}, deleted giveaway {giveaway_id}")
                    try:
                        await client.send_message(
                            hoster_id,
                            "⚠️ <b>Your giveaway was cancelled.</b>\n\n"
                            "The bot lost admin access to your channel, so the giveaway "
                            "and all its data have been removed."
                        )
                    except Exception:
                        pass
            return

        # ---- Case 2: a regular user left the channel - check if they had a vote ----
        if new_status in LEFT_STATUSES:
            giveaway = await get_giveaway_by_channel(channel_id)
            if not giveaway:
                return

            giveaway_id = giveaway["giveaway_id"]
            vote = await get_vote(giveaway_id, user_id)
            if not vote:
                return  # they never voted, nothing to do

            participant_id = vote["participant_id"]
            await remove_vote(giveaway_id, user_id)
            new_count = await increment_votes(giveaway_id, participant_id, -1)

            participant = await get_participant(giveaway_id, participant_id)
            if not participant:
                return

            voter_name = new_member.user.first_name or "A voter"
            voter_link = f'<a href="tg://user?id={user_id}">{voter_name}</a>'
            participant_link = f'<a href="tg://user?id={participant["user_id"]}">{participant["name"]}</a>'

            text = (
                "📉 <b>VOTE REMOVED</b>\n"
                "━━━━━━━━━━━━━━━\n"
                f"👤 {voter_link} has left the channel\n"
                f"🎯 Participant: {participant_link}\n"
                f"🗳️ Votes: <s>{new_count + 1}</s> → <b>{new_count}</b>\n"
                "━━━━━━━━━━━━━━━"
            )

            try:
                await client.send_message(channel_id, text)
            except Exception as e:
                logger.warning(f"Failed to post leave-announcement: {e}")

            # also live-update the participant's post button
            try:
                if participant.get("post_message_id"):
                    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    new_keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(f"🔥 Vote ({new_count})",
                                               callback_data=f"vote_{giveaway_id}_{participant_id}")]
                    ])
                    msg = await client.get_messages(channel_id, participant["post_message_id"])
                    if msg.photo:
                        import re
                        new_caption = re.sub(r"Total Votes:</b> \d+", f"Total Votes:</b> {new_count}", msg.caption or "")
                        await client.edit_message_caption(channel_id, msg.id, new_caption, reply_markup=new_keyboard)
                    else:
                        import re
                        new_text = re.sub(r"Total Votes:</b> \d+", f"Total Votes:</b> {new_count}", msg.text or "")
                        await client.edit_message_text(channel_id, msg.id, new_text, reply_markup=new_keyboard)
            except Exception as e:
                logger.warning(f"Failed to live-update post after leave: {e}")

    except Exception as e:
        logger.exception(f"chat_member_updated handler error: {e}")
