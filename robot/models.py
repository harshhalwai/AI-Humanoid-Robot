from django.db import models

class Conversation(models.Model):
    """
    Logs chat interactions, recording what the user said, what the AI replied,
    and linking them via a session_id to maintain contextual history.
    """
    session_id = models.CharField(max_length=100, db_index=True)
    user_message = models.TextField(blank=True, null=True)
    ai_response = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Session {self.session_id} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class RobotStatus(models.Model):
    """
    Maintains status parameters of the robot hardware client (like battery level,
    online status, current state, and last contact timestamp).
    """
    robot_id = models.CharField(max_length=100, default='humanoid_v1', unique=True)
    is_online = models.BooleanField(default=False)
    battery_level = models.FloatField(default=100.0, help_text="Battery percentage (0.0 to 100.0)")
    last_ping = models.DateTimeField(auto_now=True)
    current_mode = models.CharField(max_length=50, default='idle', help_text="Operating mode (e.g. idle, speaking, listening)")

    class Meta:
        verbose_name_plural = "Robot Statuses"

    def __str__(self):
        status_str = "ONLINE" if self.is_online else "OFFLINE"
        return f"Robot {self.robot_id} ({status_str}) - Batt: {self.battery_level}%"


class RobotLog(models.Model):
    """
    Stores system operation logs sent directly by the ESP32 or generated internally
    by the robot server logic.
    """
    robot_id = models.CharField(max_length=100, default='humanoid_v1')
    level = models.CharField(max_length=20, default='INFO', help_text="Log level (INFO, WARNING, DEBUG)")
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.level}] {self.timestamp.strftime('%H:%M:%S')} - {self.message[:50]}"


class ErrorLog(models.Model):
    """
    Database table for tracking system errors, exceptions, stack traces, and modules
    to simplify remote debugging of the humanoid robot.
    """
    module = models.CharField(max_length=100, help_text="Module/App where the error occurred")
    error_message = models.TextField()
    stack_trace = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Error in {self.module} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
