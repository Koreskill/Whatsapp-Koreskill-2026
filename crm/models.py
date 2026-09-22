from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class PipelineStage(models.Model):
    name = models.CharField("nombre", max_length=80, unique=True)
    order = models.PositiveSmallIntegerField("orden", default=0, db_index=True)
    is_active = models.BooleanField("activo", default=True)

    class Meta:
        ordering = ("order", "name")
        verbose_name = "etapa del pipeline"
        verbose_name_plural = "etapas del pipeline"

    def __str__(self):
        return self.name


class Lead(models.Model):
    class Operation(models.TextChoices):
        PURCHASE = "compra", "Compra"
        RENT = "alquiler", "Alquiler"
        SALE = "venta", "Venta"
        APPRAISAL = "tasacion", "Tasación"

    class Urgency(models.TextChoices):
        LOW = "baja", "Baja"
        MEDIUM = "media", "Media"
        HIGH = "alta", "Alta"

    first_name = models.CharField("nombre", max_length=100)
    last_name = models.CharField("apellido", max_length=100, blank=True)
    phone = models.CharField("teléfono", max_length=40, blank=True)
    email = models.EmailField("email", blank=True)
    source = models.CharField("origen", max_length=100, blank=True)
    advisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="asesor",
        related_name="assigned_leads",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    pipeline_stage = models.ForeignKey(
        PipelineStage,
        verbose_name="etapa del pipeline",
        related_name="leads",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    operation = models.CharField(
        "operación", max_length=20, choices=Operation.choices, blank=True
    )
    property_type = models.CharField("tipo de propiedad", max_length=100, blank=True)
    zones = models.TextField("zonas", blank=True)
    bedrooms = models.PositiveSmallIntegerField("dormitorios", null=True, blank=True)
    bathrooms = models.PositiveSmallIntegerField("baños", null=True, blank=True)
    parking = models.BooleanField("cochera", null=True, blank=True)
    minimum_surface = models.DecimalField(
        "superficie mínima",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    budget_min = models.DecimalField(
        "presupuesto mínimo",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    budget_max = models.DecimalField(
        "presupuesto máximo",
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField("moneda", max_length=3, blank=True)
    pets = models.BooleanField("mascotas", null=True, blank=True)
    guarantee = models.CharField("garantía", max_length=120, blank=True)
    estimated_date = models.DateField("fecha estimada", null=True, blank=True)
    urgency = models.CharField(
        "urgencia", max_length=10, choices=Urgency.choices, blank=True
    )
    observations = models.TextField("observaciones", blank=True)
    ai_summary = models.TextField("resumen de IA", blank=True)
    created_at = models.DateTimeField("creado", auto_now_add=True)
    updated_at = models.DateTimeField("actualizado", auto_now=True)
    last_activity_at = models.DateTimeField(
        "última actividad", null=True, blank=True, db_index=True
    )

    class Meta:
        ordering = ("-updated_at",)
        verbose_name = "lead"
        verbose_name_plural = "leads"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def clean(self):
        super().clean()
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValidationError(
                {"budget_max": "Debe ser mayor o igual al presupuesto mínimo."}
            )

    def __str__(self):
        return self.full_name


class Task(models.Model):
    lead = models.ForeignKey(
        Lead, verbose_name="lead", related_name="tasks", on_delete=models.CASCADE
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="asignada a",
        related_name="crm_tasks",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    title = models.CharField("título", max_length=200)
    description = models.TextField("descripción", blank=True)
    due_date = models.DateTimeField("fecha de vencimiento")
    completed = models.BooleanField("realizada", default=False)
    created_at = models.DateTimeField("creada", auto_now_add=True)
    updated_at = models.DateTimeField("actualizada", auto_now=True)

    class Meta:
        ordering = ("completed", "due_date")
        verbose_name = "tarea"
        verbose_name_plural = "tareas"

    def __str__(self):
        return self.title


class Note(models.Model):
    lead = models.ForeignKey(
        Lead, verbose_name="lead", related_name="notes", on_delete=models.CASCADE
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="autor",
        related_name="crm_notes",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    text = models.TextField("texto")
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "nota"
        verbose_name_plural = "notas"

    def __str__(self):
        return f"Nota de {self.author or 'sistema'} para {self.lead}"


class Conversation(models.Model):
    class Platform(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        INSTAGRAM = "instagram", "Instagram"
        MESSENGER = "messenger", "Messenger"

    lead = models.ForeignKey(
        Lead,
        verbose_name="lead",
        related_name="conversations",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    zernio_conversation_id = models.CharField(
        "id de conversación en Zernio", max_length=200, unique=True
    )
    zernio_account_id = models.CharField(
        "id de cuenta en Zernio", max_length=200, blank=True
    )
    platform = models.CharField(
        "plataforma", max_length=20, choices=Platform.choices, blank=True
    )
    contact_name = models.CharField("nombre de contacto", max_length=200, blank=True)
    contact_identifier = models.CharField(
        "identificador de contacto", max_length=200, blank=True
    )
    last_message_at = models.DateTimeField(
        "última actividad", null=True, blank=True, db_index=True
    )
    ai_enabled = models.BooleanField(
        "IA activa en esta conversación",
        default=True,
        help_text="Apagalo para que un asesor tome el hilo a mano sin desactivar el canal entero.",
    )
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        ordering = ("-last_message_at",)
        verbose_name = "conversación"
        verbose_name_plural = "conversaciones"

    def __str__(self):
        return self.contact_name or self.contact_identifier or self.zernio_conversation_id

    @property
    def last_message(self):
        """Solo para mostrar una vista previa; no reemplaza `last_message_at`."""
        return self.messages.order_by("-created_at").first()

    @property
    def window_open(self) -> bool:
        """WhatsApp solo permite texto libre dentro de las 24 h del último entrante."""
        last_inbound = (
            self.messages.filter(direction=Message.Direction.IN)
            .order_by("-created_at")
            .first()
        )
        if not last_inbound:
            return False
        reference = last_inbound.sent_at or last_inbound.created_at
        return timezone.now() - reference < timedelta(hours=24)

    @property
    def initials(self) -> str:
        name = (self.contact_name or self.contact_identifier or "?").strip()
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return name[:2].upper()


class Message(models.Model):
    class Direction(models.TextChoices):
        IN = "in", "Entrante"
        OUT = "out", "Saliente"

    conversation = models.ForeignKey(
        Conversation,
        verbose_name="conversación",
        related_name="messages",
        on_delete=models.CASCADE,
    )
    zernio_message_id = models.CharField(
        "id de mensaje en Zernio",
        max_length=200,
        unique=True,
        null=True,
        blank=True,
    )
    direction = models.CharField("dirección", max_length=3, choices=Direction.choices)
    text = models.TextField("texto", blank=True)
    ai_generated = models.BooleanField("generado por IA", default=False)
    sent_at = models.DateTimeField("enviado", null=True, blank=True)
    created_at = models.DateTimeField("recibido", auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        verbose_name = "mensaje"
        verbose_name_plural = "mensajes"

    def __str__(self):
        return f"{self.get_direction_display()}: {self.text[:40]}"


class ContactIdentity(models.Model):
    """Resuelve al mismo lead entre canales que no comparten teléfono.

    WhatsApp casi siempre trae teléfono; Instagram y Messenger no. La
    identidad estable en esos casos es el id que da la plataforma
    (`participantId` de Zernio), no el teléfono.
    """

    lead = models.ForeignKey(
        Lead, verbose_name="lead", related_name="identities", on_delete=models.CASCADE
    )
    platform = models.CharField(
        "plataforma", max_length=20, choices=Conversation.Platform.choices
    )
    external_id = models.CharField("id externo", max_length=200)
    created_at = models.DateTimeField("creada", auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["platform", "external_id"], name="unique_platform_external_id"
            )
        ]
        verbose_name = "identidad de contacto"
        verbose_name_plural = "identidades de contacto"

    def __str__(self):
        return f"{self.platform}:{self.external_id} → {self.lead}"


class WebhookEvent(models.Model):
    """Ficha de idempotencia: reclama un evento por su id antes de procesarlo.

    Zernio entrega at-least-once (puede reintentar el mismo evento). Sin
    esto, un reintento simultáneo podría procesarse dos veces antes de que
    el primero termine de guardar nada.
    """

    event_id = models.CharField("id de evento", max_length=200, primary_key=True)
    provider = models.CharField("proveedor", max_length=20, default="zernio")
    received_at = models.DateTimeField("recibido", auto_now_add=True)

    class Meta:
        verbose_name = "evento de webhook"
        verbose_name_plural = "eventos de webhook"

    def __str__(self):
        return self.event_id


class AgentConfig(models.Model):
    """Configuración del agente de IA, una fila por canal.

    Los canales arrancan apagados a propósito: activarlo por accidente antes
    de revisar el prompt significa contestarle a clientes reales con un
    prompt sin probar.
    """

    platform = models.CharField(
        "plataforma", max_length=20, choices=Conversation.Platform.choices, unique=True
    )
    enabled = models.BooleanField("activo", default=False)
    system_prompt = models.TextField(
        "prompt del sistema",
        blank=True,
        default=(
            "Sos el asistente de una inmobiliaria. Respondé breve y en "
            "español, ayudando a entender qué busca la persona (operación, "
            "zona, presupuesto). No inventes datos de propiedades."
        ),
    )
    model = models.CharField(
        "modelo",
        max_length=100,
        blank=True,
        help_text="Vacío usa el modelo por defecto (OPENAI_MODEL).",
    )

    class Meta:
        verbose_name = "configuración del agente"
        verbose_name_plural = "configuraciones del agente"

    def __str__(self):
        return f"Agente {self.get_platform_display()}"
