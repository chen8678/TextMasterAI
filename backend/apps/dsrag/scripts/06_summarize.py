#!/usr/bin/env python3
"""P09：对 predictions.jsonl 打分并写 summary。

用法（backend/）:
  .venv/bin/python apps/dsrag/scripts/06_summarize.py \\
    --pred ../SCAR/artifacts/dsrag/r2_dev_20260929/predictions.jsonl \\
    --taskset ../SCAR/data/dsrag/taskset/taskset_v0.jsonl \\
    --split dev --out ../SCAR/artifacts/dsrag/r2_dev_20260929

  # 多 run 合成预检表
  .venv/bin/python apps/dsrag/scripts/06_summarize.py \\
    --pred ../SCAR/artifacts/dsrag/r0_dev_20260929/predictions.jsonl \\
    --pred ../SCAR/artifacts/dsrag/r2_dev_20260929/predictions.jsonl \\
    --split dev --preview-out ../SCAR/artifacts/dsrag/week1_preview_table.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from apps.dsrag.config import load_base_config, resolve_path  # noqa: E402
from apps.dsrag.corpus import read_jsonl  # noqa: E402
from apps.dsrag.summarize import (  # noqa: E402
    render_preview_table,
    summarize_run,
    write_summary_files,
)


def _load_pred(path: Path) -> list[dict]:
    return read_jsonl(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="DS-RAG summarize")
    ap.add_argument("--pred", action="append", required=True, help="predictions.jsonl（可多次）")
    ap.add_argument("--taskset", default="", help="默认读 base.yaml")
    ap.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    ap.add_argument("--out", default="", help="单 pred 时写入该目录；多 pred 时忽略")
    ap.add_argument("--preview-out", default="", help="多配置预检表 Markdown 路径")
    ap.add_argument("--label", action="append", default=[], help="与 --pred 一一对应的表行标签")
    args = ap.parse_args()

    base = load_base_config()
    taskset_path = Path(args.taskset) if args.taskset else resolve_path(base["taskset"])
    taskset = read_jsonl(taskset_path)
    if args.split != "all":
        taskset = [t for t in taskset if str(t.get("split")) == args.split]

    preview_rows: list[dict] = []
    last_summary = None
    for i, pred_s in enumerate(args.pred):
        pred_path = Path(pred_s)
        if not pred_path.is_absolute():
            pred_path = (Path.cwd() / pred_path).resolve()
        preds = _load_pred(pred_path)
        # 若 pred 自带 split 字段则再滤；否则用 taskset id 交集
        label = args.label[i] if i < len(args.label) else None
        cfg = preds[0].get("config_id") if preds else "?"
        thr = preds[0].get("threshold") if preds else None
        if label is None:
            label = f"{cfg}@τ={thr}" if thr is not None else str(cfg)

        meta = {
            "run_id": pred_path.parent.name,
            "config_id": cfg,
            "config_label": label,
            "split": args.split,
            "predictions_path": str(pred_path),
            "taskset_path": str(taskset_path),
            "policy_hash": preds[0].get("policy_hash") if preds else None,
            "threshold": thr,
        }
        summary, scored = summarize_run(predictions=preds, taskset=taskset, meta=meta)
        preview_rows.append(summary)
        last_summary = summary

        out_dir = Path(args.out) if args.out and len(args.pred) == 1 else pred_path.parent
        paths = write_summary_files(summary, out_dir, preview_rows=[summary], scored=scored)
        print(json.dumps({"out": str(out_dir), "summary": summary, "files": {k: str(v) for k, v in paths.items()}}, ensure_ascii=False, indent=2))

    if args.preview_out or len(args.pred) > 1:
        preview_path = Path(args.preview_out) if args.preview_out else (
            resolve_path(base.get("artifacts_dir") or "SCAR/artifacts/dsrag") / "week1_preview_table.md"
        )
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        body = [
            "# DS-RAG 预检表（P09）",
            "",
            f"split=`{args.split}` · taskset=`{taskset_path}`",
            "",
            render_preview_table(preview_rows),
            "",
            "Scope Acc 本周跳过（无 D0）。",
            "",
        ]
        preview_path.write_text("\n".join(body), encoding="utf-8")
        print("preview_table:", preview_path)

    if last_summary is None:
        raise SystemExit("no predictions")


if __name__ == "__main__":
    main()
