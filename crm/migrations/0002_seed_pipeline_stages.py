from django.db import migrations


STAGE_NAMES = [
    "Nuevo",
    "Contactado",
    "Calificado",
    "Propiedades enviadas",
    "Visita",
    "Negociación",
    "Cerrado",
    "Perdido",
]


def create_initial_stages(apps, schema_editor):
    PipelineStage = apps.get_model("crm", "PipelineStage")
    for order, name in enumerate(STAGE_NAMES):
        PipelineStage.objects.get_or_create(name=name, defaults={"order": order})


def remove_initial_stages(apps, schema_editor):
    PipelineStage = apps.get_model("crm", "PipelineStage")
    PipelineStage.objects.filter(name__in=STAGE_NAMES).delete()


class Migration(migrations.Migration):
    dependencies = [("crm", "0001_initial")]

    operations = [
        migrations.RunPython(create_initial_stages, remove_initial_stages),
    ]
