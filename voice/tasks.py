import logging
import threading
from .utils import cleanup_old_audio_files

logger = logging.getLogger('app')

def trigger_async_audio_cleanup():
    """
    Spawns a daemon thread to delete expired audio files.
    This prevents file I/O operations from blocking the API response.
    """
    try:
        thread = threading.Thread(target=cleanup_old_audio_files, daemon=True)
        thread.start()
        logger.info("Asynchronous audio cleanup thread spawned successfully.")
    except Exception as e:
        logger.error(f"Failed to start async audio cleanup thread: {str(e)}")
