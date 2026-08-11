from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from database import get_giveaway, get_participant_by_user, add_participant, set_participant_post_message
from helpers import is_subscribed

# in-memory state for the optional-caption step: {user_id: {"giveaway_id": ...}}
participate_states: dict[int, dict] = {}


def join_button(invite_link: str):
    return InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Channel", url=invite_link)]])


async def start_participation(client: Client, message: Message, giveaway_id: str):
    user_id = message.from_user.id

    giveaway = await get_giveaway(giveaway_id)
    if not giveaway or giveaway["status"] != "active":
        await message.reply_text("❌ This giveaway is no longer active.")
        return

    channel_id = giveaway["channel_id"]

    already = await get_participant_by_user(giveaway_id, user_id)
    if already:
        await message.reply_text(
            f"⚠️ You're already participating in this giveaway!\n"
            f"🆔 Your Participant ID: <code>{already['participant_id']}</code>"
        )
        return

    if not await is_subscribed(client, user_id, channel_id):
        try:
            chat = await client.get_chat(channel_id)
            invite = chat.invite_link or (await client.export_chat_invite_link(channel_id))
        except Exception:
            invite = None

        text = "⚠️ <b>Please join the channel first to be eligible to participate!</b>"
        if invite:
            await message.reply_text(text, reply_markup=join_button(invite))
        else:
            await message.reply_text(text)
        return

    # eligible -> ask optional caption
    participate_states[user_id] = {"giveaway_id": giveaway_id}
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭️ Skip", callback_data=f"skip_caption_{giveaway_id}")]
    ])
    await message.reply_text(
        "✅ You're eligible to participate!\n\n"
        "💬 Send a short caption for your post (e.g. \"Vote for me because...\"), "
        "or tap Skip to continue without one.",
        reply_markup=keyboard
    )


async def create_participation_post(client: Client, message_or_cq, giveaway_id: str, caption: str | None):
    user = message_or_cq.from_user
    giveaway = await get_giveaway(giveaway_id)
    channel_id = giveaway["channel_id"]

    # fetch profile photo (get_chat_photos is an async generator - no "await" on the call itself)
    photo_file_id = None
    try:
        async for p in client.get_chat_photos(user.id, limit=1):
            photo_file_id = p.file_id
            break
    except Exception:
        photo_file_id = None

    name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    participant_id = await add_participant(giveaway_id, user.id, name, photo_file_id, caption)

    post_text = (
        "🎉 <b>NEW PARTICIPANT ALERT</b> 🎉\n\n"
        f"👤 <b>Name:</b> {name}\n"
        f"🆔 <b>Participant ID:</b> #{participant_id}\n"
    )
    if caption:
        post_text += f"\n💬 \"{caption}\"\n"
    post_text += (
        "\n━━━━━━━━━━━━━━━\n"
        "🗳️ <b>Total Votes:</b> 0\n"
        "━━━━━━━━━━━━━━━"
    )

    vote_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔥 Vote (0)", callback_data=f"vote_{giveaway_id}_{participant_id}")]
    ])

    if photo_file_id:
        sent = await client.send_photo(channel_id, photo_file_id, caption=post_text, reply_markup=vote_keyboard)
    else:
        sent = await client.send_message(channel_id, post_text, reply_markup=vote_keyboard)

    await set_participant_post_message(giveaway_id, participant_id, sent.id)

    reply_target = message_or_cq.message if isinstance(message_or_cq, CallbackQuery) else message_or_cq
    await reply_target.reply_text(
        f"🎊 You're in! Your post is live in the channel.\n"
        f"🆔 Your Participant ID: <code>{participant_id}</code>\n\n"
        f"Share your post link with friends to get more votes! 🔥"
    )


@Client.on_callback_query(filters.regex(r"^skip_caption_"))
async def skip_caption_cb(client: Client, cq: CallbackQuery):
    giveaway_id = cq.data.split("_", 2)[2]
    await cq.answer()
    await create_participation_post(client, cq, giveaway_id, caption=None)
    participate_states.pop(cq.from_user.id, None)


async def caption_text_handler(client: Client, message: Message):
    """Called by the central router in plugins/router.py when user is mid participate-caption step."""
    user_id = message.from_user.id
    state = participate_states.get(user_id)
    if not state:
        return

    giveaway_id = state["giveaway_id"]
    caption = message.text.strip()[:200]  # cap length
    await create_participation_post(client, message, giveaway_id, caption)
    participate_states.pop(user_id, None)