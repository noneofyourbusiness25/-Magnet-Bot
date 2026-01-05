import logging
import asyncio
from pyrogram import Client, idle
from config import Config
from user_client import user_bot

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    if not Config.API_ID or not Config.API_HASH or not Config.BOT_TOKEN:
        logger.error("API_ID, API_HASH, and BOT_TOKEN must be set in environment variables.")
        return

    # Initialize the Controller Bot
    bot = Client(
        "evergreen_controller",
        api_id=Config.API_ID,
        api_hash=Config.API_HASH,
        bot_token=Config.BOT_TOKEN,
        plugins=dict(root="plugins")
    )

    logger.info("Starting Evergreen Controller Bot...")
    await bot.start()

    me = await bot.get_me()
    logger.info(f"Controller Bot started as @{me.username}")

    # Start User Client if session exists
    await user_bot.start()

    await idle()
    await user_bot.stop()
    await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())
