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
    Converts input audio file to standard WAV format.
    Recommended standard for Speech-to-Text: 16kHz, mono, pcm_s16le.
    If FFmpeg is not installed, it will copy the file directly.
    """
    input_path_obj = Path(input_path)
    
    # If the file is already a WAV file and we don't need resampling, just copy it
    if input_path_obj.suffix.lower() == '.wav':
        shutil.copy2(input_path, output_path)
        return output_path
        
    logger.info(f"Converting audio file {input_path} to WAV at {output_path} using FFmpeg...")
    try:
        # Run FFmpeg to convert input to standard 16kHz mono PCM 16-bit WAV
        cmd = [
            'ffmpeg', '-y', 
            '-i', str(input_path), 
            '-ar', '16000', 
            '-ac', '1', 
            '-c:a', 'pcm_s16le', 
            str(output_path)
        ]
        
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
        # Scan for MP3 and WAV files in media/audio directory
        for file_path in media_audio_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in ['.mp3', '.wav']:
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
