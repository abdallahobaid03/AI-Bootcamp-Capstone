import logging
from django.conf import settings

from core.ai.main_llm import get_llm
from core.ai.gmail_sender import send_email
from core.ai.prompt import Prompt

logger = logging.getLogger(__name__)


def build_complaint_email_html(customer, complaint):
    llm = get_llm()

    phone = customer.phone or "(غير مسجل)"

    prompt = Prompt.EMAIL_PROMPT.format(
        complaint_id=complaint.id,
        customer_first_name=customer.first_name,
        phone_number=phone,
        complaint_creation_time=complaint.created_at.strftime("%Y-%m-%d %H:%M"),
        complaint_text=complaint.text,
    )

    html = llm.invoke(prompt).content
    subject = f"New Complaint From #{complaint.id} - {customer.first_name}"
    return subject, html


def send_complaint_to_staff(customer, complaint) -> str:
    to_email = getattr(settings, "RECEIVED_EMAIL", None)
    if not to_email:
        raise RuntimeError("RECEIVED_EMAIL is missing in settings/.env")

    subject, html = build_complaint_email_html(customer, complaint)
    return send_email(to_email=to_email, subject=subject, html_message=html)
