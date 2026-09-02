import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from src.database.db import db
from src.core.fast_io import fast_download, fast_upload
from src.core.metadata import modify_metadata
from src.utils.text_parser import TextSanitizer
from src.utils.progress import ProgressTracker

logger = logging.getLogger(__name__)

# Basic in-memory lock to prevent processing the same file multiple times
processing_queue = set()

@Client.on_message(filters.channel & (filters.document | filters.video | filters.audio))
async def handle_channel_message(client: Client, message: Message):
    """
    Listens to channel messages and processes them if they match the source_channel setup by any admin.
    For a single-user bot, we usually just fetch the main sudo user's settings.
    """
    # Find which admin configured this channel as source
    # For simplicity, assuming one main config. In multi-user, you'd query DB for source_channel == message.chat.id
    sudo_users_str = os.environ.get("SUDO_USERS", "")
    if not sudo_users_str:
        return

    main_admin = int(sudo_users_str.split(',')[0].strip())
    settings = await db.get_settings(main_admin)

    source_channel = settings.get("source_channel")
    target_channel = settings.get("target_channel")

    # Optional: str to int conversion if stored as strings
    try:
        if source_channel: source_channel = int(source_channel)
        if target_channel: target_channel = int(target_channel)
    except ValueError:
        pass

    if not source_channel or not target_channel:
        return

    if message.chat.id != source_channel:
        return

    # Check lock
    if message.id in processing_queue:
        return
    processing_queue.add(message.id)

    try:
        # Create a status message in the target channel or a log channel
        status_msg = await client.send_message(target_channel, "⏳ Initiating process...")

        # 1. Gather Media Info
        media = message.document or message.video or message.audio
        original_name = getattr(media, "file_name", "Unknown_file")
        original_caption = message.caption or ""

        # 2. Text Sanitization (Filename and Caption)
        new_filename = TextSanitizer.format_filename(
            original_name,
            prefix=settings.get("prefix", ""),
            suffix=settings.get("suffix", ""),
            blacklists=settings.get("blacklisted_words", [])
        )
        new_caption = TextSanitizer.apply_blacklists(original_caption, settings.get("blacklisted_words", []))

        download_path = os.path.join("downloads", new_filename)
        os.makedirs("downloads", exist_ok=True)

        # 3. Download
        download_tracker = ProgressTracker(status_msg, f"Downloading: {new_filename}")
        await fast_download(client, message, download_path, download_tracker)

        # 4. Process Metadata (Zero-encoding)
        await status_msg.edit_text("⚙️ Processing internal metadata...")
        processed_path = await modify_metadata(download_path, settings)

        # 5. Upload
        upload_tracker = ProgressTracker(status_msg, f"Uploading: {new_filename}")
        is_video_mode = settings.get("upload_mode") == "Video"

        await fast_upload(
            client=client,
            chat_id=target_channel,
            file_path=processed_path,
            caption=new_caption,
            thumb_path=settings.get("thumbnail"), # Not implemented downloading thumb from file_id yet
            is_video=is_video_mode,
            progress_func=upload_tracker
        )

        # Cleanup
        await status_msg.delete()
        if os.path.exists(processed_path):
            os.remove(processed_path)

    except Exception as e:
        logger.error(f"Error processing message {message.id}: {e}")
    finally:
        processing_queue.discard(message.id)
