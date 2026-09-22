from django.contrib import admin

from .models import Lead, Note, PipelineStage, Task


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
