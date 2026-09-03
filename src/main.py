import os
import asyncio
import logging
from dotenv import load_dotenv
from pyrogram import Client

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)
logger = logging.getLogger(__name__)

# Ensure required env vars are present
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
USER_SESSION = os.environ.get("USER_SESSION")

if not API_ID or not API_HASH or not BOT_TOKEN:
    logger.error("Missing required environment variables. Please check .env file.")
    exit(1)

# Initialize the Bot Client
bot = Client(
    "telegram_forwarder_bot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="src.handlers")
)

# Optional User Client for large files bypass
user_client = None
if USER_SESSION:
    user_client = Client(
        "telegram_user_client",
        api_id=int(API_ID),
        api_hash=API_HASH,
        session_string=USER_SESSION
    )

from src.handlers.forwarder import process_worker

async def main():
    logger.info("Starting bot...")
    await bot.start()

    # --- ADD THIS SANITY CHECK ---
    me = await bot.get_me()
    logger.info(f"SANITY CHECK: I am successfully logged in as @{me.username}")
    # ------------------------

    if user_client:
        logger.info("Starting user client...")
        await user_client.start()

    logger.info("Starting background worker...")
    worker_task = asyncio.create_task(process_worker())

    logger.info("Bot is running. Listening for events...")

    # Run forever
    await asyncio.Event().wait()

    logger.info("Stopping bot...")
    worker_task.cancel()
    await bot.stop()
    if user_client:
        await user_client.stop()

if __name__ == "__main__":
    # Workaround for ProactorEventLoop in Windows or standard loop in Linux
    asyncio.run(main())
