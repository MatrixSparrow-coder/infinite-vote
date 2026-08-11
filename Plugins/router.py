from pyrogram import Client, filters
from pyrogram.types import Message

RESERVED_COMMANDS = ["start", "help", "host", "incr", "end", "access", "exit"]


@Client.on_message(
    filters.private & (filters.text | filters.forwarded) & ~filters.command(RESERVED_COMMANDS),
    group=0,
)
async def conversation_router(client: Client, message: Message):
    # imported here (not top-level) to avoid circular imports between plugins
    from plugins.host import host_states, host_flow_handler
    from plugins.participate import participate_states, caption_text_handler

    user_id = message.from_user.id

    if user_id in host_states:
        await host_flow_handler(client, message)
        return

    if user_id in participate_states:
        await caption_text_handler(client, message)
        return

    # no active conversation for this user -> ignore silently
