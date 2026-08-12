from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import SUPPORT_USERNAME
from database import is_banned, track_user, get_start_pic
from helpers import small_caps


START_TEXT_RAW = (
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

HELP_TEXT_RAW = (
    "📖 <b>Infinite — Help & Commands</b>\n\n"
    "<b>For Hosters:</b>\n"
    "🎯 /host — Start a new giveaway (add channel, set timing)\n"
    "📊 /incr &lt;participant_id&gt; &lt;count&gt; — Manually boost a participant's votes\n"
    "🛑 /end — End your giveaway manually\n"
    "🚫 /cancel — Cancel your giveaway before anyone joins\n"
    "📈 /mystats — See your hosting history\n\n"
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
    user_id = message.from_user.id

    if await is_banned(user_id):
        await message.reply_text(small_caps("🚫 <b>You are banned from using this bot.</b>"))
        return

    await track_user(user_id)

    # deep-link handling: /start participate_<giveaway_id>
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

    text = small_caps(START_TEXT_RAW)
    start_pic = await get_start_pic()

    if start_pic:
        try:
            await message.reply_photo(start_pic, caption=text, reply_markup=keyboard)
            return
        except Exception:
            pass  # fall through to text-only if the stored file_id is somehow invalid

    await message.reply_text(text, reply_markup=keyboard)


@Client.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    await message.reply_text(small_caps(HELP_TEXT_RAW))


@Client.on_callback_query(filters.regex("^how_it_works$"))
async def how_it_works_cb(client: Client, cq):
    text = small_caps(
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
