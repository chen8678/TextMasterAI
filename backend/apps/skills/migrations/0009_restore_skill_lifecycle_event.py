# Generated manually for A2 lifecycle trace evidence.

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("skills", "0008_remove_skillsandboxrun_skill_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SkillLifecycleEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("created", "创建"),
                            ("propose", "生成草案"),
                            ("guard_blocked", "守卫拦截"),
                            ("staged", "进入草案"),
                            ("rejected", "拒绝草案"),
                            ("applied", "合并草案"),
                            ("rolled_back", "回滚"),
                            ("disabled", "禁用"),
                            ("trial_succeeded", "试跑成功"),
                            ("trial_failed", "试跑失败"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("from_version", models.PositiveIntegerField(default=0)),
                ("to_version", models.PositiveIntegerField(default=0)),
                ("content_hash", models.CharField(blank=True, default="", max_length=64)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "skill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lifecycle_events",
                        to="skills.skill",
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
                "db_table": "skill_lifecycle_events",
                "verbose_name": "Skill 生命周期事件",
                "verbose_name_plural": "Skill 生命周期事件",
                "ordering": ["-created_at"],
            },
        ),
    ]
