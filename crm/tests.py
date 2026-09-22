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

from . import agent
from .messaging import deliver_message
from .models import (
    AgentConfig,
    ContactIdentity,
    Conversation,
    Lead,
    Message,
    Note,
    PipelineStage,
    Task,
    WebhookEvent,
)
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

    def _incoming_message_payload(self, event_id="evt_1"):
        return {
            "id": event_id,
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

        payload = self._incoming_message_payload(event_id="evt_2")
        payload["message"]["id"] = "msg_2"
        payload["message"]["text"] = "Sigo interesado"
        self._post(payload)

        conversation = Conversation.objects.get(zernio_conversation_id="conv_1")
        self.assertEqual(conversation.messages.count(), 2)
        self.assertEqual(conversation.lead_id, lead_first_time.id)
        self.assertEqual(Lead.objects.filter(phone="+5491111111111").count(), 1)

    @override_settings(ZERNIO_WEBHOOK_SECRET="test-secret")
    def test_retried_event_is_not_processed_twice(self):
        payload = self._incoming_message_payload()

        first = self._post(payload)
        second = self._post(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(WebhookEvent.objects.count(), 1)
        conversation = Conversation.objects.get(zernio_conversation_id="conv_1")
        self.assertEqual(conversation.messages.count(), 1)

    @override_settings(ZERNIO_WEBHOOK_SECRET="test-secret")
    def test_same_person_on_instagram_links_to_existing_lead_by_identity(self):
        self._post(self._incoming_message_payload())
        lead = Conversation.objects.get(zernio_conversation_id="conv_1").lead
        ContactIdentity.objects.create(
            lead=lead, platform="instagram", external_id="ig_juan"
        )

        payload = {
            "id": "evt_ig_1",
            "event": "message.received",
            "message": {
                "id": "msg_ig_1",
                "conversationId": "conv_ig_1",
                "direction": "incoming",
                "text": "Hola desde Instagram",
                "sender": {"name": "Juan Pérez", "id": "ig_juan"},
                "sentAt": "2026-01-01T00:00:00Z",
            },
            "conversation": {
                "id": "conv_ig_1",
                "participantId": "ig_juan",
                "participantName": "Juan Pérez",
            },
            "account": {"id": "acc_ig_1", "platform": "instagram"},
        }
        self._post(payload)

        ig_conversation = Conversation.objects.get(zernio_conversation_id="conv_ig_1")
        self.assertEqual(ig_conversation.lead_id, lead.id)
        self.assertEqual(Lead.objects.count(), 1)


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

    def test_chat_thread_endpoint_reflects_new_messages(self):
        self.client.force_login(self.user)
        Message.objects.create(
            conversation=self.conversation,
            direction=Message.Direction.IN,
            text="Mensaje nuevo que llegó por webhook",
        )

        res = self.client.get(f"/chat/{self.conversation.pk}/thread/")

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Mensaje nuevo que llegó por webhook")

    def test_chat_sidebar_endpoint_marks_active_conversation(self):
        self.client.force_login(self.user)

        res = self.client.get(f"/chat/sidebar/?active={self.conversation.pk}")

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'class="conv-item active"')

    @patch("crm.messaging.send_zernio_message")
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

    @patch("crm.messaging.send_zernio_message", side_effect=ZernioError("401"))
    def test_chat_send_shows_error_without_saving(self, mock_send):
        self.client.force_login(self.user)

        res = self.client.post(f"/chat/{self.conversation.pk}/send/", {"text": "Hola"})

        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "No se pudo enviar")
        self.assertEqual(
            self.conversation.messages.filter(direction=Message.Direction.OUT).count(),
            0,
        )


