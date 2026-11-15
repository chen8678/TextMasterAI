#!/usr/bin/env python3
"""P07：跑 R2（retrieve → Answerable → 条件生成）。

用法（在 backend/ 下）:
  .venv/bin/python apps/dsrag/scripts/04_run_r2.py --split dev --threshold 0.5
  .venv/bin/python apps/dsrag/scripts/04_run_r2.py --split dev --limit 10
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
from apps.dsrag.pipeline import run_r2  # noqa: E402


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


def _metrics(rows: list[dict]) -> dict:
    def rate(num: int, den: int) -> float | None:
        return round(num / den, 4) if den else None

    n = len(rows)
    n_gen = sum(1 for r in rows if r.get("generated"))
    type_b = [r for r in rows if r.get("type") == "B"]
    type_a = [r for r in rows if r.get("type") == "A"]
    b_leak = sum(1 for r in type_b if r.get("answerable_pred") is True)
    a_block = sum(1 for r in type_a if r.get("answerable_pred") is False)
    short = sum(
        1
        for r in rows
        if "generate_invoked=false" in str(r.get("notes") or r.get("_notes") or "")
    )
    return {
        "n": n,
        "gen_call_rate": rate(n_gen, n),
        "n_generated": n_gen,
        "n_short_circuit": short,
        "B_n": len(type_b),
        "B_leak_rate": rate(b_leak, len(type_b)),  # type=B 且判可答
        "B_leak_n": b_leak,
        "A_n": len(type_a),
        "A_false_block_rate": rate(a_block, len(type_a)),  # type=A 且判不可答
        "A_false_block_n": a_block,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="DS-RAG R2 eval")
    ap.add_argument("--split", default="dev", choices=["dev", "test", "all"])
    ap.add_argument("--threshold", type=float, default=None, help="覆盖 policy answerable_threshold")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out-dir", default="")
    args = ap.parse_args()

    merged = load_merged()
    base = merged["base"]
    policy = merged["policy"]
    τ = float(
        args.threshold
        if args.threshold is not None
        else policy.get("answerable_threshold")
        if policy.get("answerable_threshold") is not None
        else 0.5
    )

    taskset_path = resolve_path(base["taskset"])
    cases = read_jsonl(taskset_path)
    if args.split != "all":
        cases = [r for r in cases if str(r.get("split")) == args.split]
    if args.limit and args.limit > 0:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit(f"no cases for split={args.split}")

    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    run_id = make_run_id("r2", args.split if args.split != "all" else "all", day)
    if args.limit:
        run_id = f"{run_id}_n{args.limit}"
    artifacts_root = resolve_path(base.get("artifacts_dir") or "SCAR/artifacts/dsrag")
    out_dir = Path(args.out_dir) if args.out_dir else artifacts_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    pred_path = out_dir / "predictions.jsonl"
    pred_rows: list[dict] = []
    with pred_path.open("w", encoding="utf-8") as f:
        for i, case in enumerate(cases, 1):
            trace = run_r2(case, threshold=τ, merged=merged)
            row = trace.prediction_row()
            row["type"] = case.get("type")
            row["gold_answer"] = case.get("gold_answer")
            row["gold_answerable"] = case.get("answerable")
            row["threshold"] = τ
            row["notes"] = trace.notes
            pred_rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                f"[{i}/{len(cases)}] {trace.id} type={case.get('type')} "
                f"pred={row.get('answerable_pred')} gen={trace.generated} "
                f"status={trace.status} p={row.get('answerable_prob')}"
            )

    m = _metrics(pred_rows)
    summary = {
        "run_id": run_id,
        "config_id": "R2",
        "split": args.split,
        "threshold": τ,
        "policy_hash": merged["policy_hash"],
        "generator_model": base.get("generator_model"),
        "answerable_model": base.get("answerable_model"),
        "top_k": base.get("top_k"),
        "decision_rule": policy.get("answerable_decision_rule") or "calibrated_prob_threshold",
        "git": _git_short(),
        "predictions": str(pred_path),
        **m,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # 抽检 reason：各取 5 条 A/B
    samples_a = [r for r in pred_rows if r.get("type") == "A"][:5]
    samples_b = [r for r in pred_rows if r.get("type") == "B"][:5]
    sample_lines = ["## reason_short 抽检（前 5 A / 5 B）", ""]
    for tag, samples in (("A", samples_a), ("B", samples_b)):
        sample_lines.append(f"### type={tag}")
        for r in samples:
            sample_lines.append(
                f"- `{r['id']}` pred={r.get('answerable_pred')} p={r.get('answerable_prob')} "
                f"gen={r.get('generated')} · {r.get('answerable_reason')}"
            )
        sample_lines.append("")

    note = f"""# RUN_NOTE · {run_id}

- config_id: **R2**
- split: `{args.split}` n={m['n']}
- τ (answerable_threshold): `{τ}`
- decision_rule: `calibrated_prob_threshold`（p_yes=prob if answerable else 1-prob；pred = p_yes >= τ）
- parse_fail_default: `refuse`
- policy_hash: `{merged["policy_hash"]}`
- git: `{_git_short()}`
- Gen 调用率: **{m['gen_call_rate']}**（n_generated={m['n_generated']}，short_circuit={m['n_short_circuit']}）
- B 漏放: **{m['B_leak_rate']}**（{m['B_leak_n']}/{m['B_n']}）
- A 误拦: **{m['A_false_block_rate']}**（{m['A_false_block_n']}/{m['A_n']}）
- index: 见 `SCAR/data/dsrag/index/meta.yaml`
- predictions: `{pred_path}`

**未**根据 test 调提示或 τ。

{chr(10).join(sample_lines)}
"""
    (out_dir / "RUN_NOTE.md").write_text(note, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 门禁：短路题 generated=false
    bad = [r for r in pred_rows if r.get("answerable_pred") is False and r.get("generated")]
    if bad:
        raise SystemExit(f"FAIL: {len(bad)} short-circuit cases still generated")
    if m["gen_call_rate"] is None:
        raise SystemExit("FAIL: empty run")


if __name__ == "__main__":
    main()
