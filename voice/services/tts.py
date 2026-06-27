import logging
import asyncio
from django.conf import settings
from asgiref.sync import async_to_sync

logger = logging.getLogger('app')

class BaseTTS:
    def speak(self, text: str, output_path: str) -> None:
        raise NotImplementedError("Subclasses must implement speak()")

class EdgeTTS(BaseTTS):
    """
    Microsoft Edge TTS Service.
    Generates highly natural, expressive neural voices.
    """
    def speak(self, text: str, output_path: str) -> None:
        # Get voice from settings, default to Guy (English US)
        voice = getattr(settings, 'EDGE_TTS_VOICE', 'en-US-GuyNeural')
        
        # Simple heuristic to switch voice if Hindi content is present
        # Hindi characters range from \u0900 to \u097F
        if any(ord(char) >= 0x0900 and ord(char) <= 0x097F for char in text):
            voice = 'hi-IN-MadhurNeural' # Switch to Indian Hindi neural voice
            
        logger.info(f"Generating Edge TTS audio with voice '{voice}' to '{output_path}'...")
        
        try:
            import edge_tts
            
            async def _generate():
                communicate = edge_tts.Communicate(text, voice)
                await communicate.save(output_path)
                
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            if loop.is_running():
                async_to_sync(_generate)()
            else:
                loop.run_until_complete(_generate())
                
            logger.info("Edge TTS audio generation completed successfully.")
        except ImportError:
            logger.error("edge-tts library not installed.")
            raise RuntimeError("edge-tts package is required for EdgeTTS provider.")
        except Exception as e:
            logger.error(f"Edge TTS generation failed: {str(e)}", exc_info=True)
            raise

class GoogleTTS(BaseTTS):
    """
    Google Translate TTS Service using gTTS.
    Lightweight, synchronous, and robust fallback.
    """
    def speak(self, text: str, output_path: str) -> None:
        logger.info(f"Generating Google TTS audio to '{output_path}'...")
        try:
            from gtts import gTTS
            
            # Simple heuristic for Hindi character set
            lang = 'en'
            if any(ord(char) >= 0x0900 and ord(char) <= 0x097F for char in text):
                lang = 'hi'
            else:
                voice = getattr(settings, 'EDGE_TTS_VOICE', 'en-US-GuyNeural')
                lang = voice.split('-')[0] if '-' in voice else 'en'
                
            tts = gTTS(text=text, lang=lang)
            tts.save(output_path)
            logger.info("Google TTS audio generation completed successfully.")
        except ImportError:
            logger.error("gtts library not installed.")
            raise RuntimeError("gtts package is required for GoogleTTS provider.")
        except Exception as e:
            logger.error(f"Google TTS generation failed: {str(e)}", exc_info=True)
            raise

def get_tts_service() -> BaseTTS:
    """
    Factory function returning the configured TTS service.
    Falls back to GoogleTTS if EdgeTTS is selected but fails.
    """
    provider = getattr(settings, 'TTS_PROVIDER', 'edge')
    
    if provider == 'edge':
        try:
            import edge_tts
            return EdgeTTS()
        except Exception as e:
            logger.warning(f"Edge TTS initialization failed, falling back to Google TTS. Error: {str(e)}")
            return GoogleTTS()
    else:
        return GoogleTTS()
