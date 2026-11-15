# Generated manually for Phase-C G2

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("english_learning", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="EnglishLearningGraphCheckpoint",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("thread_id", models.CharField(db_index=True, max_length=128)),
                ("graph_state", models.JSONField(blank=True, default=dict)),
                ("node_cursor", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="graph_checkpoints",
                        to="english_learning.englishlearningprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "英语学习图 checkpoint",
                "verbose_name_plural": "英语学习图 checkpoints",
                "db_table": "english_learning_graph_checkpoints",
            },
        ),
        migrations.AddConstraint(
            model_name="englishlearninggraphcheckpoint",
            constraint=models.UniqueConstraint(
                fields=("profile", "thread_id"),
                name="uniq_el_graph_checkpoint_profile_thread",
            ),
        ),
    ]
