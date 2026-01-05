import logging
import asyncio
from pyrogram import Client, filters
from config import Config
from database import db
from plugins.forwarder import setup_forwarder

logger = logging.getLogger(__name__)

class UserClientManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UserClientManager, cls).__new__(cls)
            cls._instance.client = None
        return cls._instance

    async def start(self):
        """Starts the user client if a session exists."""
        if self.client and self.client.is_connected:
            return

        session = db.get_session()
        if not session:
            logger.info("No user session found.")
            return

        logger.info("Starting User Client...")
        self.client = Client(
            "user_session",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            session_string=session,
            in_memory=True
        )

        # Attach handlers dynamically
        setup_forwarder(self.client)

        try:
            await self.client.start()
            me = await self.client.get_me()
            logger.info(f"User Client started as: {me.first_name} (@{me.username})")
        except Exception as e:
            logger.error(f"Failed to start user client: {e}")
            # If session is invalid, maybe we should delete it?
            # db.delete_session()

    async def stop(self):
        if self.client and self.client.is_connected:
            await self.client.stop()
            logger.info("User Client stopped.")

    def is_running(self):
        return self.client and self.client.is_connected

    async def restart(self):
        await self.stop()
        await self.start()

user_bot = UserClientManager()
