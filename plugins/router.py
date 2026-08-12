from pyrogram import Client, filters
from pyrogram.types import Message

RESERVED_COMMANDS = [
    "start", "help", "host", "incr", "end", "cancel", "mystats",
    "access", "exit", "current",
    "addadmin", "removeadmin", "stats", "ban", "unban", "startpic", "broadcast",
]


@Client.on_message(
    filters.private & (filters.text | filters.forwarded) & ~filters.command(RESERVED_COMMANDS),
    group=0,
)
async def conversation_router(client: Client, message: Message):
    # imported here (not top-level) to avoid circular imports between plugins
    from plugins.host import host_states, host_flow_handler
    from plugins.participate import participate_states, caption_text_handler
    from plugins.admin import admin_states, handle_broadcast_message

    user_id = message.from_user.id

    if user_id in host_states:
        await host_flow_handler(client, message)
        return

    if user_id in participate_states:
        await caption_text_handler(client, message)
        return

    state = admin_states.get(user_id)
    if state and state.get("action") == "broadcast":
        await handle_broadcast_message(client, message)
        return

    # no active conversation for this user -> ignore silently


@Client.on_message(filters.private & filters.photo, group=0)
async def photo_router(client: Client, message: Message):
    from plugins.admin import admin_states, handle_startpic_photo, handle_broadcast_message

    user_id = message.from_user.id
    state = admin_states.get(user_id)
    if not state:
        return

    if state.get("action") == "startpic":
        await handle_startpic_photo(client, message)
    elif state.get("action") == "broadcast":
        await handle_broadcast_message(client, message)
