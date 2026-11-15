"""提出 SCAR 召回策略补丁草案（进入 SkillEvolutionStaging PENDING）。"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.scar.services.strategy_evolution import propose_scar_strategy_patch
from apps.scar.services.strategy_patch import parse_patch_text


class Command(BaseCommand):
    help = "SCAR T6：提出召回策略补丁（仅 Staging，不上线）"

    def add_arguments(self, parser):
        parser.add_argument("--patch-file", required=True, help="JSON 补丁文件路径")
        parser.add_argument("--note", default="")

    def handle(self, *args, **options):
        path = Path(options["patch_file"])
        if not path.is_file():
            raise CommandError(f"文件不存在: {path}")
        try:
            patch = parse_patch_text(path.read_text(encoding="utf-8"))
            staging = propose_scar_strategy_patch(patch, note=options["note"])
        except Exception as e:
            raise CommandError(str(e)) from e
        self.stdout.write(
            self.style.SUCCESS(
                json.dumps(
                    {
                        "staging_id": str(staging.id),
                        "status": staging.status,
                        "skill_id": staging.skill_id,
                        "provenance": staging.provenance,
                    },
                    ensure_ascii=False,
                )
            )
        )