class DeliverMessageTests(TestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(
            zernio_conversation_id="conv_1", zernio_account_id="acc_1", platform="whatsapp"
        )

    @patch("crm.messaging.send_zernio_message")
    def test_delivers_and_persists_in_one_call(self, mock_send):
        mock_send.return_value = "wamid.xyz"

        message = deliver_message(self.conversation, "Hola", ai_generated=True)

        self.assertEqual(message.zernio_message_id, "wamid.xyz")
        self.assertTrue(message.ai_generated)
        self.assertEqual(message.direction, Message.Direction.OUT)
        self.conversation.refresh_from_db()
        self.assertIsNotNone(self.conversation.last_message_at)

    @patch("crm.messaging.send_zernio_message", side_effect=ZernioError("boom"))
    def test_does_not_persist_when_send_fails(self, mock_send):
        with self.assertRaises(ZernioError):
            deliver_message(self.conversation, "Hola")
        self.assertEqual(self.conversation.messages.count(), 0)


class AgentTests(TestCase):
    def setUp(self):
        self.conversation = Conversation.objects.create(
            zernio_conversation_id="conv_1", zernio_account_id="acc_1", platform="whatsapp"
        )
        Message.objects.create(
            conversation=self.conversation, direction=Message.Direction.IN, text="Hola"
        )

    def test_disabled_channel_does_not_respond(self):
        # El seed deja whatsapp apagado por defecto.
        self.assertIsNone(agent.maybe_respond(self.conversation))

    def test_conversation_switch_overrides_channel(self):
        AgentConfig.objects.filter(platform="whatsapp").update(enabled=True)
        self.conversation.ai_enabled = False
        self.conversation.save(update_fields=["ai_enabled"])

        self.assertIsNone(agent.maybe_respond(self.conversation))

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("crm.agent.deliver_message")
    @patch("crm.agent._openai_reply")
    def test_replies_and_delivers_when_both_switches_on(
        self, mock_reply, mock_deliver
    ):
        AgentConfig.objects.filter(platform="whatsapp").update(enabled=True)
        mock_reply.return_value = "¡Hola! ¿En qué puedo ayudarte?"

        agent.maybe_respond(self.conversation)

        mock_deliver.assert_called_once_with(
            self.conversation, "¡Hola! ¿En qué puedo ayudarte?", ai_generated=True
        )


class PipelineViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="asesor", password="clave-segura-123"
        )
        self.stage_new = PipelineStage.objects.get(name="Nuevo")
        self.stage_contacted = PipelineStage.objects.get(name="Contactado")
        self.lead = Lead.objects.create(first_name="Ana", pipeline_stage=self.stage_new)

    def test_board_requires_login(self):
        res = self.client.get("/pipeline/")
        self.assertEqual(res.status_code, 302)

    def test_board_lists_leads_by_stage(self):
        self.client.force_login(self.user)
        res = self.client.get("/pipeline/")
        self.assertContains(res, "Ana")
        self.assertContains(res, "Nuevo")

    def test_move_lead_updates_stage(self):
        self.client.force_login(self.user)
        res = self.client.post(
            f"/pipeline/leads/{self.lead.pk}/move/",
            {"stage_id": self.stage_contacted.pk},
        )
        self.assertEqual(res.status_code, 204)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.pipeline_stage, self.stage_contacted)


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="asesor", password="clave-segura-123"
        )
        self.stage_new = PipelineStage.objects.get(name="Nuevo")
        self.stage_closed = PipelineStage.objects.get(name="Cerrado")
        self.stage_lost = PipelineStage.objects.get(name="Perdido")
        Lead.objects.create(first_name="Ana", pipeline_stage=self.stage_new)
        Lead.objects.create(first_name="Beto", pipeline_stage=self.stage_closed)
        Lead.objects.create(first_name="Cami", pipeline_stage=self.stage_lost)

    def test_dashboard_requires_login(self):
        res = self.client.get("/dashboard/")
        self.assertEqual(res.status_code, 302)

    def test_dashboard_shows_kpis(self):
        self.client.force_login(self.user)
        res = self.client.get("/dashboard/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Leads totales")
        # 1 ganado de 2 decididos (Cerrado + Perdido) = 50%
        self.assertContains(res, "50%")


class ContactsViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="asesor")
        self.new_stage = PipelineStage.objects.get(name="Nuevo")
        self.closed_stage = PipelineStage.objects.get(name="Cerrado")
        Lead.objects.create(first_name="Ana", last_name="Torres", pipeline_stage=self.new_stage)
        Lead.objects.create(first_name="Bruno", last_name="López", pipeline_stage=self.closed_stage)

    def test_contacts_requires_login(self):
        self.assertEqual(self.client.get("/contactos/").status_code, 302)

    def test_contacts_search_and_stage_filter(self):
        self.client.force_login(self.user)
        response = self.client.get("/contactos/", {"q": "Ana", "stage": self.new_stage.pk})
        self.assertContains(response, "Ana Torres")
        self.assertNotContains(response, "Bruno López")

        response = self.client.get("/contactos/", {"stage": self.closed_stage.pk})
        self.assertContains(response, "Bruno López")
        self.assertNotContains(response, "Ana Torres")
