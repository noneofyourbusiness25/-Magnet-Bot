import asyncio
import os
import math
import random
import logging
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

    with open(file_path, "wb") as f:
        if file_size > 0:
            f.seek(file_size - 1)
            f.write(b'\0')

    tasks = [download_worker(off, ACTUAL_CHUNK) for off in offsets]

    for coro in asyncio.as_completed(tasks):
        offset, data = await coro
        with open(file_path, "r+b") as f:
            f.seek(offset)
            f.write(data)

    return file_path

async def _fallback_download(client: Client, message, file_path: str, progress_func: Callable = None):
    downloaded = 0
    file_size = getattr(message.document or message.video or message.audio, "file_size", 0)

    with open(file_path, "wb") as f:
        async for chunk in client.stream_media(message):
            f.write(chunk)
            downloaded += len(chunk)
            if progress_func:
                await progress_func.update(downloaded, file_size)
    return file_path

async def fast_upload(client: Client, chat_id: int, file_path: str, caption: str,
                     thumb_path: str = None, is_video: bool = False,
                     progress_func: Callable = None):
    """
    Custom Parallel Chunked Uploader bypassing standard upload
    """
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)

    total_parts = math.ceil(file_size / ACTUAL_CHUNK)
    file_id = random.randint(0, 2**56 - 1)

    uploaded_bytes = 0
    sem = asyncio.Semaphore(4)

    async def upload_worker(part_id, offset):
        nonlocal uploaded_bytes
        async with sem:
            with open(file_path, "rb") as f:
                f.seek(offset)
                chunk = f.read(ACTUAL_CHUNK)

            await client.invoke(
                functions.upload.SaveBigFilePart(
                    file_id=file_id,
                    file_part=part_id,
                    file_total_parts=total_parts,
                    bytes=chunk
                )
            )
            uploaded_bytes += len(chunk)
            if progress_func:
                await progress_func.update(uploaded_bytes, file_size)

    tasks = [upload_worker(i, i * ACTUAL_CHUNK) for i in range(total_parts)]
    await asyncio.gather(*tasks)

    input_file = types.InputFileBig(
        id=file_id,
        parts=total_parts,
        name=file_name
    )

    media = types.InputMediaUploadedDocument(
        file=input_file,
        mime_type="video/mp4" if is_video else "application/octet-stream",
        attributes=[types.DocumentAttributeVideo(w=1280, h=720, duration=0)] if is_video else [types.DocumentAttributeFilename(file_name=file_name)],
        force_file=not is_video
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
