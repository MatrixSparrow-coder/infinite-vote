import io
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery

from config import OWNER_ID
from database import get_giveaway, get_all_participants, get_participant_count
from helpers import format_ist, small_caps


def _build_report_text(giveaway: dict, participants: list) -> str:
    lines = [
        "INFINITE — GIVEAWAY REPORT",
        "=" * 40,
        f"Giveaway ID   : {giveaway['giveaway_id']}",
        f"Channel       : {giveaway.get('channel_title', 'N/A')}",
        f"Hoster ID     : {giveaway['hoster_id']}",
        f"Start Time    : {format_ist(giveaway['start_time'])}",
        f"End Time      : {format_ist(giveaway['end_time'])}",
        f"Status        : {giveaway['status']}",
        f"Total joined  : {len(participants)}",
        "=" * 40,
        "",
        "PARTICIPANTS (sorted by votes):",
        "",
    ]

    if not participants:
        lines.append("(No participants)")
    else:
        for p in participants:
            lines.append(
                f"#{p['participant_id']}  |  {p['name']}  |  user_id: {p['user_id']}  |  votes: {p['votes_count']}"
            )

    return "\n".join(lines)


async def _send_report(client: Client, chat_id: int, giveaway: dict):
    giveaway_id = giveaway["giveaway_id"]

    if giveaway.get("cleaned"):
        # heavy data already deleted - fall back to the stored summary snapshot
        summary = giveaway.get("top10_summary", [])
        lines = [
            "INFINITE — GIVEAWAY REPORT (ARCHIVED SUMMARY)",
            "=" * 40,
            f"Giveaway ID   : {giveaway_id}",
            f"Channel       : {giveaway.get('channel_title', 'N/A')}",
            f"Total joined  : {giveaway.get('total_participants', 'N/A')}",
            f"Total votes   : {giveaway.get('total_votes', 'N/A')}",
            "",
            "Note: full participant list was already cleaned up after 4 days.",
            "Top 10 at the time of cleanup:",
            "",
        ]
        for p in summary:
            lines.append(f"#{p['participant_id']}  |  {p['name']}  |  votes: {p['votes_count']}")
        content = "\n".join(lines)
    else:
        participants = await get_all_participants(giveaway_id)
        content = _build_report_text(giveaway, participants)

    file_bytes = io.BytesIO(content.encode("utf-8"))
    file_bytes.name = f"giveaway_{giveaway_id}.txt"

    await client.send_document(chat_id, file_bytes, caption=f"📄 Report for giveaway {giveaway_id}")


@Client.on_callback_query(filters.regex(r"^download_"))
async def download_cb(client: Client, cq: CallbackQuery):
    if cq.data == "download_dismiss":
        await cq.answer()
        await cq.message.edit_text(small_caps("👍 Okay, the data will be auto-deleted in 4 days as scheduled."))
        return

    giveaway_id = cq.data.split("_", 1)[1]
    giveaway = await get_giveaway(giveaway_id)

    if not giveaway:
        await cq.answer("This giveaway's data is no longer available.", show_alert=True)
        return

    # only the hoster of this giveaway (or the owner) may download it
    if cq.from_user.id not in (giveaway["hoster_id"], OWNER_ID):
        await cq.answer("This isn't your giveaway.", show_alert=True)
        return

    await cq.answer("Preparing your report...")
    await _send_report(client, cq.from_user.id, giveaway)


@Client.on_callback_query(filters.regex(r"^viewparts_") & filters.user(OWNER_ID))
async def viewparts_cb(client: Client, cq: CallbackQuery):
    giveaway_id = cq.data.split("_", 1)[1]
    giveaway = await get_giveaway(giveaway_id)

    if not giveaway:
        await cq.answer("Giveaway not found.", show_alert=True)
        return

    await cq.answer("Preparing participant list...")

    count = await get_participant_count(giveaway_id)
    if count <= 20:
        participants = await get_all_participants(giveaway_id)
        if not participants:
            await client.send_message(cq.from_user.id, "👥 No participants yet.")
            return
        lines = [f"👥 <b>PARTICIPANTS</b> ({count})", ""]
        for p in participants:
            lines.append(
                f"🆔 {p['participant_id']} | {p['name']} | user_id: <code>{p['user_id']}</code> | 🗳️ {p['votes_count']}"
            )
        await client.send_message(cq.from_user.id, "\n".join(lines))
    else:
        # large list -> send as a file instead of flooding the chat
        await _send_report(client, cq.from_user.id, giveaway)
