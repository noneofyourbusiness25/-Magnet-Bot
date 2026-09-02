import asyncio
import os
import math
import random
import logging
import aiofiles
import aiofiles.os
from pyrogram import Client
from typing import Callable, Coroutine
from pyrogram.file_id import FileId
from pyrogram.raw import functions, types

logger = logging.getLogger(__name__)

ACTUAL_CHUNK = 512 * 1024 # 512KB is safe for MTProto GetFile/SaveBigFilePart

async def fast_download(client: Client, message, file_path: str, progress_func: Callable = None):
    """
    Custom Parallel Chunked Downloader bypassing standard .download()
    """
    media = message.document or message.video or message.audio
    if not media:
        raise ValueError("No media found to download")

    file_id_str = media.file_id
    file_size = media.file_size

    try:
        decoded = FileId.decode(file_id_str)
        location = types.InputDocumentFileLocation(
            id=decoded.media_id,
            access_hash=decoded.access_hash,
            file_reference=decoded.file_reference,
            thumb_size=""
        )
    except Exception as e:
        logger.warning(f"Failed to create raw location, falling back to stream_media: {e}")
        return await _fallback_download(client, message, file_path, progress_func)

    # Handling DC Migration
    media_session = client
    if decoded.dc_id != await client.storage.dc_id():
        try:
            auth_key = await client.storage.auth_key()
            media_session = await client.invoke(functions.auth.ExportAuthorization(dc_id=decoded.dc_id))
            # For simplicity in this script, we'll try to just let pyrogram handle it,
            # if we get a FileMigrateError, it means Pyrogram's underlying session
            # hasn't migrated. For maximum robustness in MTProto, we would spin up a completely
            # new Client instance connected to the target DC.
            # Given Pyrogram handles `stream_media` cleanly across DCs, if `GetFile` fails,
            # falling back to `stream_media` is actually the standard Pyrogram convention
            # unless a full DC pool is implemented. I'll wrap the chunk worker to
            # gracefully catch the specific `FileMigrate` and raise it cleanly.
        except Exception:
            pass

    concurrency = 4
    sem = asyncio.Semaphore(concurrency)
    downloaded_bytes = 0

    async def download_worker(offset, chunk_size):
        nonlocal downloaded_bytes
        async with sem:
            result = await client.invoke(
                functions.upload.GetFile(
                    location=location,
                    offset=offset,
                    limit=chunk_size
                )
            )
            downloaded_bytes += len(result.bytes)
            if progress_func:
                await progress_func.update(downloaded_bytes, file_size)
            return offset, result.bytes

    offsets = range(0, file_size, ACTUAL_CHUNK)

    async with aiofiles.open(file_path, "wb") as f:
        if file_size > 0:
            await f.seek(file_size - 1)
            await f.write(b'\0')

    try:
        tasks = [asyncio.create_task(download_worker(off, ACTUAL_CHUNK)) for off in offsets]

        for coro in asyncio.as_completed(tasks):
            offset, data = await coro
            async with aiofiles.open(file_path, "r+b") as f:
                await f.seek(offset)
                await f.write(data)
    except Exception as e:
        logger.warning(f"Parallel download failed (likely FileMigrate), falling back to stream_media: {e}")
        for t in tasks:
            t.cancel()
        return await _fallback_download(client, message, file_path, progress_func)

    return file_path

async def _fallback_download(client: Client, message, file_path: str, progress_func: Callable = None):
    downloaded = 0
    file_size = getattr(message.document or message.video or message.audio, "file_size", 0)

    async with aiofiles.open(file_path, "wb") as f:
        async for chunk in client.stream_media(message):
            await f.write(chunk)
            downloaded += len(chunk)
            if progress_func:
                await progress_func.update(downloaded, file_size)
    return file_path

async def fast_upload(client: Client, chat_id: int, file_path: str, caption: str,
                     thumb_path: str = None, is_video: bool = False,
                     progress_func: Callable = None,
                     duration: int = 0, width: int = 1280, height: int = 720):
    """
    Custom Parallel Chunked Uploader bypassing standard upload
    """
    file_size = (await aiofiles.os.stat(file_path)).st_size
    file_name = os.path.basename(file_path)

    # Dynamically scale chunk size to respect Telegram's 3999 part limit
    chunk_size = ACTUAL_CHUNK
    if file_size > 3999 * chunk_size:
        chunk_size = 1024 * 1024 # 1MB (Supports up to ~3.99GB)

    total_parts = math.ceil(file_size / chunk_size)
    file_id = random.randint(0, 2**56 - 1)
    is_big = file_size > 10 * 1024 * 1024 # 10MB limit for SaveFilePart

    uploaded_bytes = 0
    sem = asyncio.Semaphore(4)

    async def upload_worker(part_id, offset):
        nonlocal uploaded_bytes
        async with sem:
            async with aiofiles.open(file_path, "rb") as f:
                await f.seek(offset)
                chunk = await f.read(chunk_size)

            if is_big:
                await client.invoke(
                    functions.upload.SaveBigFilePart(
                        file_id=file_id,
                        file_part=part_id,
                        file_total_parts=total_parts,
                        bytes=chunk
                    )
                )
            else:
                await client.invoke(
                    functions.upload.SaveFilePart(
                        file_id=file_id,
                        file_part=part_id,
                        bytes=chunk
                    )
                )
            uploaded_bytes += len(chunk)
            if progress_func:
                await progress_func.update(uploaded_bytes, file_size)

    tasks = [upload_worker(i, i * chunk_size) for i in range(total_parts)]
    await asyncio.gather(*tasks)

    if is_big:
        input_file = types.InputFileBig(
            id=file_id,
            parts=total_parts,
            name=file_name
        )
    else:
        input_file = types.InputFile(
            id=file_id,
            parts=total_parts,
            name=file_name,
            md5_checksum=""
        )

    if is_video:
        attributes = [
            types.DocumentAttributeVideo(
                duration=duration,
                w=width,
                h=height,
                supports_streaming=True
            ),
            types.DocumentAttributeFilename(file_name=file_name)
        ]
    else:
        attributes = [types.DocumentAttributeFilename(file_name=file_name)]

    # Handle thumbnail upload if provided
    thumb_input_file = None
    if thumb_path and os.path.exists(thumb_path):
        try:
            # We can use standard save_file for small thumbs
            thumb_input_file = await client.save_file(thumb_path)
        except Exception as e:
            logger.warning(f"Failed to upload thumbnail: {e}")

    media = types.InputMediaUploadedDocument(
        file=input_file,
        mime_type="video/mp4" if is_video else "application/octet-stream",
        attributes=attributes,
        force_file=not is_video,
        thumb=thumb_input_file
    )

    peer = await client.resolve_peer(chat_id)

    await client.invoke(
        functions.messages.SendMedia(
            peer=peer,
            media=media,
            message=caption,
            random_id=random.randint(0, 2**56 - 1)
        )
    )
