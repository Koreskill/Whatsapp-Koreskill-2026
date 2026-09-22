"""Recepción de eventos de Zernio (puente WhatsApp/Instagram/Messenger)."""
import hashlib
import hmac
import json

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Conversation, Message


def _valid_signature(raw_body: bytes, signature: str | None) -> bool:
    secret = settings.ZERNIO_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


@csrf_exempt
@require_POST
def zernio_webhook(request):
    signature = request.headers.get("X-Zernio-Signature")
    if not _valid_signature(request.body, signature):
        return HttpResponseForbidden("firma inválida")

    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)

    if payload.get("event") != "message.received":
        return HttpResponse(status=200)

    account = payload.get("account") or {}
    conv = payload.get("conversation") or {}
    message = payload.get("message") or {}

    conversation_id = conv.get("id") or message.get("conversationId")
    if not conversation_id:
        return HttpResponse(status=200)

    conversation, _ = Conversation.objects.get_or_create(
        zernio_conversation_id=conversation_id,
        defaults={
            "platform": account.get("platform") or "",
            "zernio_account_id": account.get("id") or "",
        },
    )

    contact_name = conv.get("participantName") or (message.get("sender") or {}).get(
        "name"
    )
    contact_identifier = conv.get("participantId") or (
        message.get("sender") or {}
    ).get("phoneNumber")
    changed_fields = []
    if contact_name and conversation.contact_name != contact_name:
        conversation.contact_name = contact_name
        changed_fields.append("contact_name")
    if contact_identifier and conversation.contact_identifier != contact_identifier:
        conversation.contact_identifier = contact_identifier
        changed_fields.append("contact_identifier")
    conversation.last_message_at = timezone.now()
    changed_fields.append("last_message_at")
    conversation.save(update_fields=changed_fields)

    zernio_message_id = message.get("id")
    if zernio_message_id:
        sent_at_raw = message.get("sentAt")
        Message.objects.get_or_create(
            zernio_message_id=zernio_message_id,
            defaults={
                "conversation": conversation,
                "direction": Message.Direction.OUT
                if message.get("direction") == "outgoing"
                else Message.Direction.IN,
                "text": message.get("text") or "",
                "sent_at": parse_datetime(sent_at_raw) if sent_at_raw else None,
            },
        )

    return HttpResponse(status=200)
