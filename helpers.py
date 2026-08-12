import re
import io
from datetime import datetime, timedelta, timezone
from pyrogram.errors import UserNotParticipant
from config import IST_OFFSET_HOURS, IST_OFFSET_MINUTES

IST = timezone(timedelta(hours=IST_OFFSET_HOURS, minutes=IST_OFFSET_MINUTES))


# ==================== FORCE-SUB / ADMIN CHECKS ====================

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
        return False


async def is_channel_admin(client, user_id: int, channel_id: int) -> bool:
    """Check if a user is admin/owner/creator of the given channel."""
    try:
        member = await client.get_chat_member(channel_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def is_bot_admin_in_channel(client, channel_id: int) -> bool:
    try:
        me = await client.get_me()
        member = await client.get_chat_member(channel_id, me.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


# ==================== TIME (IST) ====================

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


# ==================== SMALL CAPS DM STYLING ====================

_SMALL_CAPS_MAP = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ", "g": "ɢ",
    "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ",
    "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "ꜱ", "t": "ᴛ", "u": "ᴜ",
    "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ", "z": "ᴢ",
}

_TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")


def _convert_plain_segment(text: str) -> str:
    """Converts a plain (non-HTML-tag) text segment to small-caps style,
    keeping the first letter of each word normal (matches the 'title-case' look)."""
    words = text.split(" ")
    out_words = []
    for w in words:
        if not w:
            out_words.append(w)
            continue
        first = w[0]
        rest = "".join(_SMALL_CAPS_MAP.get(ch.lower(), ch) for ch in w[1:])
        out_words.append(first + rest)
    return " ".join(out_words)


def small_caps(text: str) -> str:
    """
    Converts DM-facing text to small-caps style while leaving HTML tags
    (<b>, </b>, <code>, etc.) completely untouched so Telegram parsing still works.
    """
    parts = _TAG_SPLIT_RE.split(text)
    result = []
    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            result.append(part)
        else:
            result.append(_convert_plain_segment(part))
    return "".join(result)


# ==================== IMAGE PROCESSING (square pfp) ====================

async def crop_to_square_bytes(client, file_id: str, size: int = 512) -> bytes | None:
    """
    Downloads a Telegram photo by file_id, center-crops it to a square,
    resizes to `size`x`size`, and returns JPEG bytes. Returns None on failure.
    """
    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        downloaded = await client.download_media(file_id, in_memory=True)
        if downloaded is None:
            return None
        buf = downloaded
        buf.seek(0)

        img = Image.open(buf).convert("RGB")
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((size, size), Image.LANCZOS)

        out = io.BytesIO()
        out.name = "pfp.jpg"
        img.save(out, format="JPEG", quality=90)
        out.seek(0)
        return out.getvalue()
    except Exception:
        return None
