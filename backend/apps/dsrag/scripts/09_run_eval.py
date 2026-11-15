#!/usr/bin/env python3
"""P11：统一跑 R0/R1/R2/R3（锁 policy 后建议 --split test 只跑一次）。

用法:
  .venv/bin/python apps/dsrag/scripts/09_run_eval.py --config R3 --split test
  .venv/bin/python apps/dsrag/scripts/09_run_eval.py --config R1 --split test --limit 5
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
from apps.dsrag.pipeline import RUNNERS  # noqa: E402


def _git_short() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT.parent),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, choices=["R0", "R0-prompt", "R1", "R2", "R3", "R2-rule"])
    ap.add_argument("--split", default="test", choices=["dev", "test", "all"])
    ap.add_argument("--taskset", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out-dir", default="")
    ap.add_argument(
        "--index-dir",
        default="",
        help="覆盖 base.yaml index_dir（机制主表用 TF–IDF 路径）",
    )
    ap.add_argument(
        "--answerable-model",
        default="",
        help="覆盖决策模型（D0/D3）；如 lite_rule / deepseek-chat",
    )
    args = ap.parse_args()

    merged = load_merged()
    base = merged["base"]
    if args.index_dir:
        idx = Path(args.index_dir)
        if not idx.is_absolute():
            idx = resolve_path(args.index_dir)
        base["index_dir"] = str(idx)
        base["index_dir_resolved"] = str(idx)
    if args.answerable_model:
        base["answerable_model"] = args.answerable_model.strip()
        # 决策模型变更 → 重算 policy_hash
        from apps.dsrag.config import compute_policy_hash

        merged["policy_hash"] = compute_policy_hash(
            policy=merged["policy"],
            base=base,
            prompt_version=str(merged.get("prompt_version") or "v0"),
        )
    taskset_path = Path(args.taskset) if args.taskset else resolve_path(base["taskset"])
    if not taskset_path.is_absolute():
        taskset_path = (Path.cwd() / taskset_path).resolve()
    cases = read_jsonl(taskset_path)
    if args.split != "all":
        cases = [c for c in cases if str(c.get("split")) == args.split]
    if args.limit > 0:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("no cases")

    runner = RUNNERS[args.config]
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    run_id = make_run_id(args.config.lower(), args.split if args.split != "all" else "all", day)
    if args.limit:
        run_id = f"{run_id}_n{args.limit}"
    if args.answerable_model:
        run_id = f"{run_id}_dec-{args.answerable_model.replace('/', '_')}"
    out_dir = Path(args.out_dir) if args.out_dir else resolve_path(base.get("artifacts_dir") or "SCAR/artifacts/dsrag") / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    pred_path = out_dir / "predictions.jsonl"
    n_gen = 0
    index_dir = base.get("index_dir_resolved") or base.get("index_dir")
    with pred_path.open("w", encoding="utf-8") as f:
        for i, case in enumerate(cases, 1):
            trace = runner(case, merged=merged, index_dir=index_dir)
            if trace.generated:
                n_gen += 1
            row = trace.prediction_row()
            row["type"] = case.get("type")
            row["gold_answer"] = case.get("gold_answer")
            row["gold_answerable"] = case.get("answerable")
            row["gold_in_scope"] = case.get("in_scope")
            row["notes"] = trace.notes
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                f"[{i}/{len(cases)}] {args.config} {trace.id} type={case.get('type')} "
                f"status={trace.status} gen={trace.generated}"
            )

    summary = {
        "run_id": run_id,
        "config_id": args.config,
        "split": args.split,
        "n": len(cases),
        "n_generated": n_gen,
        "gen_call_rate": round(n_gen / len(cases), 4) if cases else None,
        "policy_hash": merged["policy_hash"],
        "taskset": str(taskset_path),
        "index_dir": str(index_dir),
        "answerable_model": base.get("answerable_model"),
        "git": _git_short(),
        "predictions": str(pred_path),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gen_note = ""
    if args.config == "R0-prompt":
        gen_note = (
            "\n## Gen / 拒答解析（口径 A）\n\n"
            "- 凡调用生成 API → `generated=true`（拒答句也计 Gen）\n"
            "- 固定拒答句：`根据现有资料无法回答。` → 规则解析为 not_answerable，用于 B leak / A block / C 实质答案率\n"
            "- 与编排短路语义对齐看 **C_substantive_rate / B_leak_rate**，勿只看 Gen≈1.0\n"
        )
    (out_dir / "RUN_NOTE.md").write_text(
        f"# RUN_NOTE · {run_id}\n\n"
        f"- config: **{args.config}** · split=`{args.split}` n={len(cases)}\n"
        f"- policy_hash: `{merged['policy_hash']}`\n"
        f"- taskset: `{taskset_path}`\n"
        f"- index_dir: `{index_dir}`\n"
        f"- answerable_model: `{base.get('answerable_model')}`\n"
        f"- Gen: {summary['gen_call_rate']}\n"
        f"- git: `{_git_short()}`\n"
        f"- 论文主表：仅当 MANIFEST 声明允许时写入\n"
        f"{gen_note}",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
