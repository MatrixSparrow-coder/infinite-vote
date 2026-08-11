from datetime import datetime, timedelta, timezone
from pyrogram.errors import UserNotParticipant
from config import IST_OFFSET_HOURS, IST_OFFSET_MINUTES

IST = timezone(timedelta(hours=IST_OFFSET_HOURS, minutes=IST_OFFSET_MINUTES))


async def is_subscribed(client, user_id: int, channel_id: int) -> bool:
    """Check if a user has joined the given channel. True if joined, False otherwise."""
    try:
        member = await client.get_chat_member(channel_id, user_id)
        if member.status in ("left", "kicked", "banned"):
            return False
        return True
    except UserNotParticipant:
        return False
    except Exception:
        # If bot can't check (e.g. not admin, wrong id), fail safe -> treat as not joined
        return False


async def is_channel_admin(client, user_id: int, channel_id: int) -> bool:
    """Check if a user is admin/owner/creator of the given channel."""
    try:
        member = await client.get_chat_member(channel_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


def now_ist() -> datetime:
    return datetime.now(IST)


def parse_ist_datetime(text: str) -> datetime | None:
    """
    Parse a datetime string like '2026-08-15 20:00' or '15-08-2026 20:00' as IST.
    Returns a timezone-aware datetime in IST, or None if parsing fails.
    """
    text = text.strip()
    formats = [
        "%Y-%m-%d %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y/%m/%d %H:%M",
        "%d/%m/%Y %H:%M",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.replace(tzinfo=IST)
        except ValueError:
            continue
    return None


def format_ist(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")


def to_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc)
