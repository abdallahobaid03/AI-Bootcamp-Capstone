from django.urls import path
from core.views import WhatsAppWebhook

urlpatterns = [
    path("whatsapp/webhook/", WhatsAppWebhook.as_view(), name="whatsapp-webhook"),
]
