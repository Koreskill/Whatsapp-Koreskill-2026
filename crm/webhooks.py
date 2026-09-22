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
    secret = settings.ZERNIO_API_KEY
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


@csrf_exempt
@require_POST
def zernio_webhook(request):
    signature = request.headers.get("X-Zernio-Signature") or request.headers.get(
        "X-Late-Signature"
    )
    if not _valid_signature(request.body, signature):
        return HttpResponseForbidden("firma inválida")

    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)

    account = payload.get("account") or {}
    message = payload.get("message") or {}
    conversation_id = message.get("conversationId")
    if not conversation_id:
        return HttpResponse(status=200)

    conversation, _ = Conversation.objects.get_or_create(
        zernio_conversation_id=conversation_id,
        defaults={
            "platform": account.get("platform") or "",
            "zernio_account_id": account.get("id") or "",
        },
    )

    sender = message.get("sender") or {}
    changed_fields = []
    if sender.get("name") and conversation.contact_name != sender["name"]:
        conversation.contact_name = sender["name"]
        changed_fields.append("contact_name")
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
                if message.get("direction") == "out"
                else Message.Direction.IN,
                "text": message.get("text") or "",
                "sent_at": parse_datetime(sent_at_raw) if sent_at_raw else None,
            },
        )

    return HttpResponse(status=200)
