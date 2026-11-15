from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0005_importjob"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="content_hash",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.RunSQL(
            sql=(
                "UPDATE documents "
                "SET content_hash = md5(coalesce(content, '')) "
                "WHERE content_hash = '' OR content_hash IS NULL;"
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]

