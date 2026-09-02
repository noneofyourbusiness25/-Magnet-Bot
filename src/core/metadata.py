import asyncio
import os
import logging
from pymediainfo import MediaInfo
from src.utils.text_parser import TextSanitizer

logger = logging.getLogger(__name__)

async def analyze_media(file_path: str):
    """
    Uses pymediainfo (which wraps MediaInfo) to quickly analyze all streams.
    Because pymediainfo is blocking, we run it in an executor.
    """
    loop = asyncio.get_event_loop()
    try:
        media_info = await loop.run_in_executor(None, MediaInfo.parse, file_path)
        return media_info
    except Exception as e:
        logger.error(f"Error analyzing media: {e}")
        return None

async def modify_metadata(file_path: str, user_settings: dict) -> str:
    """
    Modifies the metadata of an MKV or MP4 file in place (or returns new file path)
    using mkvpropedit (for MKV) or ffmpeg stream copy (for MP4).

    user_settings dictionary structure (example):
    {
        'video_rules': [{'pattern': '.*', 'action': 'replace', 'replacement': 'My Video Title'}],
        'audio_rules': [{'pattern': r'\[(.*?)\]', 'action': 'extract'}], # extracts language
        'sub_rules': [{'pattern': '.*', 'action': 'blank'}],
        'toggle_metadata': True
    }
    """

    if not user_settings.get('toggle_metadata', False):
        return file_path

    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.mkv':
        return await _modify_mkv(file_path, user_settings)
    elif ext == '.mp4':
        return await _modify_mp4(file_path, user_settings)
    else:
        # Unsupported format for internal metadata modification without re-encoding
        return file_path

async def _modify_mkv(file_path: str, user_settings: dict) -> str:
    """
    Uses mkvpropedit to edit MKV metadata in place.
    """
    media_info = await analyze_media(file_path)
    if not media_info:
        return file_path

    cmd = ["mkvpropedit", file_path]

    video_rules = user_settings.get('video_rules', [])
    audio_rules = user_settings.get('audio_rules', [])
    sub_rules = user_settings.get('sub_rules', [])

    v_track_idx = 1
    a_track_idx = 1
    s_track_idx = 1

    for track in media_info.tracks:
        if track.track_type == 'General':
            if video_rules:
                # Often the main title is in the General track
                current_title = track.title or ""
                new_title = TextSanitizer.apply_regex_rules(current_title, video_rules)
                cmd.extend(["-e", "info", "-s", f"title={new_title}"])

        elif track.track_type == 'Video':
            if video_rules:
                current_title = track.title or ""
                new_title = TextSanitizer.apply_regex_rules(current_title, video_rules)
                cmd.extend(["-e", f"track:v{v_track_idx}", "-s", f"name={new_title}"])
            v_track_idx += 1

        elif track.track_type == 'Audio':
            if audio_rules:
                current_title = track.title or ""
                new_title = TextSanitizer.apply_regex_rules(current_title, audio_rules)
                cmd.extend(["-e", f"track:a{a_track_idx}", "-s", f"name={new_title}"])
            a_track_idx += 1

        elif track.track_type == 'Text': # Subtitle
            if sub_rules:
                current_title = track.title or ""
                new_title = TextSanitizer.apply_regex_rules(current_title, sub_rules)
                cmd.extend(["-e", f"track:s{s_track_idx}", "-s", f"name={new_title}"])
            s_track_idx += 1

    if len(cmd) > 2: # Check if we added any edit commands
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"mkvpropedit failed: {stderr.decode()}")

    return file_path

async def _modify_mp4(file_path: str, user_settings: dict) -> str:
    """
    Uses ffmpeg with stream copying to edit MP4 metadata quickly.
    Creates a new file and replaces the old one.
    """
    out_file = f"{file_path}.temp.mp4"

    cmd = ["ffmpeg", "-y", "-i", file_path, "-map", "0", "-c", "copy", "-map_metadata", "-1"]

    media_info = await analyze_media(file_path)
    if not media_info:
        return file_path

    video_rules = user_settings.get('video_rules', [])
    audio_rules = user_settings.get('audio_rules', [])
    sub_rules = user_settings.get('sub_rules', [])

    v_idx = 0
    a_idx = 0
    s_idx = 0

    # Very basic mapping, a more robust solution would parse stream mappings exactly,
    # but ffmpeg usually orders them predictably.
    for track in media_info.tracks:
        if track.track_type == 'General' and video_rules:
            current_title = track.title or ""
            new_title = TextSanitizer.apply_regex_rules(current_title, video_rules)
            cmd.extend(["-metadata", f"title={new_title}"])

        elif track.track_type == 'Video' and video_rules:
            current_title = track.title or ""
            new_title = TextSanitizer.apply_regex_rules(current_title, video_rules)
            cmd.extend([f"-metadata:s:v:{v_idx}", f"title={new_title}"])
            v_idx += 1

        elif track.track_type == 'Audio' and audio_rules:
            current_title = track.title or ""
            new_title = TextSanitizer.apply_regex_rules(current_title, audio_rules)
            cmd.extend([f"-metadata:s:a:{a_idx}", f"title={new_title}"])
            a_idx += 1

        elif track.track_type == 'Text' and sub_rules:
            current_title = track.title or ""
            new_title = TextSanitizer.apply_regex_rules(current_title, sub_rules)
            cmd.extend([f"-metadata:s:s:{s_idx}", f"title={new_title}"])
            s_idx += 1

    cmd.append(out_file)

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()

    if process.returncode == 0:
        os.replace(out_file, file_path)
    else:
        logger.error(f"ffmpeg metadata edit failed: {stderr.decode()}")
        if os.path.exists(out_file):
            os.remove(out_file)

    return file_path
