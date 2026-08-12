from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from datetime import datetime, timezone, timedelta
import uuid

from config import MONGO_URI, DB_NAME, OWNER_ID

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

giveaways_col = db["giveaways"]
participants_col = db["participants"]
votes_col = db["votes"]
counters_col = db["counters"]          # atomic per-giveaway participant ID counter
owner_sessions_col = db["owner_sessions"]
users_col = db["users"]                # everyone who ever /start'd the bot (for broadcast)
admins_col = db["admins"]              # bot-wide admins (not hosters)
bans_col = db["bans"]                  # banned user ids
settings_col = db["settings"]          # single-doc settings like start_pic

CLEANUP_AFTER_DAYS = 4
REMINDER_BEFORE_MINUTES = 60


# ==================== USERS (for broadcast) ====================

async def track_user(user_id: int):
    await users_col.update_one(
        {"_id": user_id},
        {"$setOnInsert": {"first_seen": datetime.now(timezone.utc)}},
        upsert=True
    )


async def get_all_user_ids() -> list[int]:
    cursor = users_col.find({}, {"_id": 1})
    return [doc["_id"] async for doc in cursor]


async def get_total_user_count() -> int:
    return await users_col.count_documents({})


# ==================== ADMINS ====================

async def is_admin(user_id: int) -> bool:
    if user_id == OWNER_ID:
        return True
    doc = await admins_col.find_one({"_id": user_id})
    return doc is not None


async def add_admin(user_id: int):
    await admins_col.update_one(
        {"_id": user_id},
        {"$set": {"added_at": datetime.now(timezone.utc)}},
        upsert=True
    )


async def remove_admin(user_id: int):
    await admins_col.delete_one({"_id": user_id})


async def list_admins() -> list[int]:
    cursor = admins_col.find({}, {"_id": 1})
    return [doc["_id"] async for doc in cursor]


# ==================== BANS ====================

async def is_banned(user_id: int) -> bool:
    doc = await bans_col.find_one({"_id": user_id})
    return doc is not None


async def ban_user(user_id: int):
    await bans_col.update_one(
        {"_id": user_id},
        {"$set": {"banned_at": datetime.now(timezone.utc)}},
        upsert=True
    )


async def unban_user(user_id: int):
    await bans_col.delete_one({"_id": user_id})


# ==================== SETTINGS (start pic, etc.) ====================

async def set_start_pic(file_id: str):
    await settings_col.update_one(
        {"_id": "start_pic"},
        {"$set": {"file_id": file_id}},
        upsert=True
    )


async def get_start_pic() -> str | None:
    doc = await settings_col.find_one({"_id": "start_pic"})
    return doc["file_id"] if doc else None


# ==================== GIVEAWAYS ====================

async def create_giveaway(hoster_id: int, channel_id: int, channel_title: str,
                           start_time: datetime, end_time: datetime) -> str:
    giveaway_id = uuid.uuid4().hex[:8]
    await giveaways_col.insert_one({
        "giveaway_id": giveaway_id,
        "hoster_id": hoster_id,
        "channel_id": channel_id,
        "channel_title": channel_title,
        "start_time": start_time,
        "end_time": end_time,
        "status": "active",  # active | ended | cancelled
        "created_at": datetime.now(timezone.utc),
        "ended_at": None,
        "reminder_sent": False,
        "cleaned": False,
    })
    return giveaway_id


async def get_active_giveaway_by_hoster(hoster_id: int):
    return await giveaways_col.find_one({"hoster_id": hoster_id, "status": "active"})


async def get_giveaway(giveaway_id: str):
    return await giveaways_col.find_one({"giveaway_id": giveaway_id})


async def get_giveaway_by_channel(channel_id: int):
    return await giveaways_col.find_one({"channel_id": channel_id, "status": "active"})


async def end_giveaway(giveaway_id: str):
    await giveaways_col.update_one(
        {"giveaway_id": giveaway_id},
        {"$set": {"status": "ended", "ended_at": datetime.now(timezone.utc)}}
    )


