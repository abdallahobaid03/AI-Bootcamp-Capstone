from datetime import timedelta
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser

from core.models import ConversationSession, ChatMessage
from core.models import Customer, ConsumptionRecord, Complaint
from django.http import HttpResponse
from xml.sax.saxutils import escape
from rest_framework.response import Response
from core.ai.router import route_message
from core.ai.rag import answer_general_question
import logging

logger = logging.getLogger(__name__)

def is_twilio_request(request) -> bool:
    # Twilio بيبعت هذا الهيدر دايمًا
    return bool(request.META.get("HTTP_X_TWILIO_SIGNATURE"))

def twiml_message(text: str) -> str:
    safe = escape(text or "")
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{safe}</Message></Response>'

def build_response(request, reply: str, http_status: int = 200):
    # لو الطلب جاي من Twilio -> لازم XML
    if is_twilio_request(request):
        return HttpResponse(
            twiml_message(reply),
            content_type="application/xml",
            status=http_status
        )

    # غير هيك (DRF / Postman / اختبارك) -> JSON
    return Response({"reply": reply}, status=http_status)


MENU_TEXT = (
    "تفضل كيف بقدر أخدمك؟\n"
    "1) استفسارات عامة\n"
    "2) استهلاك\n"
    "3) تعديل بيانات\n"
    "4) شكوى\n"
    "0) القائمة\n"
    "اكتب رقم الخيار."
)

ASK_NAME = "تمام. للتأكد من هويتك: اكتب اسمك الأول."
ASK_LAST4 = "حلو. الآن اكتب آخر 4 أرقام من رقم العداد."
VERIFY_SUCCESS = "تم التحقق ✅"
VERIFY_FAIL = "البيانات غير صحيحة ❌ حاول مرة ثانية."

GENERAL_HELP = (
    "استفسارات عامة:\n"
    "- معلومات عن خدمات الطاقة المتجددة\n"
    "- طرق الاشتراك\n"
    "- ساعات الدعم\n"
    "اكتب سؤالك (أو 0 للرجوع للقائمة)."
)


