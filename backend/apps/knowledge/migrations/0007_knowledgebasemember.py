from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("knowledge", "0006_document_content_hash"),
    ]

    operations = [
        migrations.CreateModel(
            name="KnowledgeBaseMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("viewer", "只读成员"), ("editor", "编辑成员"), ("admin", "管理成员")], default="viewer", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("knowledge_base", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="knowledge.knowledgebase")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="kb_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "知识库成员",
                "verbose_name_plural": "知识库成员",
                "db_table": "knowledge_base_members",
                "unique_together": {("knowledge_base", "user")},
            },
        ),
    ]

