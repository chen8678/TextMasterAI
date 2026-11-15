"""审批应用 SCAR 策略补丁：嵌入 heldout Field Accuracy 门禁。"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.scar.services.strategy_evolution import apply_scar_strategy_with_heldout_gate


class Command(BaseCommand):
    help = "SCAR T6：apply 策略补丁（heldout 准确率不下降）"

    def add_arguments(self, parser):
        parser.add_argument("--staging-id", required=True)
        parser.add_argument("--knowledge-base-id", default="", help="门禁评测用 KB")
        parser.add_argument("--epsilon", type=float, default=0.0)
        parser.add_argument(
            "--skip-gate",
            action="store_true",
            help="仅调试：跳过 heldout 门禁（生产勿用）",
        )

    def handle(self, *args, **options):
        result = apply_scar_strategy_with_heldout_gate(
            options["staging_id"],
            knowledge_base_id=options["knowledge_base_id"],
            epsilon=float(options["epsilon"]),
            skip_gate=bool(options["skip_gate"]),
        )
        text = json.dumps(result, ensure_ascii=False, indent=2)
        if result.get("ok"):
            self.stdout.write(self.style.SUCCESS(text))
        else:
            self.stdout.write(self.style.ERROR(text))
            raise CommandError(result.get("error") or "apply_failed")
