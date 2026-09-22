from django.db import migrations


PLATFORMS = ["whatsapp", "instagram", "messenger"]


def create_agent_configs(apps, schema_editor):
    AgentConfig = apps.get_model("crm", "AgentConfig")
    for platform in PLATFORMS:
        AgentConfig.objects.get_or_create(platform=platform, defaults={"enabled": False})


def remove_agent_configs(apps, schema_editor):
    AgentConfig = apps.get_model("crm", "AgentConfig")
    AgentConfig.objects.filter(platform__in=PLATFORMS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("crm", "0004_agentconfig_webhookevent_conversation_ai_enabled_and_more"),
    ]

    operations = [
        migrations.RunPython(create_agent_configs, remove_agent_configs),
    ]
