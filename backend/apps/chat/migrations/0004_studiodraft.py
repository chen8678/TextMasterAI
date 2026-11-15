from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0003_qarecord_agent_id_qarecord_skills_used"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudioDraft",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(blank=True, max_length=200)),
                ("content", models.TextField(blank=True)),
                (
                    "mode",
                    models.CharField(
                        choices=[("novel", "小说"), ("paper", "论文"), ("contract", "合同")],
                        default="novel",
                        max_length=20,
                    ),
                ),
                ("path", models.CharField(blank=True, default="", max_length=255)),
                ("version", models.PositiveIntegerField(default=1)),
                ("is_deleted", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="studio_drafts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "工作室草稿",
                "verbose_name_plural": "工作室草稿",
                "db_table": "studio_drafts",
                "ordering": ["-updated_at"],
            },
        ),
    ]

