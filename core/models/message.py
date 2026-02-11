from django.db import models
from .session import ConversationSession

class ChatMessage(models.Model):
    DIRECTION_CHOICES = [("in", "in"), ("out", "out")]
    TYPE_CHOICES = [("text", "text"), ("voice", "voice")]

    session = models.ForeignKey(
        ConversationSession, on_delete=models.CASCADE, related_name="messages"
    )
    direction = models.CharField(max_length=8, choices=DIRECTION_CHOICES)
    message_type = models.CharField(max_length=8, choices=TYPE_CHOICES, default="text")
    text = models.TextField(blank=True, default="")
    stt_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
