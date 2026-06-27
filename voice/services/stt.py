import os
import logging
from django.conf import settings

logger = logging.getLogger('app')

class BaseSTT:
    def transcribe(self, file_path: str, language: str = None) -> str:
        raise NotImplementedError("Subclasses must implement transcribe()")

class GoogleSTT(BaseSTT):
    """
    Google Speech Recognition API Provider.
    Does not require local GPU/CPU model loading, making it extremely fast
    for lightweight web servers.
    """
    def transcribe(self, file_path: str, language: str = None) -> str:
        logger.info(f"Transcribing {file_path} using Google Speech API...")
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(file_path) as source:
                audio_data = recognizer.record(source)
                
            # If no language is explicitly requested, try English, but support Hindi
            # We can use 'hi-IN' or 'en-US' or let Google transcribe.
            # To support both, we default to settings, or fall back to English/Hindi.
            lang = language or getattr(settings, 'STT_LANGUAGE', 'en-US')
            
            # Google Speech recognition call
            text = recognizer.recognize_google(audio_data, language=lang)
            logger.info(f"Google STT transcription successful: '{text}' (lang={lang})")
            return text
        except ImportError:
            logger.error("SpeechRecognition library not installed.")
            raise RuntimeError("SpeechRecognition library is required for Google STT.")
        except sr.UnknownValueError:
            logger.warning("Google Speech API was unable to understand audio.")
            return ""
        except sr.RequestError as e:
            logger.error(f"Could not request results from Google Speech API; {e}")
            raise
        except Exception as e:
            logger.error(f"Google STT failed: {str(e)}", exc_info=True)
            raise

class WhisperSTT(BaseSTT):
    """
    Faster-Whisper local model implementation.
    Lazy-loads weights to optimize Django start-up.
    """
    _model_instance = None

    @classmethod
    def get_model(cls):
        if cls._model_instance is None:
            try:
                from faster_whisper import WhisperModel
                
                model_size = getattr(settings, 'WHISPER_MODEL_SIZE', 'tiny')
                device = getattr(settings, 'WHISPER_DEVICE', 'cpu')
                compute_type = getattr(settings, 'WHISPER_COMPUTE_TYPE', 'int8')
                
                logger.info(f"Loading Whisper model '{model_size}' on '{device}'...")
                cls._model_instance = WhisperModel(
                    model_size,
                    device=device,
                    compute_type=compute_type
                )
                logger.info("Whisper model successfully loaded.")
            except ImportError:
                logger.error("faster-whisper is not installed. WhisperSTT cannot be initialized.")
                raise RuntimeError("faster-whisper library is required for WhisperSTT.")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {str(e)}")
                raise
        return cls._model_instance

    def transcribe(self, file_path: str, language: str = None) -> str:
        logger.info(f"Transcribing {file_path} using local Whisper...")
        try:
            model = self.get_model()
            
            # Whisper handles English and Hindi automatically via auto-detect.
            # If language is supplied, we force it, otherwise let it auto-detect.
            transcribe_kwargs = {"beam_size": 5}
            if language:
                # Map language codes like 'en-US' or 'hi-IN' to Whisper 'en' or 'hi'
                short_lang = language.split('-')[0]
                transcribe_kwargs["language"] = short_lang
                
            segments, info = model.transcribe(file_path, **transcribe_kwargs)
            
            # Combine segments
            text = " ".join([segment.text for segment in segments]).strip()
            logger.info(f"Whisper transcription successful (detected lang={info.language}): '{text}'")
            return text
        except Exception as e:
            logger.error(f"Whisper transcription failed: {str(e)}", exc_info=True)
            raise

def get_stt_service() -> BaseSTT:
    """
    Factory function returning the configured STT service.
    Falls back to Google STT if Whisper is configured but fails to initialize.
    """
    provider = getattr(settings, 'STT_PROVIDER', 'google')
    
    if provider == 'whisper':
        try:
            # Attempt to retrieve/load model
            WhisperSTT.get_model()
            return WhisperSTT()
        except Exception as e:
            logger.warning(f"Whisper initialization failed. Falling back to Google STT. Error: {str(e)}")
            return GoogleSTT()
    else:
        return GoogleSTT()
