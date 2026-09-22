import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Conversation, Lead, Message, Note, PipelineStage, Task
from .zernio import ZernioError, send_message


class CrmModelsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="asesor")
        self.stage = PipelineStage.objects.get(name="Nuevo")
        self.lead = Lead.objects.create(
            first_name="Juan",
            last_name="Pérez",
            advisor=self.user,
            pipeline_stage=self.stage,
            operation=Lead.Operation.RENT,
        )

    def test_initial_pipeline_stages_are_loaded_in_order(self):
        self.assertEqual(
            list(PipelineStage.objects.values_list("name", flat=True)),
            [
                "Nuevo",
                "Contactado",
                "Calificado",
                "Propiedades enviadas",
                "Visita",
                "Negociación",
                "Cerrado",
                "Perdido",
            ],
        )

    def test_lead_full_name_and_budget_validation(self):
        self.assertEqual(self.lead.full_name, "Juan Pérez")

        self.lead.budget_min = Decimal("800000")
        self.lead.budget_max = Decimal("700000")

        with self.assertRaises(ValidationError):
            self.lead.full_clean()

    def test_task_and_note_are_related_to_lead(self):
        task = Task.objects.create(
            lead=self.lead,
            assigned_to=self.user,
            title="Llamar al cliente",
            due_date=timezone.now() + timedelta(days=1),
        )
        note = Note.objects.create(
            lead=self.lead, author=self.user, text="Prefiere Pichincha."
        )

        self.assertEqual(self.lead.tasks.get(), task)
        self.assertEqual(self.lead.notes.get(), note)


class ZernioWebhookTests(TestCase):
    def _post(self, payload, secret="test-secret"):
        body = json.dumps(payload).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return self.client.post(
            "/webhooks/zernio/",
            data=body,
            content_type="application/json",
            HTTP_X_ZERNIO_SIGNATURE=signature,
        )

    def _incoming_message_payload(self):
        return {
            "event": "message.received",
            "message": {
                "id": "msg_1",
                "conversationId": "conv_1",
                "direction": "incoming",
                "text": "Hola, busco depto",
                "sender": {"name": "Juan Pérez", "phoneNumber": "+5491111111111"},
                "sentAt": "2026-01-01T00:00:00Z",
            },
            "conversation": {
                "id": "conv_1",
                "participantId": "5491111111111",
                "participantName": "Juan Pérez",
            },
            "account": {"id": "acc_1", "platform": "whatsapp"},
        }

    @override_settings(ZERNIO_WEBHOOK_SECRET="test-secret")
    def test_rejects_missing_or_wrong_signature(self):
        res = self.client.post(
            "/webhooks/zernio/",
            data=json.dumps(self._incoming_message_payload()),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 403)

    @override_settings(ZERNIO_WEBHOOK_SECRET="test-secret")
    def test_incoming_message_creates_conversation_and_links_lead(self):
        res = self._post(self._incoming_message_payload())
        self.assertEqual(res.status_code, 200)

        conversation = Conversation.objects.get(zernio_conversation_id="conv_1")
        self.assertEqual(conversation.messages.count(), 1)
        self.assertEqual(conversation.messages.get().text, "Hola, busco depto")
        self.assertIsNotNone(conversation.lead)
        self.assertEqual(conversation.lead.phone, "+5491111111111")
        self.assertEqual(conversation.lead.first_name, "Juan")
        self.assertEqual(conversation.lead.last_name, "Pérez")

    @override_settings(ZERNIO_WEBHOOK_SECRET="test-secret")
    def test_second_message_reuses_same_lead(self):
        self._post(self._incoming_message_payload())
        lead_first_time = Conversation.objects.get(
            zernio_conversation_id="conv_1"
        ).lead

        payload = self._incoming_message_payload()
        payload["message"]["id"] = "msg_2"
        payload["message"]["text"] = "Sigo interesado"
        self._post(payload)

        conversation = Conversation.objects.get(zernio_conversation_id="conv_1")
        self.assertEqual(conversation.messages.count(), 2)
        self.assertEqual(conversation.lead_id, lead_first_time.id)
        self.assertEqual(Lead.objects.filter(phone="+5491111111111").count(), 1)


class SendZernioMessageTests(TestCase):
    @override_settings(ZERNIO_API_KEY="test-key")
    @patch("crm.zernio.urllib.request.urlopen")
    def test_returns_platform_message_id(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"message": {"id": "wamid.123"}}
        ).encode()
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        message_id = send_message("conv_1", "acc_1", "Hola")

        self.assertEqual(message_id, "wamid.123")
        sent_request = mock_urlopen.call_args[0][0]
        self.assertEqual(
            sent_request.get_header("Authorization"), "Bearer test-key"
        )

    @override_settings(ZERNIO_API_KEY=None)
    def test_requires_api_key(self):
        with self.assertRaises(ZernioError):
            send_message("conv_1", "acc_1", "Hola")


class ChatViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="asesor", password="clave-segura-123"
        )
        self.conversation = Conversation.objects.create(
            zernio_conversation_id="conv_1",
            zernio_account_id="acc_1",
            platform="whatsapp",
            contact_name="Juan Pérez",
        )
        Message.objects.create(
            conversation=self.conversation,
            direction=Message.Direction.IN,
            text="Hola, busco depto",
        )

    def test_chat_list_requires_login(self):
        res = self.client.get("/chat/")
        self.assertEqual(res.status_code, 302)

    def test_chat_detail_shows_thread(self):
        self.client.force_login(self.user)
        res = self.client.get(f"/chat/{self.conversation.pk}/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Hola, busco depto")

    @patch("crm.views.send_zernio_message")
    def test_chat_send_creates_outgoing_message(self, mock_send):
        mock_send.return_value = "wamid.abc"
        self.client.force_login(self.user)

        res = self.client.post(
            f"/chat/{self.conversation.pk}/send/", {"text": "Hola, en qué te ayudo"}
        )

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Hola, en qué te ayudo")
        message = self.conversation.messages.get(direction=Message.Direction.OUT)
        self.assertEqual(message.zernio_message_id, "wamid.abc")
        mock_send.assert_called_once_with(
            conversation_id="conv_1", account_id="acc_1", text="Hola, en qué te ayudo"
        )

    @patch("crm.views.send_zernio_message", side_effect=ZernioError("401"))
    def test_chat_send_shows_error_without_saving(self, mock_send):
        self.client.force_login(self.user)

        res = self.client.post(f"/chat/{self.conversation.pk}/send/", {"text": "Hola"})

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "No se pudo enviar")
        self.assertEqual(
            self.conversation.messages.filter(direction=Message.Direction.OUT).count(),
            0,
        )
