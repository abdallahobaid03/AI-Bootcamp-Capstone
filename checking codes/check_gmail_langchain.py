import os
from dotenv import load_dotenv

# LangChain Gmail send tool
from langchain_google_community.gmail.send_message import GmailSendMessage

load_dotenv()

TO_EMAIL = os.getenv("RECEIVED_EMAIL")
if not TO_EMAIL:
    raise RuntimeError("Missing RECEIVED_EMAIL in .env")

# This tool uses token/credentials on disk (token.json + credentials.json)
send_tool = GmailSendMessage()

result = send_tool.run(
    {
        "to": TO_EMAIL,
        "subject": "WhatsApp Complaints Test ✅",
        "message": "هذا اختبار إرسال من LangChain Gmail Tool.\nإذا وصلتك الرسالة، الأمور تمام.",
    }
)

print("RESULT:", result)
