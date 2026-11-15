"""一键跑 B0/S1/A1/A2 并写出 JSON + Markdown 主表（T4.4）+ 标准 artifacts。"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.scar.services.eval_runner import run_field_eval
from apps.scar.services.schema_compiler import repo_construction_data_dir


REPO_ROOT = Path(__file__).resolve().parents[5]
SCAR_ROOT = REPO_ROOT / "SCAR"
TASKSET_SHA256 = "8ca7d7ebd8a27e458990e7cfd9fbd58e23570e73d1e288e6c25a920857539468"
GATE_THRESHOLD = 0.15


class Command(BaseCommand):
    help = "SCAR：一键四配置评测 → reports JSON + 主表 md + 可选 artifacts 归档"

    def add_arguments(self, parser):
        parser.add_argument("--knowledge-base-id", default="")
        parser.add_argument("--split", default="heldout", choices=["all", "dev", "heldout"])
        parser.add_argument("--out-dir", default="")
        parser.add_argument("--tag", default="")
        parser.add_argument(
            "--artifacts",
            action="store_true",
            help="写入 SCAR/artifacts/eval/<tag>/（MANIFEST+PROTOCOL+predictions+scores）",
        )

    def handle(self, *args, **options):
        split = options["split"]
        kb = (options["knowledge_base_id"] or "").strip()
        tag = (options["tag"] or datetime.now(timezone.utc).strftime("%Y%m%d")).strip()
        out_dir = Path(options["out_dir"]) if options["out_dir"] else (SCAR_ROOT / "reports")
        out_dir.mkdir(parents=True, exist_ok=True)
        use_artifacts = bool(options["artifacts"])

        configs = ["B0", "S1", "A1", "A2"]
        reports = {}
        for cfg in configs:
            rep = run_field_eval(config=cfg, split=split, knowledge_base_id=kb)
            reports[cfg] = rep
            cfg_path = out_dir / f"eval_{cfg}_{split}_{tag}.json"
            cfg_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            self.stdout.write(f"wrote {cfg_path}")

        delta = reports["S1"]["field_accuracy"] - reports["B0"]["field_accuracy"]
        gate_passed = bool(split == "heldout" and delta >= GATE_THRESHOLD)
        code_version = self._git_head()
        generated_at = datetime.now(timezone.utc).isoformat()
        b0_mode = reports["B0"].get("b0_mode")

        summary = {
            "experiment_id": tag,
            "tag": tag,
            "split": split,
            "knowledge_base_id": kb or None,
            "generated_at": generated_at,
            "timestamp": generated_at,
            "taskset": str(repo_construction_data_dir() / "eval" / "taskset_v1.json"),
            "taskset_id": "taskset_v1",
            "taskset_sha256": TASKSET_SHA256,
            "n_heldout": reports["S1"].get("n") if split == "heldout" else None,
            "code_version": code_version,
            "b0_mode": b0_mode,
            "gate_threshold": GATE_THRESHOLD,
            "gate_passed": gate_passed if split == "heldout" else None,
            "configs": {
                c: {
                    "n": reports[c]["n"],
                    "field_accuracy": reports[c]["field_accuracy"],
                    "path_hit": reports[c]["path_hit"],
                    "error_buckets": reports[c].get("error_buckets"),
                    "b0_mode": reports[c].get("b0_mode"),
                }
                for c in configs
            },
            "field_acc": {c: reports[c]["field_accuracy"] for c in configs},
            "path_hit": {c: reports[c]["path_hit"] for c in configs},
            "delta_s1_minus_b0_field_accuracy": delta,
            "delta_field_acc_S1_B0": delta,
            "note": (
                "主指标仅 Field Acc / Path Hit；error_buckets 为错误分析附录。"
                "论文主表仅认库内 B0（见 PROTOCOL）；离线启发式不得入主表。"
            ),
            "protocol_version": "1.0",
        }
        summary_path = out_dir / f"eval_main_{split}_{tag}.json"
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        md = self._render_main_table(summary)
        md_path = out_dir / f"eval_main_{split}_{tag}.md"
        md_path.write_text(md, encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"wrote {summary_path}\nwrote {md_path}"))

        if use_artifacts:
            art_root = self._write_artifacts(tag=tag, split=split, reports=reports, summary=summary)
            self.stdout.write(self.style.SUCCESS(f"artifacts: {art_root}"))

        self.stdout.write(
            json.dumps(
                {
                    "delta_s1_b0": delta,
                    "gate_passed": summary.get("gate_passed"),
                    "S1": summary["configs"]["S1"]["field_accuracy"],
                    "B0": summary["configs"]["B0"]["field_accuracy"],
                    "b0_mode": b0_mode,
                },
                ensure_ascii=False,
            )
        )

    def _git_head(self) -> str | None:
        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(REPO_ROOT),
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            return None

    def _write_artifacts(self, *, tag: str, split: str, reports: dict, summary: dict) -> Path:
        art = SCAR_ROOT / "artifacts" / "eval" / tag
        pred_dir = art / "predictions"
        scores_dir = art / "scores" / "per_config"
        pred_dir.mkdir(parents=True, exist_ok=True)
        scores_dir.mkdir(parents=True, exist_ok=True)

        # PROTOCOL 副本
        proto_src = SCAR_ROOT / "docs" / "PROTOCOL.md"
        if proto_src.is_file():
            shutil.copy2(proto_src, art / "PROTOCOL.md")

        # MANIFEST：基线 yaml + run 字段覆盖
        base_manifest = SCAR_ROOT / "data" / "construction" / "eval" / "MANIFEST.yaml"
        run_block = {
            "experiment_id": tag,
            "split": split,
            "knowledge_base_id": summary.get("knowledge_base_id"),
            "b0_mode": summary.get("b0_mode"),
            "code_version": summary.get("code_version"),
            "timestamp": summary.get("timestamp"),
            "gate_passed": summary.get("gate_passed"),
            "delta_field_acc_S1_B0": summary.get("delta_field_acc_S1_B0"),
            "gate_threshold": summary.get("gate_threshold"),
            "field_acc": summary.get("field_acc"),
            "path_hit": summary.get("path_hit"),
        }
        if base_manifest.is_file():
            text = base_manifest.read_text(encoding="utf-8")
            # 追加 run 快照（YAML 友好：尾部覆盖块）
            run_yaml = "\n# --- run snapshot (auto) ---\nrun:\n"
            for k, v in run_block.items():
                if isinstance(v, str):
                    run_yaml += f'  {k}: "{v}"\n'
                elif v is None:
                    run_yaml += f"  {k}: null\n"
                elif isinstance(v, bool):
                    run_yaml += f"  {k}: {'true' if v else 'false'}\n"
                elif isinstance(v, dict):
                    run_yaml += f"  {k}:\n"
                    for kk, vv in v.items():
                        run_yaml += f"    {kk}: {vv}\n"
                else:
                    run_yaml += f"  {k}: {v}\n"
            # 去掉模板末尾空 run: 块再追加
            marker = "\n# 正式跑批时由 scar_run_main_eval"
            if marker in text:
                text = text.split(marker)[0].rstrip() + "\n"
            (art / "MANIFEST.yaml").write_text(text + "\n" + run_yaml, encoding="utf-8")
        else:
            (art / "MANIFEST.yaml").write_text(
                json.dumps({"run": run_block}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        for cfg, rep in reports.items():
            # per-config full json
            (scores_dir / f"{cfg}.json").write_text(
                json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            # predictions jsonl
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
                            "error_bucket": row.get("error_bucket"),
                            "notes": row.get("notes"),
                        },
                        ensure_ascii=False,
                    )
                )
            (pred_dir / f"{cfg}.jsonl").write_text(
                ("\n".join(lines) + ("\n" if lines else "")), encoding="utf-8"
            )

        (art / "scores" / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (art / "scores" / "main_table.md").write_text(
            self._render_main_table(summary), encoding="utf-8"
        )
        return art

    def _render_main_table(self, summary: dict) -> str:
        lines = [
            "# SCAR 主结果表",
            "",
            f"- protocol_version: `{summary.get('protocol_version', '1.0')}`",
            f"- split: `{summary['split']}`",
            f"- tag / experiment_id: `{summary['tag']}`",
            f"- knowledge_base_id: `{summary.get('knowledge_base_id')}`",
            f"- b0_mode: `{summary.get('b0_mode')}`",
            f"- taskset_sha256: `{summary.get('taskset_sha256')}`",
            f"- code_version: `{summary.get('code_version')}`",
            f"- generated_at: `{summary['generated_at']}`",
            "",
            "> 主指标仅 Field Accuracy / Path Hit；**不含**守卫 Block Recall。",
            "> 论文主表仅认**库内 B0**（PROTOCOL）；离线启发式不得入主表。",
            "",
            "| 配置 | n | Field Acc | Path Hit |",
            "|------|---|-----------|----------|",
        ]
        for c in ["B0", "S1", "A1", "A2"]:
            cfg = summary["configs"][c]
            lines.append(
                f"| {c} | {cfg['n']} | {cfg['field_accuracy']:.4f} | {cfg['path_hit']:.4f} |"
            )
        delta = summary["delta_s1_minus_b0_field_accuracy"]
        gate = summary.get("gate_passed")
        gate_s = {True: "PASS", False: "FAIL", None: "n/a"}.get(gate, "n/a")
        lines.extend(
            [
                "",
                f"**Δ(S1−B0) Field Acc = {delta:.4f}**（门禁 ≥ {summary.get('gate_threshold', GATE_THRESHOLD)} → **{gate_s}**）",
                "",
                "## 错误分析桶（附录）",
                "",
            ]
        )
        for c in ["B0", "S1", "A1", "A2"]:
            buckets = summary["configs"][c].get("error_buckets") or {}
            lines.append(f"### {c}")
            lines.append("")
            lines.append("| bucket | count |")
            lines.append("|--------|-------|")
            for k, v in buckets.items():
                lines.append(f"| {k} | {v} |")
            lines.append("")
        return "\n".join(lines) + "\n"
