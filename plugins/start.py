from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import SUPPORT_USERNAME
from database import get_participant, cast_vote, has_voted, increment_votes, \
    get_giveaway, get_participant_by_user
from helpers import is_subscribed


START_TEXT = (
    "👋 <b>Welcome to Infinite!</b>\n\n"
    "🎉 The ultimate Giveaway Voting Bot\n\n"
    "Here's what you can do:\n"
    "🏆 Host your own giveaway & manage voting\n"
    "🗳️ Participate & get your friends to vote for you\n"
    "🔥 Track live results in real-time\n\n"
    "━━━━━━━━━━━━━━━\n"
    "👉 Tap below to get started!\n"
    "━━━━━━━━━━━━━━━"
)

HELP_TEXT = (
    "📖 <b>Infinite — Help & Commands</b>\n\n"
    "<b>For Hosters:</b>\n"
    "🎯 /host — Start a new giveaway (add channel, set timing)\n"
    "📊 /incr &lt;participant_id&gt; &lt;count&gt; — Manually boost a participant's votes\n"
    "🛑 /end — End your giveaway manually\n\n"
    "<b>For Everyone:</b>\n"
    "🎉 /start — Get started with the bot\n"
    "🗳️ Vote — Tap the \"Vote\" button on any participant's post\n"
    "📌 Participate — Click \"Participate\" to join an active giveaway\n\n"
    "━━━━━━━━━━━━━━━\n"
    f"❓ Need more help? Contact @{SUPPORT_USERNAME}\n"
    "━━━━━━━━━━━━━━━"
)


@Client.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    # deep-link handling: /start participate_<giveaway_id> or vote_<giveaway_id>_<participant_id>
    if len(message.command) > 1:
        payload = message.command[1]
        if payload.startswith("participate_"):
            from plugins.participate import start_participation
            giveaway_id = payload.split("_", 1)[1]
            await start_participation(client, message, giveaway_id)
            return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Host a Giveaway", callback_data="host_start")],
        [InlineKeyboardButton("ℹ️ How it Works", callback_data="how_it_works")],
    ])
    await message.reply_text(START_TEXT, reply_markup=keyboard)


@Client.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    await message.reply_text(HELP_TEXT)


@Client.on_callback_query(filters.regex("^how_it_works$"))
async def how_it_works_cb(client: Client, cq):
    text = (
        "ℹ️ <b>How Infinite Works</b>\n\n"
        "1️⃣ A hoster adds their channel and sets a giveaway duration\n"
        "2️⃣ Anyone can join by joining the channel and tapping Participate\n"
        "3️⃣ Each participant gets their own post with a Vote button\n"
        "4️⃣ Friends vote by joining the channel and tapping Vote\n"
        "5️⃣ One user = one vote for the entire giveaway\n"
        "6️⃣ When time's up, results are posted automatically 🏆"
    )
    await cq.message.edit_text(text)
    await cq.answer()