async def cancel_giveaway(giveaway_id: str):
    """Only allowed by the caller if the giveaway has 0 participants."""
    await giveaways_col.update_one(
        {"giveaway_id": giveaway_id},
        {"$set": {"status": "cancelled", "ended_at": datetime.now(timezone.utc)}}
    )


async def delete_giveaway_completely(giveaway_id: str):
    """Used when the bot is removed as admin from the hoster's channel - wipe everything, no trace."""
    await giveaways_col.delete_one({"giveaway_id": giveaway_id})
    await participants_col.delete_many({"giveaway_id": giveaway_id})
    await votes_col.delete_many({"giveaway_id": giveaway_id})
    await counters_col.delete_one({"_id": giveaway_id})


async def get_all_active_giveaways():
    cursor = giveaways_col.find({"status": "active"})
    return [g async for g in cursor]


async def get_giveaways_needing_reminder():
    now = datetime.now(timezone.utc)
    window_end = now + timedelta(minutes=REMINDER_BEFORE_MINUTES)
    cursor = giveaways_col.find({
        "status": "active",
        "reminder_sent": False,
        "end_time": {"$gt": now, "$lte": window_end},
    })
    return [g async for g in cursor]


async def mark_reminder_sent(giveaway_id: str):
    await giveaways_col.update_one(
        {"giveaway_id": giveaway_id},
        {"$set": {"reminder_sent": True}}
    )


async def get_giveaways_pending_cleanup():
    cutoff = datetime.now(timezone.utc) - timedelta(days=CLEANUP_AFTER_DAYS)
    cursor = giveaways_col.find({
        "status": {"$in": ["ended", "cancelled"]},
        "cleaned": {"$ne": True},
        "ended_at": {"$ne": None, "$lte": cutoff},
    })
    return [g async for g in cursor]


async def cleanup_giveaway_data(giveaway_id: str):
    """Deletes heavy per-giveaway data (participants, votes) but keeps a summary on the giveaway doc."""
    top = await get_top_participants(giveaway_id, limit=10)
    total_participants = await participants_col.count_documents({"giveaway_id": giveaway_id})
    total_votes = await votes_col.count_documents({"giveaway_id": giveaway_id})

    summary = [
        {"name": p["name"], "participant_id": p["participant_id"], "votes_count": p["votes_count"]}
        for p in top
    ]

    await giveaways_col.update_one(
        {"giveaway_id": giveaway_id},
        {"$set": {
            "cleaned": True,
            "total_participants": total_participants,
            "total_votes": total_votes,
            "top10_summary": summary,
        }}
    )
    await participants_col.delete_many({"giveaway_id": giveaway_id})
    await votes_col.delete_many({"giveaway_id": giveaway_id})
    await counters_col.delete_one({"_id": giveaway_id})


async def get_hoster_giveaways(hoster_id: int, limit: int = 20):
    cursor = giveaways_col.find({"hoster_id": hoster_id}).sort("created_at", -1).limit(limit)
    return [g async for g in cursor]


async def get_hoster_giveaway_count(hoster_id: int) -> int:
    return await giveaways_col.count_documents({"hoster_id": hoster_id})


async def get_bot_stats() -> dict:
    total_giveaways = await giveaways_col.count_documents({})
    active_giveaways = await giveaways_col.count_documents({"status": "active"})
    total_hosters = len(await giveaways_col.distinct("hoster_id"))
    total_users = await get_total_user_count()

    # sum participants/votes across live (uncleaned) giveaways + cleaned summaries
    live_participants = await participants_col.count_documents({})
    live_votes = await votes_col.count_documents({})

    cleaned_cursor = giveaways_col.find({"cleaned": True}, {"total_participants": 1, "total_votes": 1})
    cleaned_participants = 0
    cleaned_votes = 0
    async for g in cleaned_cursor:
        cleaned_participants += g.get("total_participants", 0)
        cleaned_votes += g.get("total_votes", 0)

    return {
        "total_giveaways": total_giveaways,
        "active_giveaways": active_giveaways,
        "total_hosters": total_hosters,
        "total_users": total_users,
        "total_participants": live_participants + cleaned_participants,
        "total_votes": live_votes + cleaned_votes,
    }


