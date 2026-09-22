from django.contrib import admin, messages
from django.utils import timezone

from .models import Conversation, Lead, Message, Note, PipelineStage, Task
from .zernio import ZernioError, send_message as send_zernio_message


@admin.register(PipelineStage)
class PipelineStageAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active")
    list_editable = ("order", "is_active")
    ordering = ("order", "name")
    search_fields = ("name",)


class NoteInline(admin.TabularInline):
    model = Note
    extra = 0
    fields = ("author", "text", "created_at")
    readonly_fields = ("created_at",)


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ("title", "assigned_to", "due_date", "completed")


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "operation",
        "pipeline_stage",
        "advisor",
        "last_activity_at",
    )
    list_filter = ("operation", "pipeline_stage", "urgency", "advisor")
    search_fields = ("first_name", "last_name", "phone", "email", "zones")
    autocomplete_fields = ("advisor", "pipeline_stage")
    readonly_fields = ("created_at", "updated_at")
    inlines = (TaskInline, NoteInline)
    fieldsets = (
        (
            "Datos personales",
            {
                "fields": (
                    ("first_name", "last_name"),
                    ("phone", "email"),
                    ("source", "advisor"),
                )
            },
        ),
        (
            "Búsqueda inmobiliaria",
            {
                "fields": (
                    ("operation", "property_type"),
                    "zones",
                    ("bedrooms", "bathrooms", "parking"),
                    "minimum_surface",
                    ("budget_min", "budget_max", "currency"),
                    ("pets", "guarantee"),
                    "estimated_date",
                )
            },
        ),
        (
            "Estado",
            {
                "fields": (
                    ("pipeline_stage", "urgency"),
                    "last_activity_at",
                )
            },
        ),
        (
            "Información adicional",
            {"fields": ("observations", "ai_summary")},
        ),
        (
            "Auditoría",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "lead", "assigned_to", "due_date", "completed")
    list_filter = ("completed", "due_date", "assigned_to")
    search_fields = ("title", "description", "lead__first_name", "lead__last_name")
    autocomplete_fields = ("lead", "assigned_to")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ("lead", "author", "created_at")
    search_fields = ("text", "lead__first_name", "lead__last_name")
    autocomplete_fields = ("lead", "author")
    readonly_fields = ("created_at",)


class MessageInline(admin.TabularInline):
    """Historial de solo lectura, con una fila vacía al final para responder.

    Un mensaje nuevo escrito acá siempre es saliente: `ConversationAdmin`
    lo manda por la API de Zernio antes de guardarlo. Los mensajes ya
    guardados quedan de solo lectura para no reescribir el historial.
    """

    model = Message
    extra = 1
    fields = ("direction", "text", "sent_at")
    readonly_fields = ("direction", "sent_at")
    can_delete = False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        "__str__",
        "platform",
        "lead",
        "last_message_at",
    )
    list_filter = ("platform",)
    search_fields = ("contact_name", "contact_identifier", "zernio_conversation_id")
    autocomplete_fields = ("lead",)
    readonly_fields = (
        "zernio_conversation_id",
        "zernio_account_id",
        "created_at",
        "last_message_at",
    )
    inlines = (MessageInline,)

    def save_formset(self, request, form, formset, change):
        if formset.model is not Message:
            super().save_formset(request, form, formset, change)
            return

        for obj in formset.save(commit=False):
            if obj.pk:
                obj.save()
                continue
            obj.direction = Message.Direction.OUT
            obj.sent_at = timezone.now()
            try:
                message_id = send_zernio_message(
                    conversation_id=obj.conversation.zernio_conversation_id,
                    account_id=obj.conversation.zernio_account_id,
                    text=obj.text,
                )
            except ZernioError as exc:
                messages.error(request, f"No se pudo enviar el mensaje: {exc}")
                continue
            obj.zernio_message_id = message_id or None
            obj.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()
