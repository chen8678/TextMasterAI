from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("skills", "0003_skill_evolution_mvp"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="skill",
            name="content_hash",
            field=models.CharField(blank=True, db_index=True, max_length=64),
        ),
        migrations.AddField(
            model_name="skill",
            name="lifecycle_status",
            field=models.CharField(
                choices=[
                    ("draft", "草案"),
                    ("active", "已生效"),
                    ("disabled", "已禁用"),
                    ("rolled_back", "已回滚"),
                ],
                db_index=True,
                default="active",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="skill",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="skill",
            name="version",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="skillexecutionlog",
            name="refusal_reason",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name="skillexecutionlog",
            name="retrieval_refs",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="skillexecutionlog",
            name="skill_content_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="skillexecutionlog",
            name="skill_version",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="skillexecutionlog",
            name="trigger_source",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="skillevolutionstaging",
            name="candidate_hash",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="skillevolutionstaging",
            name="candidate_version",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="skillevolutionstaging",
            name="sandbox_note",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="skillevolutionstaging",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "待审核"),
                    ("sandbox_passed", "沙盒通过"),
                    ("sandbox_failed", "沙盒失败"),
                    ("approved", "已批准"),
                    ("rejected", "已拒绝"),
                    ("applied", "已合并"),
                ],
                db_index=True,
                default="pending",
                max_length=16,
            ),
        ),
        migrations.CreateModel(
            name="SkillLifecycleEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("created", "创建"),
                            ("trial_succeeded", "试跑成功"),
                            ("trial_failed", "试跑失败"),
                            ("staged", "进入草案"),
                            ("applied", "应用生效"),
                            ("rolled_back", "回滚"),
                            ("disabled", "禁用"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("from_version", models.PositiveIntegerField(default=0)),
                ("to_version", models.PositiveIntegerField(default=0)),
                ("content_hash", models.CharField(blank=True, max_length=64)),
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
