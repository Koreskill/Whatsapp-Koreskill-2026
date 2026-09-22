from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Lead, Note, PipelineStage, Task


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
