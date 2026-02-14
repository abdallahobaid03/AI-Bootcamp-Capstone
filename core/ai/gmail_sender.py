import logging
from django.conf import settings

from langchain_community.tools.gmail.send_message import GmailSendMessage
from langchain_community.tools.gmail.utils import get_gmail_credentials, build_resource_service

logger = logging.getLogger(__name__)

GMAIL_SEND_SCOPE = ["https://www.googleapis.com/auth/gmail.send"]


def get_gmail_tool() -> GmailSendMessage:
    token_file = getattr(settings, "GMAIL_TOKEN_FILE", "token.json")
    creds_file = getattr(settings, "GMAIL_CREDENTIALS_FILE", "credentials.json")

    creds = get_gmail_credentials(
        token_file=token_file,
        client_secrets_file=creds_file,
        scopes=GMAIL_SEND_SCOPE,
    )
    api_resource = build_resource_service(credentials=creds)
    return GmailSendMessage(api_resource=api_resource)


def send_email(to_email: str, subject: str, html_message: str) -> str:
    tool = get_gmail_tool()
    # NOTE: tool expects: message/to/subject  :contentReference[oaicite:2]{index=2}
    result = tool.invoke(
        {"to": to_email, "subject": subject, "message": html_message}
    )
    return str(result)
