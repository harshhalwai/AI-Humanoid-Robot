from django.urls import path
from .views import (
    UploadAudioView,
    ChatView,
    TTSView,
    RobotStatusView,
    AudioDownloadView
)

urlpatterns = [
    # Core Robot REST endpoints
    path('upload_audio/', UploadAudioView.as_view(), name='upload-audio'),
    path('chat/', ChatView.as_view(), name='chat'),
    path('tts/', TTSView.as_view(), name='tts'),
    path('status/', RobotStatusView.as_view(), name='status'),
    
    # Media download endpoint
    path('audio/<str:filename>/', AudioDownloadView.as_view(), name='audio-download'),
]
