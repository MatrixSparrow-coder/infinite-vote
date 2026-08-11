import asyncio
import logging
from datetime import datetime, timezone

from database import get_all_active_giveaways, end_giveaway, get_top_participants
from helpers import format_ist

logger = logging.getLogger("Infinite.Scheduler")

CHECK_INTERVAL_SECONDS = 30

MEDALS = ["🥇", "🥈", "🥉"]


async def announce_results(client, giveaway: dict):
    channel_id = giveaway["channel_id"]
    giveaway_id = giveaway["giveaway_id"]

    top = await get_top_participants(giveaway_id, limit=10)

    if not top:
        text = "🏁 <b>Giveaway Ended!</b>\n\nNo participants joined this giveaway."
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


async def giveaway_scheduler_loop(client):
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
                    logger.info(f"Auto-ended giveaway {giveaway['giveaway_id']}")

        except Exception as e:
            logger.exception(f"Scheduler loop error: {e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
