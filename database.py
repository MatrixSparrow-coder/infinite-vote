from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import uuid

from config import MONGO_URI, DB_NAME

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

giveaways_col = db["giveaways"]
participants_col = db["participants"]
votes_col = db["votes"]
owner_sessions_col = db["owner_sessions"]  # tracks owner's /access session


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
        "status": "active",  # active | ended
        "created_at": datetime.now(timezone.utc),
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
        {"$set": {"status": "ended"}}
    )


async def get_all_active_giveaways():
    cursor = giveaways_col.find({"status": "active"})
    return [g async for g in cursor]


# ==================== PARTICIPANTS ====================

async def add_participant(giveaway_id: str, user_id: int, name: str,
                           photo_file_id: str | None, caption: str | None) -> str:
    # sequential-ish short id per giveaway
    count = await participants_col.count_documents({"giveaway_id": giveaway_id})
    participant_id = f"{count + 1:03d}"

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


async def increment_votes(giveaway_id: str, participant_id: str, amount: int = 1):
    await participants_col.update_one(
        {"giveaway_id": giveaway_id, "participant_id": participant_id},
        {"$inc": {"votes_count": amount}}
    )
    updated = await get_participant(giveaway_id, participant_id)
    return updated["votes_count"] if updated else None


# ==================== VOTES ====================

async def has_voted(giveaway_id: str, voter_id: int) -> bool:
    """1 user = 1 vote TOTAL per giveaway (not per participant)."""
    existing = await votes_col.find_one({"giveaway_id": giveaway_id, "voter_id": voter_id})
    return existing is not None


async def cast_vote(giveaway_id: str, voter_id: int, participant_id: str):
    await votes_col.insert_one({
        "giveaway_id": giveaway_id,
        "voter_id": voter_id,
        "participant_id": participant_id,
        "timestamp": datetime.now(timezone.utc),
    })


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
