from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from pyrogram.errors import RPCError

from database import get_active_giveaway_by_hoster, create_giveaway
from helpers import is_channel_admin, parse_ist_datetime, format_ist, to_utc

# Simple in-memory conversation state: {user_id: {"step": ..., data...}}
host_states: dict[int, dict] = {}


async def send_step_channel(client, chat_id):
    await client.send_message(
        chat_id,
        "📢 <b>Step 1/3 — Add your channel</b>\n\n"
        "1. Add this bot as <b>admin</b> in your giveaway channel\n"
        "2. Forward any message from that channel here, "
        "OR send the channel's @username\n\n"
        "⚠️ You must be the admin/owner of that channel."
    )


@Client.on_message(filters.command("host") & filters.private)
async def host_cmd(client: Client, message: Message):
    user_id = message.from_user.id

    existing = await get_active_giveaway_by_hoster(user_id)
    if existing:
        await message.reply_text(
            f"⚠️ You already have an active giveaway (ID: <code>{existing['giveaway_id']}</code>).\n"
            f"You can only run one giveaway at a time. Use /end to close it first."
        )
        return

    host_states[user_id] = {"step": "awaiting_channel"}
    await send_step_channel(client, message.chat.id)


@Client.on_callback_query(filters.regex("^host_start$"))
async def host_start_cb(client: Client, cq: CallbackQuery):
    user_id = cq.from_user.id

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
                await message.reply_text("❌ Couldn't find that channel. Please check the username and try again.")
                return
        else:
            await message.reply_text("❌ Please forward a message from the channel, or send its @username.")
            return

        try:
            chat = await client.get_chat(channel_id)
        except RPCError:
            await message.reply_text("❌ Couldn't access that channel. Make sure the bot is added there.")
            return

        # bot must be admin
        try:
            me = await client.get_me()
            bot_member = await client.get_chat_member(channel_id, me.id)
            if bot_member.status not in ("administrator", "creator"):
                await message.reply_text("❌ The bot must be an <b>admin</b> in that channel. Add it as admin and try again.")
                return
        except RPCError:
            await message.reply_text("❌ The bot isn't in that channel yet, or can't verify admin status. Add the bot as admin first.")
            return

        # user must be admin/owner of channel
        if not await is_channel_admin(client, user_id, channel_id):
            await message.reply_text("❌ You must be an admin or owner of that channel to host a giveaway there.")
            return

        state["channel_id"] = channel_id
        state["channel_title"] = chat.title
        state["step"] = "awaiting_start_time"

        await message.reply_text(
            f"✅ Channel set: <b>{chat.title}</b>\n\n"
            "📅 <b>Step 2/3 — Start time</b>\n\n"
            "Send the giveaway <b>start time</b> in IST, format:\n"
            "<code>YYYY-MM-DD HH:MM</code>\n"
            "Example: <code>2026-08-15 20:00</code>"
        )
        return

    # ---------- Step 2: start time ----------
    if step == "awaiting_start_time":
        dt = parse_ist_datetime(message.text or "")
        if not dt:
            await message.reply_text("❌ Invalid format. Please send like: <code>2026-08-15 20:00</code>")
            return

        state["start_time"] = dt
        state["step"] = "awaiting_end_time"
        await message.reply_text(
            f"✅ Start time: {format_ist(dt)}\n\n"
            "📅 <b>Step 3/3 — End time</b>\n\n"
            "Send the giveaway <b>end time</b> in IST, same format:\n"
            "<code>YYYY-MM-DD HH:MM</code>"
        )
        return

    # ---------- Step 3: end time ----------
    if step == "awaiting_end_time":
        dt = parse_ist_datetime(message.text or "")
        if not dt:
            await message.reply_text("❌ Invalid format. Please send like: <code>2026-08-16 20:00</code>")
            return

        if dt <= state["start_time"]:
            await message.reply_text("❌ End time must be after the start time. Please resend the end time.")
            return

        giveaway_id = await create_giveaway(
            hoster_id=user_id,
            channel_id=state["channel_id"],
            channel_title=state["channel_title"],
            start_time=to_utc(state["start_time"]),
            end_time=to_utc(dt),
        )

        await message.reply_text(
            "🎉 <b>Giveaway created successfully!</b>\n\n"
            f"🆔 Giveaway ID: <code>{giveaway_id}</code>\n"
            f"📢 Channel: {state['channel_title']}\n"
            f"🟢 Start: {format_ist(state['start_time'])}\n"
            f"🔴 End: {format_ist(dt)}\n\n"
            "Share the participate link with your audience, or post it in your channel:\n"
            f"👉 <code>https://t.me/{(await client.get_me()).username}?start=participate_{giveaway_id}</code>"
        )

        host_states.pop(user_id, None)

        # notify owner silently
        from plugins.owner import notify_owner_new_giveaway
        await notify_owner_new_giveaway(client, giveaway_id, user_id, state["channel_title"])
        return
  
