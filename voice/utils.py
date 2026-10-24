import os
import time
import logging
import subprocess
import shutil
from pathlib import Path
from django.conf import settings

logger = logging.getLogger('app')

def convert_to_wav(input_path: str, output_path: str) -> str:
    """
    Converts input audio file (raw PCM from ESP32 or standard formats) to standard WAV format.
    Recommended standard for Speech-to-Text: 16kHz, mono, pcm_s16le.
    """
    input_path_obj = Path(input_path)
    ext = input_path_obj.suffix.lower()

    logger.info(f"Converting audio file {input_path} (ext: '{ext}') to WAV at {output_path} using FFmpeg...")
    
    try:
        # Check if input is raw PCM audio (sent from ESP32 without headers)
        if ext in ['.pcm', '.raw'] or ext == '':
            cmd = [
                'ffmpeg', '-y',
                '-f', 's32le',       # Signed 32-bit little-endian PCM (Matched with ESP32 32-bit I2S mode)
                '-ar', '16000',      # Sample rate 16kHz
                '-ac', '1',          # Mono channel
                '-i', str(input_path),
                '-ar', '16000',
                '-ac', '1',
                '-c:a', 'pcm_s16le',
                str(output_path)
            ]
        else:
            # Standard formats (mp3, wav, etc.)
            cmd = [
                'ffmpeg', '-y',
                '-i', str(input_path),
                '-ar', '16000',
                '-ac', '1',
                '-c:a', 'pcm_s16le',
                str(output_path)
            ]

        logger.info(f"Executing FFmpeg command: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        logger.info("FFmpeg audio conversion completed successfully.")
        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg conversion failed: {e.stderr}")
        raise RuntimeError(f"FFmpeg conversion failed: {e.stderr}")
    except FileNotFoundError:
        logger.warning("FFmpeg was not found in system path. Copying raw file directly as fallback.")
        shutil.copy2(input_path, output_path)
        return output_path


def cleanup_old_audio_files() -> int:
    """
    Deletes generated response MP3 audio files in media/audio/ that are older
    than settings.AUDIO_CLEANUP_AGE_MINUTES.
    Returns the number of files deleted.
    """
    media_audio_dir = Path(settings.MEDIA_AUDIO_DIR)
    cleanup_age_mins = getattr(settings, 'AUDIO_CLEANUP_AGE_MINUTES', 10)
    
    if not media_audio_dir.exists():
        return 0
        
    now = time.time()
    cutoff_time = now - (cleanup_age_mins * 60)
    deleted_count = 0
    
    logger.info(f"Starting audio cleanup. Files older than {cleanup_age_mins} minutes will be deleted.")
    
    try:
        for file_path in media_audio_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.mp3', '.wav', '.pcm']:
                file_mtime = file_path.stat().st_mtime
                if file_mtime < cutoff_time:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted old audio file: {file_path.name}")
                    except Exception as e:
                        logger.error(f"Failed to delete {file_path.name}: {str(e)}")
    except Exception as e:
        logger.error(f"Error during audio cleanup: {str(e)}")
        
    if deleted_count > 0:
        logger.info(f"Cleanup finished. Deleted {deleted_count} file(s).")
        
    return deleted_count
