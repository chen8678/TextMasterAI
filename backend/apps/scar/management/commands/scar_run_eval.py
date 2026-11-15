"""字段题评测：B0/S1/A1/A2（核心逻辑见 services.eval_runner）。"""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.scar.services.eval_runner import run_field_eval
from apps.scar.services.schema_compiler import repo_construction_data_dir


class Command(BaseCommand):
    help = "SCAR：跑字段题集主指标（准确率），不报守卫率"

    def add_arguments(self, parser):
        parser.add_argument("--taskset", default="")
        parser.add_argument(
            "--config",
            default="S1",
            choices=["B0", "S1", "A1", "A2"],
        )
        parser.add_argument("--knowledge-base-id", default="")
        parser.add_argument("--split", default="all", choices=["all", "dev", "heldout"])
        parser.add_argument("--out", default="")

    def handle(self, *args, **options):
        data_dir = repo_construction_data_dir()
        taskset_path = Path(options["taskset"]) if options["taskset"] else data_dir / "eval" / "taskset_v1.json"
        report = run_field_eval(
            config=options["config"],
            split=options["split"],
            knowledge_base_id=options["knowledge_base_id"],
            taskset_path=taskset_path,
        )
        out = options["out"]
        if out:
            Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"wrote {out}"))
        self.stdout.write(
            json.dumps(
                {
                    "config": report["config"],
                    "n": report["n"],
                    "field_accuracy": report["field_accuracy"],
                    "path_hit": report["path_hit"],
                    "knowledge_base_id": report.get("knowledge_base_id"),
                    "b0_mode": report.get("b0_mode"),
                },
                ensure_ascii=False,
            )
        )
