from django.db import models
from django.utils import timezone

class ConversationSession(models.Model):
    user_key = models.CharField(max_length=64, unique=True)
    state = models.CharField(max_length=64, default="WAIT_MENU")
    pending_intent = models.CharField(max_length=16, blank=True, default="")
    verify_first_name = models.CharField(max_length=64, blank=True, default="")
    verify_meter_last4 = models.CharField(max_length=4, blank=True, default="")
    attempts = models.IntegerField(default=0)
    verified_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_verified(self) -> bool:
        return self.verified_until is not None and self.verified_until > timezone.now()