def normalize(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def is_verified(session: ConversationSession) -> bool:
    return bool(session.verified_until and timezone.now() < session.verified_until)


def reset_to_menu(session: ConversationSession):
    session.state = "WAIT_MENU"
    session.pending_intent = ""
    session.verify_first_name = ""
    session.verify_meter_last4 = ""
    session.save(update_fields=["state", "pending_intent", "verify_first_name", "verify_meter_last4"])


def get_customer(user_key: str):
    return Customer.objects.filter(user_key=user_key).first()


def handle_intent(session: ConversationSession, user_key: str) -> str:
    """
    ينفذ intent الحالي (2/3/4) بناءً على session.pending_intent
    وبيحدد الـ state التالي.
    """
    intent = session.pending_intent
    customer = get_customer(user_key)

    if not customer:
        reset_to_menu(session)
        return "ما لقيت حساب مرتبط بهذا الرقم.\n\n" + MENU_TEXT

    # 2) استهلاك
    if intent == "2":
        rec = ConsumptionRecord.objects.filter(customer=customer).order_by("-created_at", "-id").first()
        if not rec:
            reset_to_menu(session)
            return "ما في بيانات استهلاك لهذا الرقم حالياً.\n\n" + MENU_TEXT

        reply = (
            f"استهلاكك ({rec.period_label}): {rec.kwh} kWh\n"
            f"التوفير: {rec.saving_percent}%\n\n"
            + MENU_TEXT
        )
        reset_to_menu(session)
        return reply

    # 3) تعديل بيانات
    if intent == "3":
        session.state = "EDIT_CHOOSE"
        session.save(update_fields=["state"])
        return (
            "بياناتك الحالية:\n"
            f"- الاسم: {customer.first_name}\n"
            f"- الهاتف: {customer.phone or '(غير مسجل)'}\n"
            f"- العنوان: {customer.address or '(غير مسجل)'}\n\n"
            "اكتب:\n"
            "1 لتعديل الهاتف\n"
            "2 لتعديل العنوان\n"
            "0 للرجوع للقائمة"
        )

    # 4) شكوى
    if intent == "4":
        session.state = "COMPLAINT_TEXT"
        session.save(update_fields=["state"])
        return "تمام، اكتب الشكوى الآن (أو 0 للرجوع للقائمة)."

    # fallback
    reset_to_menu(session)
    return MENU_TEXT


class WhatsAppWebhook(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [JSONParser, FormParser, MultiPartParser]  # Twilio form-data + JSON

    def get(self, request):
        return Response({
            "info": "Use POST with From & Body",
            "example_json": {"From": "whatsapp:+962...", "Body": "hi"},
        })

    def post(self, request):
        body = normalize(request.data.get("Body"))
        from_number = normalize(request.data.get("From"))

        if not from_number:
            return build_response(request, "Missing From", http_status=400)

        session, _ = ConversationSession.objects.get_or_create(user_key=from_number)

        # سجّل inbound
        ChatMessage.objects.create(session=session, direction="Customer", message_type="text", text=body)

        logger.info("inbound from=%s state=%s body=%s", from_number, session.state, body[:200])

        # 0) رجوع للقائمة من أي مكان
        if body.lower() in {"0", "menu", "start", "القائمة", "قائمة"}:
            reset_to_menu(session)
            ChatMessage.objects.create(session=session, direction="System", message_type="text", text=MENU_TEXT)
            return build_response(request, MENU_TEXT)

        # =============== STATES ===============

        if session.state == "WAIT_MENU":
            # لو كتب رقم مباشر
            if body in {"1", "2", "3", "4"}:
                mapped = body
            else:
                # نص حر → خلّي الراوتر يقرر
                routed = route_message(body)
                mapped = routed.mapped_option  # "0/1/2/3/4"

            # طبّق الـ mapped
            if mapped == "0":
                reply = MENU_TEXT

            elif mapped == "1":
                session.state = "GENERAL_QA"
                session.pending_intent = ""
                session.save(update_fields=["state", "pending_intent"])
                reply = GENERAL_HELP

            elif mapped in {"2", "3", "4"}:
                session.pending_intent = mapped
                session.save(update_fields=["pending_intent"])

                if is_verified(session):
                    reply = handle_intent(session, from_number)
                else:
                    session.state = "VERIFY_NAME"
                    session.verify_first_name = ""
                    session.verify_meter_last4 = ""
                    session.attempts = 0
                    session.verified_until = None
                    session.save(update_fields=[
                        "state", "verify_first_name", "verify_meter_last4",
                        "attempts", "verified_until"
                    ])
                    reply = ASK_NAME

            else:
                reply = MENU_TEXT


        elif session.state == "GENERAL_QA":
            if body.strip() == "0":
                reply = MENU_TEXT
                reset_to_menu(session)
            else:
                from core.ai.rag import answer_general_question
                reply = f"{answer_general_question(body)}\n\nاكتب سؤال ثاني، أو 0 للرجوع للقائمة."


        elif session.state == "VERIFY_NAME":
            session.verify_first_name = body
            session.state = "VERIFY_LAST4"
            session.save(update_fields=["verify_first_name", "state"])
            reply = ASK_LAST4

        elif session.state == "VERIFY_LAST4":
            last4 = normalize(body)[-4:]
            session.verify_meter_last4 = last4
            session.save(update_fields=["verify_meter_last4"])

            customer = Customer.objects.filter(
                user_key=from_number,
                first_name__iexact=session.verify_first_name,
                meter_last4=last4
            ).first()

            if not customer:
                session.attempts = (session.attempts or 0) + 1
                if session.attempts >= 3:
                    reset_to_menu(session)
                    reply = "حاولت أكثر من مرة. رجعناك للقائمة.\n\n" + MENU_TEXT
                else:
                    session.state = "VERIFY_NAME"
                    session.save(update_fields=["attempts", "state"])
                    reply = f"{VERIFY_FAIL}\n\n{ASK_NAME}"
            else:
                session.verified_until = timezone.now() + timedelta(minutes=14)
                session.state = "AFTER_VERIFY"
                session.save(update_fields=["verified_until", "state"])

                # ✅ نفّذ الطلب مباشرة
                reply = VERIFY_SUCCESS + "\n\n" + handle_intent(session, from_number)

        elif session.state == "AFTER_VERIFY":
            # احتياط لو وصلنا هون لأي سبب
            reply = handle_intent(session, from_number)

        elif session.state == "EDIT_CHOOSE":
            if body == "1":
                session.state = "EDIT_PHONE"
                session.save(update_fields=["state"])
                reply = "اكتب رقم الهاتف الجديد (أو 0 للرجوع للقائمة)."
            elif body == "2":
                session.state = "EDIT_ADDRESS"
                session.save(update_fields=["state"])
                reply = "اكتب العنوان الجديد (أو 0 للرجوع للقائمة)."
            else:
                reply = "اختيار غير صحيح.\nاكتب 1 للهاتف أو 2 للعنوان أو 0 للقائمة."

        elif session.state == "EDIT_PHONE":
            customer = get_customer(from_number)
            if not customer:
                reset_to_menu(session)
                reply = "ما لقيت حساب مرتبط بهذا الرقم.\n\n" + MENU_TEXT
            else:
                customer.phone = body
                customer.save(update_fields=["phone"])
                reset_to_menu(session)
                reply = "تم تحديث رقم الهاتف ✅\n\n" + MENU_TEXT

        elif session.state == "EDIT_ADDRESS":
            customer = get_customer(from_number)
            if not customer:
                reset_to_menu(session)
                reply = "ما لقيت حساب مرتبط بهذا الرقم.\n\n" + MENU_TEXT
            else:
                customer.address = body
                customer.save(update_fields=["address"])
                reset_to_menu(session)
                reply = "تم تحديث العنوان ✅\n\n" + MENU_TEXT

        elif session.state == "COMPLAINT_TEXT":
            customer = get_customer(from_number)
            if not customer:
                reset_to_menu(session)
                reply = "ما لقيت حساب مرتبط بهذا الرقم.\n\n" + MENU_TEXT
            else:
                comp = Complaint.objects.create(customer=customer, text=body, status="OPEN")
                reset_to_menu(session)
                reply = f"تم تسجيل الشكوى ✅ رقمها: {comp.id}\n\n" + MENU_TEXT
        elif session.state == "GENERAL_QA":
            if body.strip() == "0":
                reply = MENU_TEXT
                reset_to_menu(session)
            else:
                reply = f"{answer_general_question(body)}\n\nاكتب سؤال ثاني، أو 0 للرجوع للقائمة."

        else:
            reset_to_menu(session)
            reply = MENU_TEXT

        # سجّل outbound
        ChatMessage.objects.create(session=session, direction="System", message_type="text", text=reply)
        return build_response(request, reply)
