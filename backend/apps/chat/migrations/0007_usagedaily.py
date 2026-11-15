# Generated manually for P0-08 UsageDaily

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("chat", "0006_alter_studiodraftrevision_revision_index"),
    ]

    operations = [
        migrations.CreateModel(
            name="UsageDaily",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("date", models.DateField(db_index=True)),
                ("ask_count", models.PositiveIntegerField(default=0)),
                ("token_count", models.PositiveIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_daily",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "日问答用量",
                "verbose_name_plural": "日问答用量",
                "db_table": "chat_usage_daily",
            },
        ),
        migrations.AddIndex(
            model_name="usagedaily",
            index=models.Index(fields=["date"], name="chat_usage_daily_date_idx"),
        ),
        migrations.AddConstraint(
            model_name="usagedaily",
            constraint=models.UniqueConstraint(
                fields=("user", "date"), name="uniq_usage_daily_user_date"
            ),
        ),
    ]
