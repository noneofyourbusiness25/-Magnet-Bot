from pyrogram import Client, filters
from database import db
import logging

logger = logging.getLogger(__name__)

def setup_forwarder(app: Client):
    """Attaches the forwarder handler to the User Client instance."""

    @app.on_message(~filters.me & ~filters.service)
    async def auto_forward(client, message):
        chat_id = message.chat.id
        destinations = db.get_destinations(chat_id)

        if not destinations:
            return

        for dest_id in destinations:
            try:
                await message.forward(dest_id)
                logger.info(f"Forwarded message {message.id} from {chat_id} to {dest_id}")
            except Exception as e:
                logger.error(f"Failed to forward message from {chat_id} to {dest_id}: {e}")
