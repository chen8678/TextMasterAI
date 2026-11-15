#!/usr/bin/env python3
"""P06：跑 R0 基线（retrieve → always generate）。

用法（在 backend/ 下）:
  .venv/bin/python apps/dsrag/scripts/03_run_r0.py --split dev
  .venv/bin/python apps/dsrag/scripts/03_run_r0.py --split dev --limit 5
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

# 加载 backend/.env（不依赖 django）
_env = ROOT / ".env"
if _env.is_file():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

from apps.dsrag.config import load_merged, make_run_id, resolve_path  # noqa: E402
from apps.dsrag.corpus import read_jsonl  # noqa: E402
from apps.dsrag.pipeline import run_r0  # noqa: E402


def _git_short() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT.parent),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser(description="DS-RAG R0 eval")
    ap.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    ap.add_argument("--limit", type=int, default=0, help=">0 时只跑前 N 题（冒烟）")
    ap.add_argument("--out-dir", default="", help="覆盖默认 artifacts/dsrag/{run_id}")
    args = ap.parse_args()

    merged = load_merged()
    base = merged["base"]
    taskset_path = resolve_path(base["taskset"])
    rows = read_jsonl(taskset_path)
    if args.split != "all":
        rows = [r for r in rows if str(r.get("split")) == args.split]
    if args.limit and args.limit > 0:
        rows = rows[: args.limit]
    if not rows:
        raise SystemExit(f"no cases for split={args.split}")

    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    run_id = make_run_id("r0", args.split if args.split != "all" else "all", day)
    if args.limit:
        run_id = f"{run_id}_n{args.limit}"
    artifacts_root = resolve_path(base.get("artifacts_dir") or "SCAR/artifacts/dsrag")
    out_dir = Path(args.out_dir) if args.out_dir else artifacts_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    pred_path = out_dir / "predictions.jsonl"
    n_gen = 0
    n_ok = 0
    errors: list[str] = []
    with pred_path.open("w", encoding="utf-8") as f:
        for i, case in enumerate(rows, 1):
            trace = run_r0(case, merged=merged)
            if trace.generated:
                n_gen += 1
            if not (trace.notes or "").startswith("generate_error:"):
                n_ok += 1
            else:
                errors.append(f"{trace.id}:{trace.notes}")
            row = trace.prediction_row()
            # 附带 type 便于后续 P09
            row["type"] = case.get("type")
            row["gold_answer"] = case.get("gold_answer")
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"[{i}/{len(rows)}] {trace.id} gen={trace.generated} ms={trace.latency_ms:.0f} cost={trace.cost_est:.6f}")

    gen_rate = n_gen / len(rows) if rows else 0.0
    summary = {
        "run_id": run_id,
        "config_id": "R0",
        "split": args.split,
        "n": len(rows),
        "n_generated": n_gen,
        "gen_call_rate": round(gen_rate, 4),
        "n_generate_ok": n_ok,
        "n_generate_error": len(errors),
        "policy_hash": merged["policy_hash"],
        "generator_model": base.get("generator_model"),
        "top_k": base.get("top_k"),
        "temperature": base.get("temperature"),
        "max_tokens": base.get("max_tokens"),
        "git": _git_short(),
        "predictions": str(pred_path),
        "errors_sample": errors[:10],
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    note = f"""# RUN_NOTE · {run_id}

- config_id: **R0**
- split: `{args.split}`（n={len(rows)}{' limited' if args.limit else ''}）
- generator_model: `{base.get("generator_model")}`
- temperature: `{base.get("temperature")}` · max_tokens: `{base.get("max_tokens")}`
- top_k: `{base.get("top_k")}`
- policy_hash: `{merged["policy_hash"]}`
- git: `{_git_short()}`
- Gen 调用率: **{gen_rate:.2f}**（期望 1.00）
- generate_ok: {n_ok}/{len(rows)} · errors: {len(errors)}
- index: 见 `SCAR/data/dsrag/index/meta.yaml`（若 backend=tfidf 须在 RUN 注明）
- predictions: `{pred_path}`

## 口径

- R0：检索后**始终**调用 generate；`generated=true`，`status=answer`
- cost_est：单题估算 USD（DeepSeek 粗略单价）；汇总 $/k 留待 P09
- 本 run **未**调 Answerable / Scope（S7+）
"""
    (out_dir / "RUN_NOTE.md").write_text(note, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if gen_rate < 1.0:
        raise SystemExit("FAIL: gen_call_rate < 1.0")
    if errors and n_ok == 0:
        raise SystemExit("FAIL: all generate calls errored")


if __name__ == "__main__":
    main()
