#!/usr/bin/env python3
"""P08：仅在 dev 上离线扫描 Answerable τ，写回 policy_dev.yaml。

用法（backend/）:
  .venv/bin/python apps/dsrag/scripts/05_tune_threshold_dev.py \\
    --pred ../SCAR/artifacts/dsrag/r2_dev_20260929/predictions.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from apps.dsrag.config import compute_policy_hash, load_base_config, load_policy, resolve_path  # noqa: E402
from apps.dsrag.corpus import read_jsonl  # noqa: E402
from apps.dsrag.tune_threshold import (  # noqa: E402
    choose_tau,
    format_curve_csv,
    format_curve_md,
    scan_thresholds,
)

DEFAULT_TAUS = [0.30, 0.40, 0.50, 0.60, 0.70]


def _update_policy_yaml(path: Path, tau: float) -> None:
    text = path.read_text(encoding="utf-8")
    if re.search(r"^answerable_threshold:\s*", text, re.M):
        text = re.sub(
            r"^answerable_threshold:\s*.*$",
            f"answerable_threshold: {tau}",
            text,
            count=1,
            flags=re.M,
        )
    else:
        text = f"answerable_threshold: {tau}\n" + text
    # 标注选点来源（注释行）
    note = f"# chosen_tau_dev={tau}  # by 05_tune_threshold_dev.py · do not use test"
    if "chosen_tau_dev=" in text:
        text = re.sub(r"^# chosen_tau_dev=.*$", note, text, count=1, flags=re.M)
    else:
        text = text.rstrip() + "\n" + note + "\n"
    path.write_text(text, encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="DS-RAG tune Answerable τ on dev only")
    ap.add_argument(
        "--pred",
        default="",
        help="含 answerable_prob 的 R2 predictions.jsonl（默认 r2_dev 最新）",
    )
    ap.add_argument("--taus", default="0.3,0.4,0.5,0.6,0.7", help="逗号分隔")
    ap.add_argument("--split", default="dev", choices=["dev"])  # 硬限制：禁止 test
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--write-policy", action="store_true", default=True)
    ap.add_argument("--no-write-policy", action="store_true")
    ap.add_argument("--prefer", default="mid_safe", choices=["mid_safe", "highest_tau"])
    args = ap.parse_args()

    if args.split != "dev":
        raise SystemExit("FORBIDDEN: threshold tuning only on split=dev")

    base = load_base_config()
    artifacts = resolve_path(base.get("artifacts_dir") or "SCAR/artifacts/dsrag")
    if args.pred:
        pred_path = Path(args.pred)
        if not pred_path.is_absolute():
            pred_path = (Path.cwd() / pred_path).resolve()
    else:
        pred_path = artifacts / "r2_dev_20260929" / "predictions.jsonl"
    if not pred_path.is_file():
        raise SystemExit(f"missing predictions: {pred_path}")

    rows = read_jsonl(pred_path)
    # 仅保留有 type 与 prob 的行；若含 test 误混入则剔除（防御）
    rows = [r for r in rows if r.get("answerable_prob") is not None]
    if any(str(r.get("split")) == "test" for r in rows if r.get("split")):
        rows = [r for r in rows if str(r.get("split")) != "test"]
        print("WARN: dropped test rows from pred (must not tune on test)")

    # join type from taskset if missing
    if any(not r.get("type") for r in rows):
        taskset = read_jsonl(resolve_path(base["taskset"]))
        by = {str(t["id"]): t for t in taskset if str(t.get("split")) == "dev"}
        enriched = []
        for r in rows:
            t = by.get(str(r["id"]))
            if not t:
                continue  # skip non-dev
            rr = dict(r)
            rr["type"] = t.get("type")
            rr["split"] = "dev"
            enriched.append(rr)
        rows = enriched

    # 再按 taskset dev 过滤
    task_dev_ids = {
        str(t["id"])
        for t in read_jsonl(resolve_path(base["taskset"]))
        if str(t.get("split")) == "dev"
    }
    rows = [r for r in rows if str(r["id"]) in task_dev_ids]
    if not rows:
        raise SystemExit("no dev rows with answerable_prob")

    taus = [float(x.strip()) for x in args.taus.split(",") if x.strip()]
    if len(taus) < 3:
        raise SystemExit("need ≥3 taus")
    curve = scan_thresholds(rows, taus)
    chosen, reason = choose_tau(curve, prefer=args.prefer)

    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_dir = Path(args.out_dir) if args.out_dir else artifacts / f"threshold_scan_dev_{day}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "curve.csv").write_text(format_curve_csv(curve), encoding="utf-8")
    (out_dir / "curve.md").write_text(format_curve_md(curve, chosen=chosen, reason=reason), encoding="utf-8")
    (out_dir / "chosen_tau.txt").write_text(f"{chosen}\n", encoding="utf-8")
    (out_dir / "CHOICE.md").write_text(reason + "\n", encoding="utf-8")

    write_policy = args.write_policy and not args.no_write_policy
    policy_path = Path(__file__).resolve().parents[1] / "configs" / "policy_dev.yaml"
    old_policy = load_policy(policy_path)
    if write_policy:
        _update_policy_yaml(policy_path, chosen)
    new_policy = load_policy(policy_path)
    ph = compute_policy_hash(policy=new_policy, base=base, prompt_version=str(new_policy.get("prompt_version") or "v0"))

    meta = {
        "split": "dev",
        "source_predictions": str(pred_path),
        "n": len(rows),
        "taus": taus,
        "chosen_tau": chosen,
        "reason": reason,
        "policy_path": str(policy_path),
        "policy_written": write_policy,
        "old_threshold": old_policy.get("answerable_threshold"),
        "new_threshold": new_policy.get("answerable_threshold"),
        "policy_hash": ph,
        "curve": curve,
        "out_dir": str(out_dir),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(format_curve_md(curve, chosen=chosen, reason=reason))


if __name__ == "__main__":
    main()
