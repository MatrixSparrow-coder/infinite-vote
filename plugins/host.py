from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import RPCError

from database import get_active_giveaway_by_hoster, create_giveaway, is_banned
from helpers import is_channel_admin, is_bot_admin_in_channel, parse_ist_datetime, format_ist, to_utc, small_caps

# Simple in-memory conversation state: {user_id: {"step": ..., data...}}
host_states: dict[int, dict] = {}


async def send_step_channel(client, chat_id):
    await client.send_message(
        chat_id,
        small_caps(
            "📢 <b>Step 1/3 — Add your channel</b>\n\n"
            "1. Add this bot as <b>admin</b> in your giveaway channel\n"
            "2. Forward any message from that channel here, "
            "OR send the channel's @username\n\n"
            "⚠️ You must be the admin/owner of that channel."
        )
    )


@Client.on_message(filters.command("host") & filters.private)
async def host_cmd(client: Client, message: Message):
    user_id = message.from_user.id

    if await is_banned(user_id):
        await message.reply_text(small_caps("🚫 <b>You are banned from using this bot.</b>"))
        return

    existing = await get_active_giveaway_by_hoster(user_id)
    if existing:
        await message.reply_text(small_caps(
            f"⚠️ You already have an active giveaway (ID: <code>{existing['giveaway_id']}</code>).\n"
            f"You can only run one giveaway at a time. Use /end to close it first."
        ))
        return

    host_states[user_id] = {"step": "awaiting_channel"}
    await send_step_channel(client, message.chat.id)


@Client.on_callback_query(filters.regex("^host_start$"))
async def host_start_cb(client: Client, cq: CallbackQuery):
    user_id = cq.from_user.id

    if await is_banned(user_id):
        await cq.answer("You are banned from using this bot.", show_alert=True)
        return

    existing = await get_active_giveaway_by_hoster(user_id)
    if existing:
        await cq.answer("You already have an active giveaway running!", show_alert=True)
        return

    host_states[user_id] = {"step": "awaiting_channel"}
    await cq.answer()
    await send_step_channel(client, cq.message.chat.id)


async def host_flow_handler(client: Client, message: Message):
    """Called by the central router in plugins/router.py when user is mid host-setup."""
    user_id = message.from_user.id
    state = host_states.get(user_id)
    if not state:
        return

    step = state["step"]

    # ---------- Step 1: channel ----------
    if step == "awaiting_channel":
        channel_id = None

        if message.forward_from_chat:
            channel_id = message.forward_from_chat.id
        elif message.text and message.text.startswith("@"):
            try:
                chat = await client.get_chat(message.text.strip())
                channel_id = chat.id
            except RPCError:
                await message.reply_text(small_caps("❌ Couldn't find that channel. Please check the username and try again."))
                return
        else:
            await message.reply_text(small_caps("❌ Please forward a message from the channel, or send its @username."))
            return

        try:
            chat = await client.get_chat(channel_id)
        except RPCError:
            await message.reply_text(small_caps("❌ Couldn't access that channel. Make sure the bot is added there."))
            return

        if not await is_bot_admin_in_channel(client, channel_id):
            await message.reply_text(small_caps("❌ The bot must be an <b>admin</b> in that channel. Add it as admin and try again."))
            return

        if not await is_channel_admin(client, user_id, channel_id):
            await message.reply_text(small_caps("❌ You must be an admin or owner of that channel to host a giveaway there."))
            return

        state["channel_id"] = channel_id
        state["channel_title"] = chat.title
        state["step"] = "awaiting_start_time"

        await message.reply_text(small_caps(
            f"✅ Channel set: <b>{chat.title}</b>\n\n"
            "📅 <b>Step 2/3 — Start time</b>\n\n"
            "Send the giveaway <b>start time</b> in IST, format:\n"
            "<code>YYYY-MM-DD HH:MM</code>\n"
            "Example: <code>2026-08-15 20:00</code>"
        ))
        return

    # ---------- Step 2: start time ----------
    if step == "awaiting_start_time":
        dt = parse_ist_datetime(message.text or "")
        if not dt:
            await message.reply_text(small_caps("❌ Invalid format. Please send like: <code>2026-08-15 20:00</code>"))
            return

        state["start_time"] = dt
        state["step"] = "awaiting_end_time"
        await message.reply_text(small_caps(
            f"✅ Start time: {format_ist(dt)}\n\n"
            "📅 <b>Step 3/3 — End time</b>\n\n"
            "Send the giveaway <b>end time</b> in IST, same format:\n"
            "<code>YYYY-MM-DD HH:MM</code>"
        ))
        return

    # ---------- Step 3: end time -> review & confirm ----------
    if step == "awaiting_end_time":
        dt = parse_ist_datetime(message.text or "")
        if not dt:
            await message.reply_text(small_caps("❌ Invalid format. Please send like: <code>2026-08-16 20:00</code>"))
            return

        if dt <= state["start_time"]:
            await message.reply_text(small_caps("❌ End time must be after the start time. Please resend the end time."))
            return

        state["end_time"] = dt
        state["step"] = "awaiting_confirmation"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Confirm & Create", callback_data="host_confirm")],
            [InlineKeyboardButton("❌ Cancel & Restart", callback_data="host_restart")],
        ])

        await message.reply_text(
            small_caps(
                "📋 <b>Review your giveaway</b>\n\n"
                f"📢 Channel: <b>{state['channel_title']}</b>\n"
                f"🟢 Start: {format_ist(state['start_time'])}\n"
                f"🔴 End: {format_ist(state['end_time'])}\n\n"
                "Everything correct?"
            ),
            reply_markup=keyboard
        )
        return


@Client.on_callback_query(filters.regex("^host_restart$"))
async def host_restart_cb(client: Client, cq: CallbackQuery):
    user_id = cq.from_user.id
    host_states[user_id] = {"step": "awaiting_channel"}
    await cq.answer()
    await cq.message.edit_text(small_caps("🔄 Restarting setup..."))
    await send_step_channel(client, cq.message.chat.id)


@Client.on_callback_query(filters.regex("^host_confirm$"))
async def host_confirm_cb(client: Client, cq: CallbackQuery):
    user_id = cq.from_user.id
    state = host_states.get(user_id)
    if not state or state.get("step") != "awaiting_confirmation":
        await cq.answer("This setup session expired, please /host again.", show_alert=True)
        return

    await cq.answer()

    giveaway_id = await create_giveaway(
        hoster_id=user_id,
        channel_id=state["channel_id"],
        channel_title=state["channel_title"],
        start_time=to_utc(state["start_time"]),
        end_time=to_utc(state["end_time"]),
    )

    me = await client.get_me()
    await cq.message.edit_text(small_caps(
        "🎉 <b>Giveaway created successfully!</b>\n\n"
        f"🆔 Giveaway ID: <code>{giveaway_id}</code>\n"
        f"📢 Channel: {state['channel_title']}\n"
        f"🟢 Start: {format_ist(state['start_time'])}\n"
        f"🔴 End: {format_ist(state['end_time'])}\n\n"
        "Share the participate link with your audience, or post it in your channel:\n"
        f"👉 <code>https://t.me/{me.username}?start=participate_{giveaway_id}</code>"
    ))

    host_states.pop(user_id, None)

    from plugins.owner import notify_owner_new_giveaway
    await notify_owner_new_giveaway(client, giveaway_id, user_id, state["channel_title"])
          
