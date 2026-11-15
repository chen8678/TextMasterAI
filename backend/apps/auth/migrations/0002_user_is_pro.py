# Generated manually for Text Master AI Phase 1 (P1-T20)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("custom_auth", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_pro",
            field=models.BooleanField(db_index=True, default=False, verbose_name="PRO 用户"),
        ),
    ]
