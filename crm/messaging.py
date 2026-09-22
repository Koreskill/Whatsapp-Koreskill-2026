"""Único camino de salida para mensajes: envía por Zernio y persiste.

Si el admin, la vista de chat y el agente de IA insertaran cada uno el
Message por su lado, un envío que falla a mitad de camino puede dejar un
mensaje guardado que nunca salió, o uno que salió pero no quedó en el
historial. Todos pasan por esta única función.
"""
from django.utils import timezone

from .models import Conversation, Message
from .zernio import send_message as send_zernio_message


def deliver_message(
    conversation: Conversation, text: str, *, ai_generated: bool = False
) -> Message:
    """Manda `text` por Zernio y recién después guarda el Message.

    Propaga `ZernioError` si el envío falla: quien llama decide cómo
    mostrarlo, pero nunca se guarda un mensaje que no salió de verdad.
    """
    message_id = send_zernio_message(
        conversation_id=conversation.zernio_conversation_id,
        account_id=conversation.zernio_account_id,
        text=text,
    )
    message = Message.objects.create(
        conversation=conversation,
        zernio_message_id=message_id or None,
        direction=Message.Direction.OUT,
        text=text,
        ai_generated=ai_generated,
        sent_at=timezone.now(),
    )
    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=["last_message_at"])
    return message
