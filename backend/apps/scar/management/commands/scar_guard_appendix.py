"""T6.4：守卫实验附录报告（明确不衡量问答准确率）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand
from io import StringIO


class Command(BaseCommand):
    help = "SCAR T6.4：跑守卫附录评测并标注「不衡量问答准确率」"

    def add_arguments(self, parser):
        parser.add_argument("--skill-id", default="scar_retrieve")
        parser.add_argument("--out", default="")

    def handle(self, *args, **options):
        buf = StringIO()
        # 复用现有守卫评测命令；失败时仍写附录说明
        appendix = {
            "title": "SCAR 守卫实验附录",
            "disclaimer": "本附录仅衡量进化守卫/草案拦截能力，不衡量问答准确率；主指标见 scar_run_eval Field Accuracy / Path Hit。",
            "skill_id": options["skill_id"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "upstream_command": "run_minimal_evolution_eval",
            "note": "T6.4 — 守卫实验仅附录",
        }
        try:
            call_command(
                "run_minimal_evolution_eval",
                skill_id=options["skill_id"],
                stdout=buf,
                stderr=buf,
            )
            appendix["upstream_ok"] = True
            appendix["upstream_stdout"] = buf.getvalue()[-4000:]
        except Exception as e:
            appendix["upstream_ok"] = False
            appendix["upstream_error"] = str(e)
            appendix["upstream_stdout"] = buf.getvalue()[-2000:]

        out = options["out"]
        if not out:
            report_dir = Path(__file__).resolve().parents[5] / "SCAR" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
            out = str(report_dir / f"guard_appendix_{stamp}.json")

        Path(out).write_text(json.dumps(appendix, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"wrote {out}"))
        self.stdout.write(appendix["disclaimer"])
