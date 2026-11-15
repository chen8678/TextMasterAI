# Generated manually for content safety audit

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("system", "0003_analyticsevent"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContentSafetyEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "direction",
                    models.CharField(
                        choices=[("input", "用户输入"), ("output", "模型输出")],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                ("channel", models.CharField(db_index=True, help_text="如 chat / english_roadmap", max_length=64)),
                ("category", models.CharField(db_index=True, max_length=64)),
                ("category_label", models.CharField(blank=True, default="", max_length=64)),
                ("matched_hint", models.CharField(blank=True, default="", max_length=64)),
                ("blocked", models.BooleanField(db_index=True, default=True)),
                ("text_preview", models.CharField(blank=True, default="", max_length=128)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "内容安全事件",
                "verbose_name_plural": "内容安全事件",
                "db_table": "content_safety_events",
                "ordering": ["-created_at"],
            },
        ),
    ]
