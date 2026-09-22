"""Agente de IA por canal: contesta solo cuando los dos interruptores están en on."""
import json
import urllib.error
import urllib.request

from django.conf import settings

from .messaging import deliver_message
from .models import AgentConfig, Conversation, Message

MAX_HISTORY = 12
OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


class AgentError(Exception):
    """El agente no pudo generar o mandar una respuesta."""


def _openai_reply(system_prompt: str, model: str, history: list[dict]) -> str:
    if not settings.OPENAI_API_KEY:
        raise AgentError("OPENAI_API_KEY no está configurada")

    body = json.dumps(
        {
            "model": model or settings.OPENAI_MODEL,
            "messages": [{"role": "system", "content": system_prompt}, *history],
        }
    ).encode()
    request = urllib.request.Request(
        OPENAI_CHAT_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        raise AgentError(f"OpenAI respondió {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AgentError("No se pudo contactar la API de OpenAI") from exc

    data = json.loads(raw)
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise AgentError("Respuesta de OpenAI con formato inesperado") from exc


def maybe_respond(conversation: Conversation) -> Message | None:
    """Genera y manda una respuesta si el canal y la conversación lo permiten.

    Doble interruptor, calcado del que pide evitar sorpresas: `AgentConfig`
    tiene que estar activo para esa plataforma, Y `conversation.ai_enabled`
    tiene que seguir prendido en este hilo puntual (un asesor lo apaga para
    tomar la conversación a mano sin afectar al resto del canal).
    """
    if not conversation.ai_enabled:
        return None

    config = AgentConfig.objects.filter(platform=conversation.platform).first()
    if not config or not config.enabled:
        return None

    recent = list(conversation.messages.order_by("-created_at")[:MAX_HISTORY])
    history = [
        {
            "role": "assistant" if m.direction == Message.Direction.OUT else "user",
            "content": m.text,
        }
        for m in reversed(recent)
        if m.text
    ]
    if not history:
        return None

    reply = _openai_reply(config.system_prompt, config.model, history)
    if not reply:
        return None
    return deliver_message(conversation, reply, ai_generated=True)
