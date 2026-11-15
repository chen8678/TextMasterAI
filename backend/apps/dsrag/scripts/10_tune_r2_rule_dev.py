#!/usr/bin/env python3
"""P12：dev 上离线扫 τ_rule；可选写回 policy；再跑 test R2-rule。

用法:
  # 1) 先为 dev 落盘仅检索分数（无 LLM）
  .venv/bin/python apps/dsrag/scripts/10_tune_r2_rule_dev.py --prepare-scores
  # 2) 扫 τ + 写 policy + 跑 test
  .venv/bin/python apps/dsrag/scripts/10_tune_r2_rule_dev.py --run-test
"""

from __future__ import annotations

import argparse
import json
import os
import re
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
from apps.dsrag.pipeline import run_r2_rule  # noqa: E402
from apps.dsrag.retrieve_adapter import retrieve_chunks  # noqa: E402
from apps.dsrag.tune_score_threshold import (  # noqa: E402
    choose_tau_rule,
    format_curve_md,
    scan_tau_rule,
)


def _prepare_dev_scores(out_path: Path) -> list[dict]:
    merged = load_merged()
    base = merged["base"]
    taskset = [
        t
        for t in read_jsonl(resolve_path(base["taskset"]))
        if str(t.get("split")) == "dev"
    ]
    rows = []
    for i, case in enumerate(taskset, 1):
        cands = retrieve_chunks(str(case["question"]), base=base)
        row = {
            "id": case["id"],
            "type": case["type"],
            "split": "dev",
            "question": case["question"],
            "retrieve_ids": [c.chunk_id for c in cands],
            "retrieve_scores": [c.score for c in cands],
            "max_retrieve_score": max((c.score for c in cands), default=0.0),
        }
        rows.append(row)
        if i % 20 == 0:
            print(f"retrieve {i}/{len(taskset)}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


def _update_policy(path: Path, tau: float) -> None:
    text = path.read_text(encoding="utf-8")
    if re.search(r"^score_threshold:\s*", text, re.M):
        text = re.sub(r"^score_threshold:\s*.*$", f"score_threshold: {tau}", text, count=1, flags=re.M)
    else:
        text = text.rstrip() + f"\nscore_threshold: {tau}\n"
    note = f"# chosen_tau_rule_dev={tau}  # by 10_tune_r2_rule_dev.py"
    if "chosen_tau_rule_dev=" in text:
        text = re.sub(r"^# chosen_tau_rule_dev=.*$", note, text, count=1, flags=re.M)
    else:
        text = text.rstrip() + "\n" + note + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare-scores", action="store_true")
    ap.add_argument("--scores", default="", help="dev retrieve-only jsonl")
    ap.add_argument("--taus", default="0.05,0.08,0.10,0.12,0.15,0.18,0.20,0.25,0.30")
    ap.add_argument("--run-test", action="store_true")
    ap.add_argument("--no-write-policy", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    merged = load_merged()
    base = merged["base"]
    artifacts = resolve_path(base.get("artifacts_dir") or "SCAR/artifacts/dsrag")
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    scores_path = Path(args.scores) if args.scores else artifacts / f"r2_rule_dev_scores_{day}.jsonl"

    if args.prepare_scores or not scores_path.is_file():
        print("preparing dev retrieve scores…", scores_path)
        rows = _prepare_dev_scores(scores_path)
    else:
        rows = read_jsonl(scores_path)

    taus = [float(x) for x in args.taus.split(",") if x.strip()]
    curve = scan_tau_rule(rows, taus)
    chosen, reason = choose_tau_rule(curve)

    out_dir = artifacts / f"r2_rule_threshold_scan_dev_{day}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "curve.md").write_text(format_curve_md(curve, chosen=chosen, reason=reason), encoding="utf-8")
    (out_dir / "curve.csv").write_text(
        "tau_rule,B_leak_rate,A_false_block_rate,gen_call_rate\n"
        + "\n".join(
            f"{r['tau_rule']},{r['B_leak_rate']},{r['A_false_block_rate']},{r['gen_call_rate']}"
            for r in curve
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "chosen_tau_rule.txt").write_text(f"{chosen}\n", encoding="utf-8")
    (out_dir / "CHOICE.md").write_text(reason + "\n", encoding="utf-8")

    policy_path = Path(__file__).resolve().parents[1] / "configs" / "policy_dev.yaml"
    if not args.no_write_policy:
        _update_policy(policy_path, chosen)

    meta = {
        "chosen_tau_rule": chosen,
        "reason": reason,
        "curve": curve,
        "scores_path": str(scores_path),
        "out_dir": str(out_dir),
    }
    (out_dir / "summary.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(format_curve_md(curve, chosen=chosen, reason=reason))

    if not args.run_test:
        return

    # refresh merged after policy write
    merged = load_merged()
    cases = [
        t
        for t in read_jsonl(resolve_path(merged["base"]["taskset"]))
        if str(t.get("split")) == "test"
    ]
    if args.limit > 0:
        cases = cases[: args.limit]
    run_id = make_run_id("r2-rule", "test", day)
    if args.limit:
        run_id = f"{run_id}_n{args.limit}"
    test_dir = artifacts / run_id
    test_dir.mkdir(parents=True, exist_ok=True)
    pred_path = test_dir / "predictions.jsonl"
    n_gen = 0
    with pred_path.open("w", encoding="utf-8") as f:
        for i, case in enumerate(cases, 1):
            tr = run_r2_rule(case, tau_rule=chosen, merged=merged)
            if tr.generated:
                n_gen += 1
            row = tr.prediction_row()
            row["type"] = case.get("type")
            row["gold_answer"] = case.get("gold_answer")
            row["gold_answerable"] = case.get("answerable")
            row["max_retrieve_score"] = max(tr.retrieve_scores) if tr.retrieve_scores else 0.0
            row["tau_rule"] = chosen
            row["notes"] = tr.notes
            # 为 summarize 复用 answerable_pred 语义
            row["answerable_pred"] = bool(tr.generated)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"[{i}/{len(cases)}] R2-rule {tr.id} gen={tr.generated} status={tr.status}")

    summary = {
        "run_id": run_id,
        "config_id": "R2-rule",
        "split": "test",
        "n": len(cases),
        "n_generated": n_gen,
        "gen_call_rate": round(n_gen / len(cases), 4) if cases else None,
        "tau_rule": chosen,
        "policy_hash": merged["policy_hash"],
        "predictions": str(pred_path),
    }
    (test_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (test_dir / "RUN_NOTE.md").write_text(
        f"# RUN_NOTE · {run_id}\n\n- config: **R2-rule**\n- τ_rule: `{chosen}`\n"
        f"- Gen: {summary['gen_call_rate']}\n- policy_hash: `{merged['policy_hash']}`\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
