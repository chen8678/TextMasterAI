"""表2：B0′/S1′ 端到端评测 → artifacts/eval_e2e/<tag>/"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.scar.services.e2e_eval import E2E_GATE, E2E_MODEL, E2E_TEMPERATURE, TASKSET_V2_SHA256, run_e2e_eval

REPO_ROOT = Path(__file__).resolve().parents[5]
SCAR_ROOT = REPO_ROOT / "SCAR"


class Command(BaseCommand):
    help = "SCAR：B0′/S1′ 端到端 heldout 评测（taskset_v2）"

    def add_arguments(self, parser):
        parser.add_argument("--knowledge-base-id", required=True)
        parser.add_argument("--split", default="heldout", choices=["all", "dev", "heldout"])
        parser.add_argument("--tag", default="")
        parser.add_argument("--limit", type=int, default=0, help="调试限题；正式跑批用 0")
        parser.add_argument("--sleep", type=float, default=0.12, help="每题间隔秒，控速")
        parser.add_argument("--artifacts", action="store_true")
        parser.add_argument("--taskset", default="", help="默认 taskset_v2.json")

    def handle(self, *args, **options):
        kb = (options["knowledge_base_id"] or "").strip()
        if not kb:
            raise CommandError("需要 --knowledge-base-id")
        split = options["split"]
        tag = (options["tag"] or datetime.now(timezone.utc).strftime("e2e_%Y%m%d")).strip()
        limit = int(options["limit"] or 0)
        sleep_s = float(options["sleep"] or 0)
        taskset = (options["taskset"] or "").strip() or None

        reports = {}
        for cfg in ("B0_prime", "S1_prime"):

            def _prog(i, n, qid, ok, _cfg=cfg):
                if i == 1 or i % 20 == 0 or i == n:
                    self.stdout.write(f"[{_cfg}] {i}/{n} {qid} field_ok={ok}")

            self.stdout.write(f"running {cfg} ...")
            reports[cfg] = run_e2e_eval(
                config=cfg,
                split=split,
                knowledge_base_id=kb,
                taskset_path=taskset,
                limit=limit,
                sleep_s=sleep_s,
                on_progress=_prog,
            )

        delta = reports["S1_prime"]["field_accuracy"] - reports["B0_prime"]["field_accuracy"]
        gate_passed = bool(split == "heldout" and delta >= E2E_GATE)
        generated_at = datetime.now(timezone.utc).isoformat()
        code_version = self._git_head()

        summary = {
            "experiment_id": tag,
            "table": "e2e",
            "split": split,
            "knowledge_base_id": kb,
            "generated_at": generated_at,
            "timestamp": generated_at,
            "taskset_id": "taskset_v2",
            "taskset_sha256": TASKSET_V2_SHA256,
            "n_heldout": reports["S1_prime"]["n"] if split == "heldout" else None,
            "model": E2E_MODEL,
            "temperature": E2E_TEMPERATURE,
            "code_version": code_version,
            "gate_threshold": E2E_GATE,
            "gate_passed": gate_passed if split == "heldout" else None,
            "field_acc": {
                "B0_prime": reports["B0_prime"]["field_accuracy"],
                "S1_prime": reports["S1_prime"]["field_accuracy"],
            },
            "path_hit": {
                "B0_prime": reports["B0_prime"]["path_hit"],
                "S1_prime": reports["S1_prime"]["path_hit"],
            },
            "raw_llm_parse_field_accuracy": {
                "B0_prime": reports["B0_prime"]["raw_llm_parse_field_accuracy"],
                "S1_prime": reports["S1_prime"]["raw_llm_parse_field_accuracy"],
            },
            "error_buckets": {
                "B0_prime": reports["B0_prime"]["error_buckets"],
                "S1_prime": reports["S1_prime"]["error_buckets"],
            },
            "api_errors": {
                "B0_prime": reports["B0_prime"]["api_errors"],
                "S1_prime": reports["S1_prime"]["api_errors"],
            },
            "llm_backends": {
                "B0_prime": reports["B0_prime"].get("llm_backends"),
                "S1_prime": reports["S1_prime"].get("llm_backends"),
            },
            "delta_field_acc_S1p_B0p": delta,
            "protocol_version": "1.1",
            "note": "主表 Field Acc：B0'=LLM解析；S1'=EvidencePack绑定。附录 raw_llm_parse_*。",
        }

        out_dir = SCAR_ROOT / "reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        summary_path = out_dir / f"eval_e2e_{split}_{tag}.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md = self._render_md(summary)
        md_path = out_dir / f"eval_e2e_{split}_{tag}.md"
        md_path.write_text(md, encoding="utf-8")
        for cfg, rep in reports.items():
            (out_dir / f"eval_{cfg}_{split}_{tag}.json").write_text(
                json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        self.stdout.write(self.style.SUCCESS(f"wrote {summary_path}\nwrote {md_path}"))

        if options["artifacts"]:
            art = self._write_artifacts(tag, split, reports, summary)
            self.stdout.write(self.style.SUCCESS(f"artifacts: {art}"))

        self.stdout.write(
            json.dumps(
                {
                    "delta": delta,
                    "gate_passed": summary.get("gate_passed"),
                    "B0_prime": summary["field_acc"]["B0_prime"],
                    "S1_prime": summary["field_acc"]["S1_prime"],
                },
                ensure_ascii=False,
            )
        )

    def _git_head(self) -> str | None:
        try:
            return (
                subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), stderr=subprocess.DEVNULL)
                .decode()
                .strip()
            )
        except Exception:
            return None

    def _write_artifacts(self, tag: str, split: str, reports: dict, summary: dict) -> Path:
        art = SCAR_ROOT / "artifacts" / "eval_e2e" / tag
        pred = art / "predictions"
        scores = art / "scores" / "per_config"
        pred.mkdir(parents=True, exist_ok=True)
        scores.mkdir(parents=True, exist_ok=True)

        proto = SCAR_ROOT / "docs" / "PROTOCOL.md"
        if proto.is_file():
            shutil.copy2(proto, art / "PROTOCOL.md")
        man = SCAR_ROOT / "data" / "construction" / "eval" / "MANIFEST.yaml"
        if man.is_file():
            run = "\n# --- e2e run snapshot ---\nrun_e2e:\n"
            for k, v in {
                "experiment_id": tag,
                "split": split,
                "knowledge_base_id": summary.get("knowledge_base_id"),
                "model": summary.get("model"),
                "temperature": summary.get("temperature"),
                "gate_passed": summary.get("gate_passed"),
                "delta_field_acc_S1p_B0p": summary.get("delta_field_acc_S1p_B0p"),
                "code_version": summary.get("code_version"),
                "timestamp": summary.get("timestamp"),
            }.items():
                if isinstance(v, str):
                    run += f'  {k}: "{v}"\n'
                elif v is None:
                    run += f"  {k}: null\n"
                elif isinstance(v, bool):
                    run += f"  {k}: {'true' if v else 'false'}\n"
                else:
                    run += f"  {k}: {v}\n"
            text = man.read_text(encoding="utf-8")
            (art / "MANIFEST.yaml").write_text(text.rstrip() + "\n" + run, encoding="utf-8")

        for cfg, rep in reports.items():
            (scores / f"{cfg}.json").write_text(
                json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            lines = []
            for row in rep.get("rows") or []:
                lines.append(
                    json.dumps(
                        {
                            "qid": row.get("qid"),
                            "config": cfg,
                            "split": split,
                            "pred_path": row.get("predicted_path"),
                            "pred_value": row.get("predicted_value"),
                            "gold_path": row.get("gold_path"),
                            "gold_value": row.get("gold_value"),
                            "path_hit": row.get("path_hit"),
                            "field_acc": row.get("field_accuracy"),
                            "raw_field_acc": row.get("raw_field_accuracy"),
                            "error_bucket": row.get("error_bucket"),
                            "notes": row.get("notes"),
                        },
                        ensure_ascii=False,
                    )
                )
            (pred / f"{cfg}.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

        (art / "scores" / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (art / "scores" / "main_table.md").write_text(self._render_md(summary), encoding="utf-8")
        return art

    def _render_md(self, summary: dict) -> str:
        delta = summary["delta_field_acc_S1p_B0p"]
        gate = summary.get("gate_passed")
        gate_s = {True: "PASS", False: "FAIL", None: "n/a"}.get(gate, "n/a")
        lines = [
            "# SCAR 表2 端到端主结果（B0′ / S1′）",
            "",
            f"- protocol_version: `{summary.get('protocol_version')}`",
            f"- split: `{summary['split']}`",
            f"- tag: `{summary['experiment_id']}`",
            f"- knowledge_base_id: `{summary.get('knowledge_base_id')}`",
            f"- model: `{summary.get('model')}` temperature=`{summary.get('temperature')}`",
            f"- taskset_sha256: `{summary.get('taskset_sha256')}`",
            f"- n_heldout: `{summary.get('n_heldout')}`",
            f"- generated_at: `{summary['generated_at']}`",
            "",
            "> 主表：B0′=hybrid+LLM 解析；S1′=EvidencePack **绑定** pred。附录 raw_llm_parse。",
            "",
            "| 配置 | Field Acc | Path Hit | raw LLM parse Field Acc |",
            "|------|-----------|----------|-------------------------|",
        ]
        for c in ("B0_prime", "S1_prime"):
            lines.append(
                f"| {c} | {summary['field_acc'][c]:.4f} | {summary['path_hit'][c]:.4f} | "
                f"{summary['raw_llm_parse_field_accuracy'][c]:.4f} |"
            )
        lines.extend(
            [
                "",
                f"**Δ(S1′−B0′) Field Acc = {delta:.4f}**（门禁 ≥ {summary.get('gate_threshold')} → **{gate_s}**）",
                "",
                "## 错误桶",
                "",
            ]
        )
        for c in ("B0_prime", "S1_prime"):
            lines.append(f"### {c}")
            lines.append("")
            lines.append("| bucket | count |")
            lines.append("|--------|-------|")
            for k, v in (summary.get("error_buckets") or {}).get(c, {}).items():
                lines.append(f"| {k} | {v} |")
            lines.append("")
        return "\n".join(lines) + "\n"
