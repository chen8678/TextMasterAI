from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("skills", "0005_skillversionsnapshot"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="SkillSandboxRun",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("status", models.CharField(choices=[("passed", "通过"), ("failed", "失败")], db_index=True, max_length=16)),
                ("source_type", models.CharField(default="user_kb_text", max_length=32)),
                ("source_summary", models.JSONField(blank=True, default=dict)),
                ("used_cases", models.PositiveIntegerField(default=0)),
                ("max_cases", models.PositiveIntegerField(default=0)),
                ("max_rounds", models.PositiveIntegerField(default=0)),
                ("judge_timeout_seconds", models.PositiveIntegerField(default=0)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("candidate_version", models.PositiveIntegerField(default=1)),
                ("candidate_hash", models.CharField(blank=True, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "skill",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sandbox_runs", to="skills.skill"),
                ),
                (
                    "staging",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sandbox_runs",
                        to="skills.skillevolutionstaging",
                    ),
                ),
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
                "verbose_name": "Skill 沙盒试跑记录",
                "verbose_name_plural": "Skill 沙盒试跑记录",
                "db_table": "skill_sandbox_runs",
                "ordering": ["-created_at"],
            },
        ),
    ]
