from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView
)


def home(request):
    return JsonResponse({
        "status": "online",
        "project": "AI Humanoid Robot",
        "version": "1.0.0",
        "server": "Render",
        "ai": "Gemini",
        "message": "AI Humanoid Robot API is running successfully.",
        "endpoints": {
            "chat": "/api/chat/",
            "voice": "/api/voice/",
            "status": "/api/status/",
            "admin": "/admin/"
        }
    })

urlpatterns = [
    path("", home),
    path('admin/', admin.site.urls),
    
    # Core API endpoints
    path('api/', include('api.urls')),
    
    # API Documentation Schema and Interfaces
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Serve media files in development mode
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
