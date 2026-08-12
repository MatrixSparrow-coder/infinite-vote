import asyncio
import logging
from datetime import datetime, timezone

from database import (
    get_all_active_giveaways, end_giveaway, get_top_participants,
    get_giveaways_needing_reminder, mark_reminder_sent,
    get_giveaways_pending_cleanup, cleanup_giveaway_data,
)
from helpers import small_caps

logger = logging.getLogger("Infinite.Scheduler")

END_CHECK_INTERVAL_SECONDS = 30
REMINDER_CHECK_INTERVAL_SECONDS = 60
CLEANUP_CHECK_INTERVAL_SECONDS = 3600  # 1 hour

MEDALS = ["🥇", "🥈", "🥉"]


async def announce_results(client, giveaway: dict):
    channel_id = giveaway["channel_id"]
    giveaway_id = giveaway["giveaway_id"]

    top = await get_top_participants(giveaway_id, limit=10)

    if not top:
        text = "🏁 <b>GIVEAWAY ENDED</b>\n\nNo one participated this time."
    else:
        lines = ["🏆 <b>GIVEAWAY RESULTS — TOP 10</b> 🏆", ""]
        for i, p in enumerate(top):
            rank = i + 1
            prefix = MEDALS[i] if i < 3 else f"#{rank}"
            lines.append(f"{prefix}  <b>{p['name']}</b> — {p['votes_count']} votes")
        lines.append("")
        lines.append("🎉 Congratulations to the winner(s)!")
        text = "\n".join(lines)

    try:
        await client.send_message(channel_id, text)
    except Exception as e:
        logger.warning(f"Failed to announce results for giveaway {giveaway_id}: {e}")


async def notify_hoster_end(client, giveaway: dict):
    """DM the hoster after their giveaway ends, offering to download the full data before cleanup."""
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    hoster_id = giveaway["hoster_id"]
    giveaway_id = giveaway["giveaway_id"]

    text = small_caps(
        "🏁 <b>Your giveaway has ended!</b>\n\n"
        "Do you want to download the full details "
        "(participants, votes, results) before it's auto-deleted in "
        f"{4} days?"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Download Data", callback_data=f"download_{giveaway_id}")],
        [InlineKeyboardButton("❌ No, thanks", callback_data="download_dismiss")],
    ])

    try:
        await client.send_message(hoster_id, text, reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"Failed to DM hoster {hoster_id} for giveaway {giveaway_id}: {e}")


async def send_reminder(client, giveaway: dict):
    channel_id = giveaway["channel_id"]
    text = (
        "⏰ <b>ONLY 1 HOUR LEFT TO VOTE!</b>\n\n"
        "The giveaway is closing soon — get your last votes in now! 🔥"
    )
    try:
        await client.send_message(channel_id, text)
        await mark_reminder_sent(giveaway["giveaway_id"])
    except Exception as e:
        logger.warning(f"Failed to send reminder for giveaway {giveaway['giveaway_id']}: {e}")


async def giveaway_end_loop(client):
    """Continuously checks active giveaways and ends the ones past their end_time."""
    while True:
        try:
            active = await get_all_active_giveaways()
            now = datetime.now(timezone.utc)

            for giveaway in active:
                end_time = giveaway["end_time"]
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)

                if now >= end_time:
                    await end_giveaway(giveaway["giveaway_id"])
                    await announce_results(client, giveaway)
                    await notify_hoster_end(client, giveaway)
                    logger.info(f"Auto-ended giveaway {giveaway['giveaway_id']}")

        except Exception as e:
            logger.exception(f"End-loop error: {e}")

        await asyncio.sleep(END_CHECK_INTERVAL_SECONDS)


async def reminder_loop(client):
    """Sends a '1 hour left' reminder to the channel, once per giveaway."""
    while True:
        try:
            due = await get_giveaways_needing_reminder()
            for giveaway in due:
                await send_reminder(client, giveaway)
        except Exception as e:
            logger.exception(f"Reminder-loop error: {e}")

        await asyncio.sleep(REMINDER_CHECK_INTERVAL_SECONDS)


async def cleanup_loop(client):
    """Deletes heavy participants/votes data for giveaways ended more than 4 days ago."""
    while True:
        try:
            pending = await get_giveaways_pending_cleanup()
            for giveaway in pending:
                await cleanup_giveaway_data(giveaway["giveaway_id"])
                logger.info(f"Cleaned up giveaway {giveaway['giveaway_id']}")
        except Exception as e:
            logger.exception(f"Cleanup-loop error: {e}")

        await asyncio.sleep(CLEANUP_CHECK_INTERVAL_SECONDS)