# ==================== PARTICIPANTS ====================

async def get_next_participant_seq(giveaway_id: str) -> int:
    """Atomic counter - avoids duplicate participant IDs under concurrent participation."""
    result = await counters_col.find_one_and_update(
        {"_id": giveaway_id},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result["seq"]


async def add_participant(giveaway_id: str, user_id: int, name: str,
                           photo_file_id: str | None, caption: str | None) -> str:
    seq = await get_next_participant_seq(giveaway_id)
    participant_id = f"{seq:03d}"

    await participants_col.insert_one({
        "participant_id": participant_id,
        "giveaway_id": giveaway_id,
        "user_id": user_id,
        "name": name,
        "photo_file_id": photo_file_id,
        "caption": caption,
        "votes_count": 0,
        "post_message_id": None,
        "joined_at": datetime.now(timezone.utc),
    })
    return participant_id


async def set_participant_post_message(giveaway_id: str, participant_id: str, message_id: int):
    await participants_col.update_one(
        {"giveaway_id": giveaway_id, "participant_id": participant_id},
        {"$set": {"post_message_id": message_id}}
    )


async def get_participant(giveaway_id: str, participant_id: str):
    return await participants_col.find_one({"giveaway_id": giveaway_id, "participant_id": participant_id})


async def get_participant_by_user(giveaway_id: str, user_id: int):
    return await participants_col.find_one({"giveaway_id": giveaway_id, "user_id": user_id})


async def get_top_participants(giveaway_id: str, limit: int = 10):
    cursor = participants_col.find({"giveaway_id": giveaway_id}).sort("votes_count", -1).limit(limit)
    return [p async for p in cursor]


async def get_all_participants(giveaway_id: str):
    cursor = participants_col.find({"giveaway_id": giveaway_id}).sort("votes_count", -1)
    return [p async for p in cursor]


async def get_participant_count(giveaway_id: str) -> int:
    return await participants_col.count_documents({"giveaway_id": giveaway_id})


async def increment_votes(giveaway_id: str, participant_id: str, amount: int = 1):
    await participants_col.update_one(
        {"giveaway_id": giveaway_id, "participant_id": participant_id},
        {"$inc": {"votes_count": amount}}
    )
    updated = await get_participant(giveaway_id, participant_id)
    return updated["votes_count"] if updated else None


# ==================== VOTES ====================

async def get_vote(giveaway_id: str, voter_id: int):
    """Returns the vote doc (with participant_id) if this voter has voted in this giveaway."""
    return await votes_col.find_one({"giveaway_id": giveaway_id, "voter_id": voter_id})


async def cast_vote(giveaway_id: str, voter_id: int, participant_id: str):
    await votes_col.insert_one({
        "giveaway_id": giveaway_id,
        "voter_id": voter_id,
        "participant_id": participant_id,
        "timestamp": datetime.now(timezone.utc),
    })


async def remove_vote(giveaway_id: str, voter_id: int):
    await votes_col.delete_one({"giveaway_id": giveaway_id, "voter_id": voter_id})


async def get_votes_by_giveaway(giveaway_id: str):
    cursor = votes_col.find({"giveaway_id": giveaway_id})
    return [v async for v in cursor]


# ==================== OWNER SESSION ====================

async def set_owner_session(giveaway_id: str):
    await owner_sessions_col.update_one(
        {"_id": "owner"},
        {"$set": {"giveaway_id": giveaway_id}},
        upsert=True
    )


async def clear_owner_session():
    await owner_sessions_col.delete_one({"_id": "owner"})


async def get_owner_session():
    doc = await owner_sessions_col.find_one({"_id": "owner"})
    return doc["giveaway_id"] if doc else None
