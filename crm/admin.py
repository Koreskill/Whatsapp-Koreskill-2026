from django.contrib import admin, messages

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
)
from .zernio import ZernioError


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
        "ai_enabled",
        "last_message_at",
    )
    list_filter = ("platform", "ai_enabled")
    search_fields = ("contact_name", "contact_identifier", "zernio_conversation_id")
    autocomplete_fields = ("lead",)
    readonly_fields = (
        "zernio_conversation_id",
        "zernio_account_id",
        "created_at",
        "last_message_at",
    )
    fields = (
        "lead",
        "platform",
        "ai_enabled",
        "contact_name",
        "contact_identifier",
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
            try:
                deliver_message(obj.conversation, obj.text)
            except ZernioError as exc:
                messages.error(request, f"No se pudo enviar el mensaje: {exc}")
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()


@admin.register(ContactIdentity)
class ContactIdentityAdmin(admin.ModelAdmin):
    list_display = ("lead", "platform", "external_id", "created_at")
    list_filter = ("platform",)
    search_fields = ("external_id", "lead__first_name", "lead__last_name")
    autocomplete_fields = ("lead",)
    readonly_fields = ("created_at",)


@admin.register(AgentConfig)
class AgentConfigAdmin(admin.ModelAdmin):
    list_display = ("platform", "enabled", "model")
    list_editable = ("enabled",)
    fields = ("platform", "enabled", "model", "system_prompt")
    readonly_fields = ("platform",)
