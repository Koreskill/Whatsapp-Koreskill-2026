"""Envío de mensajes salientes a través de la API de Zernio."""
import json
import urllib.error
import urllib.request

from django.conf import settings


class ZernioError(Exception):
    """La API de Zernio no pudo enviar el mensaje."""


def _base_url() -> str:
    return getattr(settings, "ZERNIO_BASE_URL", None) or "https://zernio.com/api/v1"


def send_message(conversation_id: str, account_id: str, text: str) -> str:
    """Envía `text` a una conversación de Zernio. Devuelve el id del mensaje."""
    if not settings.ZERNIO_API_KEY:
        raise ZernioError("ZERNIO_API_KEY no está configurada")

    url = f"{_base_url()}/inbox/conversations/{conversation_id}/messages"
    body = json.dumps({"accountId": account_id, "message": text}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.ZERNIO_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        raise ZernioError(f"Zernio respondió {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise ZernioError("No se pudo contactar la API de Zernio") from exc

    data = json.loads(raw) if raw else {}
    message_id = (data.get("message") or {}).get("id") or data.get("id")
    return message_id or ""
