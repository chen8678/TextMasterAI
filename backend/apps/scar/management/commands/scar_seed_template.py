from django.core.management.base import BaseCommand
from apps.scar.services.ingest import ensure_construction_template


class Command(BaseCommand):
    help = "SCAR：播种 construction active 模板 v1"

    def handle(self, *args, **options):
        tpl = ensure_construction_template()
        self.stdout.write(
            self.style.SUCCESS(
                f"template {tpl.domain_key} v{tpl.version} lifecycle={tpl.lifecycle}"
            )
        )
