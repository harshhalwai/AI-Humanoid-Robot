import logging
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework import exceptions

logger = logging.getLogger('app')

class RobotAPIKeyAuthentication(authentication.BaseAuthentication):
    """
    Custom API Key authentication for the ESP32 robot and test clients.
    Looks for the key in:
    1. Header: X-Robot-API-Key: <key>
    2. Header: Authorization: Robot-Key <key>
    3. Query parameter: ?api_key=<key>
    """
    def authenticate(self, request):
        api_key = request.headers.get('X-Robot-API-Key')
        
        # 1. Fallback to query parameter (useful for quick browser tests)
        if not api_key:
            api_key = request.query_params.get('api_key')
            
        # 2. Fallback to Authorization Header (standard style)
        if not api_key:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Robot-Key '):
                parts = auth_header.split(' ')
                if len(parts) == 2:
                    api_key = parts[1]
                    
        # If no key is provided, defer to other authentication systems (or return None to fail)
        if not api_key:
            return None

        # Verify key against setting
        expected_key = getattr(settings, 'ROBOT_API_KEY', 'robot-secret-api-key-987654321')
        if api_key != expected_key:
            logger.warning("Robot API Authentication failed: Invalid token received.")
            raise exceptions.AuthenticationFailed('Invalid Robot API Key')

        # Return authenticated user
        try:
            # Try to get or create the robot client user in the DB
            user, _ = User.objects.get_or_create(
                username='robot_client',
                defaults={
                    'is_active': True,
                    'first_name': 'Humanoid',
                    'last_name': 'Robot'
                }
            )
            return (user, None)
        except Exception as e:
            logger.warning(f"Database error during user fetch (using mock user): {str(e)}")
            
            # Safe fallback if DB migrations haven't run yet
            from django.contrib.auth.models import AnonymousUser
            class AuthenticatedRobotUser(AnonymousUser):
                @property
                def is_authenticated(self):
                    return True
            
            return (AuthenticatedRobotUser(), None)
