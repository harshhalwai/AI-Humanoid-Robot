import os
import uuid
import logging
import traceback
from django.conf import settings
from django.urls import reverse
from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status, views, permissions
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

from .serializers import (
    ChatInputSerializer,
    ESP32ResponseSerializer,
    VoiceInputSerializer,
    TTSInputSerializer,
    TTSOutputSerializer,
    RobotStatusInputSerializer,
    RobotStatusOutputSerializer
)
from assistant.services import GeminiClient
from voice.services.stt import get_stt_service
from voice.services.tts import get_tts_service
from voice.utils import convert_to_wav
from voice.tasks import trigger_async_audio_cleanup
from robot.commands import generate_commands, get_movement_flags
from robot.models import Conversation, RobotStatus, RobotLog, ErrorLog

logger = logging.getLogger('app')

def log_system_error(module_name: str, exception: Exception):
    """Utility to record error stack traces directly into the database."""
    try:
        stack_trace = traceback.format_exc()
        ErrorLog.objects.create(
            module=module_name,
            error_message=str(exception),
            stack_trace=stack_trace
        )
        logger.error(f"Logged database error for {module_name}: {str(exception)}")
    except Exception as db_err:
        logger.critical(f"Failed to write error to DB log: {str(db_err)}")


@extend_schema_view(
    post=extend_schema(
        summary="Process user voice upload",
        description="Transcribes audio, queries Gemini, generates speech MP3, logs interactions, and returns movement parameters.",
        request=VoiceInputSerializer,
        responses={200: ESP32ResponseSerializer}
    )
)
class UploadAudioView(views.APIView):
    """
    Endpoint: POST /api/upload_audio/
    Accepts an audio file upload, transcribes it, runs Gemini reasoning,
    generates response speech, resolves servo movements, and logs data.
    """
    def post(self, request):
        serializer = VoiceInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        audio_file = serializer.validated_data['audio']
        session_id = serializer.validated_data.get('session_id', 'default')
        
        logger.info(f"Received audio upload '{audio_file.name}' ({audio_file.size} bytes) for session '{session_id}'")
        
        temp_input_path = None
        temp_wav_path = None
        
        try:
            # 1. Write the uploaded audio to a temporary file
            ext = os.path.splitext(audio_file.name)[1].lower()
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_file:
                for chunk in audio_file.chunks():
                    temp_file.write(chunk)
                temp_input_path = temp_file.name
                
            # 2. Resample/Convert to standard PCM WAV format for STT engines
            temp_wav_path = os.path.join(tempfile.gettempdir(), f"robot_stt_{uuid.uuid4().hex}.wav")
            convert_to_wav(temp_input_path, temp_wav_path)
            
            # 3. Transcribe audio to text
            stt_service = get_stt_service()
            transcribed_text = stt_service.transcribe(temp_wav_path)
            
            if not transcribed_text:
                return Response(
                    {"error": "Failed to transcribe any speech from the audio file."},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY
                )
                
            logger.info(f"Transcribed Text: '{transcribed_text}'")
            
            # 4. Fetch response text from Google Gemini
            gemini_client = GeminiClient()
            reply = gemini_client.generate_response(transcribed_text, session_id=session_id)
            
            # 5. Log the interaction to the database
            Conversation.objects.create(
                session_id=session_id,
                user_message=transcribed_text,
                ai_response=reply
            )
            
            # 6. Synthesize reply text to speech MP3
            tts_service = get_tts_service()
            response_filename = f"response_{uuid.uuid4().hex[:12]}.mp3"
            response_filepath = os.path.join(settings.MEDIA_AUDIO_DIR, response_filename)
            
            tts_service.speak(reply, response_filepath)
            
            # 7. Generate absolute download URL for the ESP32
            audio_url = request.build_absolute_uri(
                reverse('audio-download', kwargs={'filename': response_filename})
            )
            
            # 8. Extract motion commands and resolve boolean motor flags
            commands = generate_commands(transcribed_text, reply)
            flags = get_movement_flags(commands)
            
            # 9. Trigger background file cleanup task
            trigger_async_audio_cleanup()
            
            # Format output matching ESP32 requirement
            response_data = {
                "reply": reply,
                "audio_url": audio_url,
                "mouth": flags["mouth"],
                "eye": flags["eye"],
                "head": flags["head"]
            }
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            log_system_error("UploadAudioView", e)
            return Response(
                {"error": "Failed to process voice upload.", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
        finally:
            # Clean up local temporary files
            for path in [temp_input_path, temp_wav_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                        logger.debug(f"Removed temp file: {path}")
                    except Exception as ex:
                        logger.warning(f"Could not delete temp file {path}: {str(ex)}")


@extend_schema_view(
    post=extend_schema(
        summary="Process chat query",
        description="Receives text message, queries Gemini, generates speech MP3, logs interactions, and returns movement parameters.",
        request=ChatInputSerializer,
        responses={200: ESP32ResponseSerializer}
    )
)
class ChatView(views.APIView):
    """
    Endpoint: POST /api/chat/
    Allows text-based interaction, generating text, movement flags,
    and a corresponding voice audio file.
    """
    def post(self, request):
        serializer = ChatInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        text = serializer.validated_data['text']
        session_id = serializer.validated_data.get('session_id', 'default')
        
        logger.info(f"Received chat prompt: '{text}' for session '{session_id}'")
        
        try:
            # 1. Fetch response from Gemini
            client = GeminiClient()
            reply = client.generate_response(text, session_id=session_id)
            
            # 2. Log interaction
            Conversation.objects.create(
                session_id=session_id,
                user_message=text,
                ai_response=reply
            )
            
            # 3. Generate response speech audio file
            tts_service = get_tts_service()
            response_filename = f"response_{uuid.uuid4().hex[:12]}.mp3"
            response_filepath = os.path.join(settings.MEDIA_AUDIO_DIR, response_filename)
            tts_service.speak(reply, response_filepath)
            
            # 4. Generate absolute download URL
            audio_url = request.build_absolute_uri(
                reverse('audio-download', kwargs={'filename': response_filename})
            )
            
            # 5. Extract commands and map movement flags
            commands = generate_commands(text, reply)
            flags = get_movement_flags(commands)
            
            # 6. Trigger background file cleanup task
            trigger_async_audio_cleanup()
            
            response_data = {
                "reply": reply,
                "audio_url": audio_url,
                "mouth": flags["mouth"],
                "eye": flags["eye"],
                "head": flags["head"]
            }
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            log_system_error("ChatView", e)
            return Response(
                {"error": "Failed to process chat query.", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema_view(
    post=extend_schema(
        summary="Convert text to speech",
        description="Generates an audio MP3 for the given text, returning its download link.",
        request=TTSInputSerializer,
        responses={200: TTSOutputSerializer}
    )
)
class TTSView(views.APIView):
    """
    Endpoint: POST /api/tts/
    Independent Text-to-Speech API.
    """
    def post(self, request):
        serializer = TTSInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        text = serializer.validated_data['text']
        
        try:
            tts_service = get_tts_service()
            response_filename = f"tts_{uuid.uuid4().hex[:12]}.mp3"
            response_filepath = os.path.join(settings.MEDIA_AUDIO_DIR, response_filename)
            
            tts_service.speak(text, response_filepath)
            
            audio_url = request.build_absolute_uri(
                reverse('audio-download', kwargs={'filename': response_filename})
            )
            
            # Trigger background cleanup task
            trigger_async_audio_cleanup()
            
            return Response({"audio_url": audio_url}, status=status.HTTP_200_OK)
            
        except Exception as e:
            log_system_error("TTSView", e)
            return Response(
                {"error": "Failed to synthesize speech.", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema_view(
    get=extend_schema(
        summary="Retrieve robot status",
        description="Returns system online status, battery percentage, active mode, and last ping time.",
        responses={200: RobotStatusOutputSerializer}
    ),
    post=extend_schema(
        summary="Update robot status & submit logs",
        description="Updates battery level, mode, and records device log reports in the database.",
        request=RobotStatusInputSerializer,
        responses={200: RobotStatusOutputSerializer}
    )
)
class RobotStatusView(views.APIView):
    """
    Endpoint: GET & POST /api/status/
    GET: Reads the current robot telemetry and server health.
    POST: Updates battery levels, online state, and appends robot logs.
    """
    def get(self, request):
        try:
            status_obj, _ = RobotStatus.objects.get_or_create(robot_id='humanoid_v1')
            
            # Simple threshold check: if last ping was more than 30 seconds ago, mark offline
            threshold = timezone.now() - timezone.timedelta(seconds=30)
            if status_obj.last_ping < threshold and status_obj.is_online:
                status_obj.is_online = False
                status_obj.save()
                
            response_data = {
                "status": "online",
                "version": "1.0",
                "battery_level": status_obj.battery_level,
                "is_online": status_obj.is_online,
                "current_mode": status_obj.current_mode,
                "last_ping": status_obj.last_ping
            }
            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            log_system_error("RobotStatusView_GET", e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        serializer = RobotStatusInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        battery_level = serializer.validated_data.get('battery_level')
        current_mode = serializer.validated_data.get('current_mode')
        is_online = serializer.validated_data.get('is_online', True)
        log_message = serializer.validated_data.get('log_message')
        
        try:
            status_obj, _ = RobotStatus.objects.get_or_create(robot_id='humanoid_v1')
            
            # Update telemetry parameters
            if battery_level is not None:
                status_obj.battery_level = battery_level
            if current_mode is not None:
                status_obj.current_mode = current_mode
                
            status_obj.is_online = is_online
            # Force last_ping update by saving
            status_obj.save()
            
            # Record log message if provided
            if log_message:
                RobotLog.objects.create(
                    robot_id=status_obj.robot_id,
                    level='INFO',
                    message=log_message
                )
                logger.info(f"Robot client log recorded: '{log_message}'")
                
            response_data = {
                "status": "online",
                "version": "1.0",
                "battery_level": status_obj.battery_level,
                "is_online": status_obj.is_online,
                "current_mode": status_obj.current_mode,
                "last_ping": status_obj.last_ping
            }
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            log_system_error("RobotStatusView_POST", e)
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AudioDownloadView(views.APIView):
    """
    Endpoint: GET /api/audio/<str:filename>/
    Serves generated voice MP3 audio files to the public client (ESP32).
    No authentication is enforced here to simplify download requests.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    
    @extend_schema(
        summary="Retrieve response audio MP3 file",
        description="Returns the requested MP3 file binary directly with correct Content-Type header.",
        responses={200: {} }
    )
    def get(self, request, filename):
        file_path = os.path.join(settings.MEDIA_AUDIO_DIR, filename)
        
        # Verify file path is safe to prevent directory traversal attacks
        base_dir = os.path.abspath(settings.MEDIA_AUDIO_DIR)
        target_path = os.path.abspath(file_path)
        
        if not target_path.startswith(base_dir):
            logger.warning(f"Directory traversal attempt detected: {filename}")
            raise Http404("File not found.")
            
        if not os.path.exists(file_path):
            logger.warning(f"Requested audio file not found: {filename}")
            raise Http404("File not found.")
            
        logger.info(f"Serving response audio: {filename}")
        return FileResponse(open(file_path, 'rb'), content_type='audio/mpeg')
