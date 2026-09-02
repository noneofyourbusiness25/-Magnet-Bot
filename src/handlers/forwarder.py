import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from src.database.db import db
from src.core.fast_io import fast_download, fast_upload
from src.core.metadata import modify_metadata, analyze_media, extract_video_attributes
from src.utils.text_parser import TextSanitizer
from src.utils.progress import ProgressTracker

logger = logging.getLogger(__name__)

# Basic in-memory lock and queue
processing_queue = set()
task_queue = asyncio.Queue()

async def process_worker():
    """
    Background worker that processes files sequentially to protect disk and RAM.
    """
    while True:
        task_data = await task_queue.get()
        try:
            await process_file(task_data)
        except Exception as e:
            logger.error(f"Error in process_worker: {e}")
        finally:
            task_queue.task_done()

async def process_file(task_data: dict):
    client = task_data['client']
    message = task_data['message']
    target_channel = task_data['target_channel']
    settings = task_data['settings']

    download_path = ""
    processed_path = ""
    thumb_path = None

    try:
        status_msg = await client.send_message(target_channel, "⏳ Initiating process in queue...")

        media = message.document or message.video or message.audio
        original_name = getattr(media, "file_name", "Unknown_file")
        original_caption = message.caption or ""

        new_filename = TextSanitizer.format_filename(
            original_name,
            prefix=settings.get("prefix", ""),
            suffix=settings.get("suffix", ""),
            blacklists=settings.get("blacklisted_words", [])
        )
        new_caption = TextSanitizer.apply_blacklists(original_caption, settings.get("blacklisted_words", []))

        download_path = os.path.join("downloads", new_filename)
        os.makedirs("downloads", exist_ok=True)

        # Download
        download_tracker = ProgressTracker(status_msg, f"Downloading: {new_filename}")
        await fast_download(client, message, download_path, download_tracker)

        # Metadata Processing
        await status_msg.edit_text("⚙️ Processing internal metadata...")
        processed_path = await modify_metadata(download_path, settings)

        # Extract attributes for video
        duration, width, height = 0, 1280, 720
        is_video_mode = settings.get("upload_mode") == "Video"
        if is_video_mode:
            media_info = await analyze_media(processed_path)
            duration, width, height = await extract_video_attributes(media_info)

        # Thumbnail download
        thumb_file_id = settings.get("thumbnail")
        if thumb_file_id:
            try:
                thumb_path = await client.download_media(thumb_file_id)
            except Exception as e:
                logger.warning(f"Failed to download thumbnail: {e}")
                thumb_path = None

        # Upload
        upload_tracker = ProgressTracker(status_msg, f"Uploading: {new_filename}")

        await fast_upload(
            client=client,
            chat_id=target_channel,
            file_path=processed_path,
            caption=new_caption,
            thumb_path=thumb_path,
            is_video=is_video_mode,
            progress_func=upload_tracker,
            duration=duration,
            width=width,
            height=height
        )

        await status_msg.delete()

    except Exception as e:
        logger.error(f"Error processing message {message.id}: {e}")
        try:
            await status_msg.edit_text(f"❌ Error: {str(e)}")
        except Exception:
            pass
    finally:
        # Strict Cleanup
        if download_path and os.path.exists(download_path):
            try:
                os.remove(download_path)
            except Exception:
                pass
        if processed_path and processed_path != download_path and os.path.exists(processed_path):
            try:
                os.remove(processed_path)
            except Exception:
                pass
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except Exception:
                pass

        processing_queue.discard(message.id)


@Client.on_message(filters.channel & (filters.document | filters.video | filters.audio))
async def handle_channel_message(client: Client, message: Message):
    """
    Listens to channel messages and pushes them to the queue.
    """
    sudo_users_str = os.environ.get("SUDO_USERS", "")
    if not sudo_users_str:
        return

    main_admin = int(sudo_users_str.split(',')[0].strip())
    settings = await db.get_settings(main_admin)

    source_channel = settings.get("source_channel")
    target_channel = settings.get("target_channel")

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

    # Push to queue
    await task_queue.put({
        'client': client,
        'message': message,
        'target_channel': target_channel,
        'settings': settings
    })
