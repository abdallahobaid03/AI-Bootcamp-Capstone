import tempfile
import requests
from django.conf import settings

# OpenAI official SDK (v1+)
from openai import OpenAI
import os
client = OpenAI(api_key=settings.OPENAI_API_KEY)


def is_voice_message(payload: dict) -> bool:
    """
    Twilio sends: NumMedia, MediaContentType0, MediaUrl0
    """
    try:
        num_media = int(payload.get("NumMedia", "0"))
    except ValueError:
        num_media = 0

    if num_media <= 0:
        return False

    ctype = (payload.get("MediaContentType0") or "").lower()
    return ctype.startswith("audio/")


def download_twilio_media(media_url: str, content_type: str) -> str:
    """
    Download Twilio-hosted media to a temp file and return file path.
    """
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise RuntimeError("Twilio credentials are missing (TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN).")

    # Choose a suffix by content type (WhatsApp voice is often audio/ogg)
    suffix = ".ogg"
    if "mpeg" in content_type or "mp3" in content_type:
        suffix = ".mp3"
    elif "wav" in content_type:
        suffix = ".wav"
    elif "webm" in content_type:
        suffix = ".webm"

    r = requests.get(
        media_url,
        auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
        timeout=30,
    )
    r.raise_for_status()

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(r.content)
    tmp.flush()
    tmp.close()
    return tmp.name


def transcribe_audio_file(file_path: str) -> str:
    """
    Send audio file to OpenAI transcription endpoint and return text.
    """
    model = getattr(settings, "OPENAI_STT_MODEL", "whisper-1")
    with open(file_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model=model,
            file=f,
        )
    # result.text in OpenAI SDK v1
    return (result.text or "").strip()


def transcribe_twilio_voice(payload: dict) -> str:
    media_url = payload.get("MediaUrl0")
    content_type = (payload.get("MediaContentType0") or "audio/ogg").lower()
    if not media_url:
        raise RuntimeError("Missing MediaUrl0 in payload.")

    path = download_twilio_media(media_url, content_type)
    try:
        return transcribe_audio_file(path)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
