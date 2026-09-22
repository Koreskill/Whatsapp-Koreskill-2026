# Generated for the initial CRM schema.
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="PipelineStage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True, verbose_name="nombre")),
                ("order", models.PositiveSmallIntegerField(db_index=True, default=0, verbose_name="orden")),
                ("is_active", models.BooleanField(default=True, verbose_name="activo")),
            ],
            options={
                "verbose_name": "etapa del pipeline",
                "verbose_name_plural": "etapas del pipeline",
                "ordering": ("order", "name"),
            },
        ),
        migrations.CreateModel(
            name="Lead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("first_name", models.CharField(max_length=100, verbose_name="nombre")),
                ("last_name", models.CharField(blank=True, max_length=100, verbose_name="apellido")),
                ("phone", models.CharField(blank=True, max_length=40, verbose_name="teléfono")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="email")),
                ("source", models.CharField(blank=True, max_length=100, verbose_name="origen")),
                ("operation", models.CharField(blank=True, choices=[("compra", "Compra"), ("alquiler", "Alquiler"), ("venta", "Venta"), ("tasacion", "Tasación")], max_length=20, verbose_name="operación")),
                ("property_type", models.CharField(blank=True, max_length=100, verbose_name="tipo de propiedad")),
                ("zones", models.TextField(blank=True, verbose_name="zonas")),
                ("bedrooms", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="dormitorios")),
                ("bathrooms", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="baños")),
                ("parking", models.BooleanField(blank=True, null=True, verbose_name="cochera")),
                ("minimum_surface", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="superficie mínima")),
                ("budget_min", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="presupuesto mínimo")),
                ("budget_max", models.DecimalField(blank=True, decimal_places=2, max_digits=15, null=True, validators=[django.core.validators.MinValueValidator(0)], verbose_name="presupuesto máximo")),
                ("currency", models.CharField(blank=True, max_length=3, verbose_name="moneda")),
                ("pets", models.BooleanField(blank=True, null=True, verbose_name="mascotas")),
                ("guarantee", models.CharField(blank=True, max_length=120, verbose_name="garantía")),
                ("estimated_date", models.DateField(blank=True, null=True, verbose_name="fecha estimada")),
                ("urgency", models.CharField(blank=True, choices=[("baja", "Baja"), ("media", "Media"), ("alta", "Alta")], max_length=10, verbose_name="urgencia")),
                ("observations", models.TextField(blank=True, verbose_name="observaciones")),
                ("ai_summary", models.TextField(blank=True, verbose_name="resumen de IA")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creado")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizado")),
                ("last_activity_at", models.DateTimeField(blank=True, db_index=True, null=True, verbose_name="última actividad")),
                ("advisor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_leads", to=settings.AUTH_USER_MODEL, verbose_name="asesor")),
                ("pipeline_stage", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="leads", to="crm.pipelinestage", verbose_name="etapa del pipeline")),
            ],
            options={
                "verbose_name": "lead",
                "verbose_name_plural": "leads",
                "ordering": ("-updated_at",),
            },
        ),
        migrations.CreateModel(
            name="Note",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField(verbose_name="texto")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creada")),
                ("author", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_notes", to=settings.AUTH_USER_MODEL, verbose_name="autor")),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notes", to="crm.lead", verbose_name="lead")),
            ],
            options={
                "verbose_name": "nota",
                "verbose_name_plural": "notas",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="Task",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="título")),
                ("description", models.TextField(blank=True, verbose_name="descripción")),
                ("due_date", models.DateTimeField(verbose_name="fecha de vencimiento")),
                ("completed", models.BooleanField(default=False, verbose_name="realizada")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="creada")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="actualizada")),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="crm_tasks", to=settings.AUTH_USER_MODEL, verbose_name="asignada a")),
                ("lead", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="crm.lead", verbose_name="lead")),
            ],
            options={
                "verbose_name": "tarea",
                "verbose_name_plural": "tareas",
                "ordering": ("completed", "due_date"),
            },
        ),
    ]
