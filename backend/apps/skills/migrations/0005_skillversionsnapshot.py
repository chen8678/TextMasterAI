from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("skills", "0004_skill_lifecycle_foundation"),
    ]

    operations = [
        migrations.CreateModel(
            name="SkillVersionSnapshot",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("version", models.PositiveIntegerField(db_index=True)),
                ("content_hash", models.CharField(blank=True, max_length=64)),
                (
                    "lifecycle_status",
                    models.CharField(
                        choices=[
                            ("draft", "草案"),
                            ("active", "已生效"),
                            ("disabled", "已禁用"),
                            ("rolled_back", "已回滚"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("note", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "skill",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="version_snapshots",
                        to="skills.skill",
                    ),
                ),
            ],
            options={
                "verbose_name": "Skill 版本快照",
                "verbose_name_plural": "Skill 版本快照",
                "db_table": "skill_version_snapshots",
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(fields=("skill", "version"), name="uniq_skill_version_snapshot")
                ],
            },
        ),
    ]
