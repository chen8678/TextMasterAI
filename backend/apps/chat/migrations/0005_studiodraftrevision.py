# Generated manually for P3-T01 studio draft version history

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chat", "0004_studiodraft"),
    ]

    operations = [
        migrations.CreateModel(
            name="StudioDraftRevision",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "revision_index",
                    models.PositiveIntegerField(
                        help_text="保存前草稿的 version，与本条快照内容对应",
                        verbose_name="版本号",
                    ),
                ),
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "draft",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="revisions",
                        to="chat.studiodraft",
                    ),
                ),
            ],
            options={
                "verbose_name": "工作室草稿历史版本",
                "verbose_name_plural": "工作室草稿历史版本",
                "db_table": "studio_draft_revisions",
                "ordering": ["-revision_index", "-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="studiodraftrevision",
            constraint=models.UniqueConstraint(
                fields=("draft", "revision_index"),
                name="uniq_studio_draft_revision_per_version",
            ),
        ),
        migrations.AddIndex(
            model_name="studiodraftrevision",
            index=models.Index(fields=["draft", "-revision_index"], name="studio_draft_rev_draft_idx"),
        ),
    ]
