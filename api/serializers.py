import os
from rest_framework import serializers

class ChatInputSerializer(serializers.Serializer):
    text = serializers.CharField(
        max_length=1000, 
        required=True, 
        help_text="User text query to be sent to Gemini."
    )
    session_id = serializers.CharField(
        max_length=100, 
        required=False, 
        default="default",
        help_text="Session key to track conversational context."
    )


class ESP32ResponseSerializer(serializers.Serializer):
    """
    Standard format returned by the Django Cloud Server for the ESP32 client.
    """
    reply = serializers.CharField(help_text="Response text from the AI brain.")
    audio_url = serializers.CharField(help_text="Fully qualified URL to download the response MP3 audio.")
    mouth = serializers.BooleanField(help_text="Boolean flag: True if mouth movement is active.")
    eye = serializers.BooleanField(help_text="Boolean flag: True if eye movement is active.")
    head = serializers.BooleanField(help_text="Boolean flag: True if head movement is active.")


class VoiceInputSerializer(serializers.Serializer):
    audio = serializers.FileField(
        required=True,
        help_text="Binary voice audio file (e.g. WAV, MP3, maximum 10MB)."
    )
    session_id = serializers.CharField(
        max_length=100,
        required=False,
        default="default",
        help_text="Session key to track conversational context."
    )

    def validate_audio(self, value):
        # Limit uploads to 10MB to protect server disk space
        MAX_SIZE = 10 * 1024 * 1024
        if value.size > MAX_SIZE:
            raise serializers.ValidationError("Audio file size must not exceed 10MB.")
        
        # Verify file suffix matches accepted types
        allowed_extensions = ['.wav', '.mp3', '.ogg', '.m4a', '.webm', '.raw', '.pcm']
        ext = os.path.splitext(value.name)[1].lower()
        if ext not in allowed_extensions:
            raise serializers.ValidationError(
                f"Unsupported audio format. Supported: {', '.join(allowed_extensions)}"
            )
            
        return value


class TTSInputSerializer(serializers.Serializer):
    text = serializers.CharField(
        max_length=1000,
        required=True,
        help_text="Text to be synthesized into MP3 speech."
    )


class TTSOutputSerializer(serializers.Serializer):
    audio_url = serializers.CharField(help_text="URL to download the synthesized audio.")


class RobotStatusInputSerializer(serializers.Serializer):
    battery_level = serializers.FloatField(
        required=False, 
        min_value=0.0, 
        max_value=100.0,
        help_text="Current battery percentage of the robot."
    )
    current_mode = serializers.CharField(
        max_length=50, 
        required=False,
        help_text="Current mode of the robot."
    )
    is_online = serializers.BooleanField(
        required=False,
        help_text="Online state indicator."
    )
    log_message = serializers.CharField(
        required=False,
        help_text="Optional device log message to save in the database."
    )


class RobotStatusOutputSerializer(serializers.Serializer):
    status = serializers.CharField()
    version = serializers.CharField()
    battery_level = serializers.FloatField()
    is_online = serializers.BooleanField()
    current_mode = serializers.CharField()
    last_ping = serializers.DateTimeField()
