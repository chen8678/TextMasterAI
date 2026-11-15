#!/usr/bin/env python3
"""P11：生成 taskset_v1（A≥80 B≥60 C≥60）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from apps.dsrag.config import load_base_config, resolve_path  # noqa: E402
from apps.dsrag.make_taskset import (  # noqa: E402
    assign_ids_and_split,
    build_type_a,
    build_type_b,
    build_type_c,
    dedupe,
    expand_to_v1_quotas,
    load_chunks,
    write_taskset,
)


def main() -> None:
    base = load_base_config()
    chunks = load_chunks(resolve_path(base["corpus_chunks"]))
    a = dedupe(build_type_a(chunks))
    b = dedupe(build_type_b(a))
    c = dedupe(build_type_c())
    a, b, c = expand_to_v1_quotas(a, b, c, min_a=80, min_b=60, min_c=60)
    rows = assign_ids_and_split(a + b + c, seed=20260929)
    out = resolve_path("SCAR/data/dsrag/taskset/taskset_v1.jsonl")
    h = write_taskset(out, rows, sha_name="taskset_v1.sha256")

    # SAMPLE_CHECK ≥30%
    n = len(rows)
    sample_n = max(1, (n + 2) // 3)
    sample = rows[:sample_n]  # 简单：按写出顺序前 30%
    check_path = out.parent / "SAMPLE_CHECK_v1.md"
    lines = [
        f"# SAMPLE_CHECK taskset_v1",
        f"",
        f"- n={n} A={sum(1 for r in rows if r['type']=='A')} "
        f"B={sum(1 for r in rows if r['type']=='B')} "
        f"C={sum(1 for r in rows if r['type']=='C')}",
        f"- dev={sum(1 for r in rows if r['split']=='dev')} "
        f"test={sum(1 for r in rows if r['split']=='test')}",
        f"- sha256=`{h}`",
        f"- sample_n={sample_n} (≥30%)",
        "",
        "| id | type | split | question |",
        "|----|------|-------|----------|",
    ]
    for r in sample:
        lines.append(f"| {r['id']} | {r['type']} | {r['split']} | {r['question'][:40]} |")
    # B 泄漏粗扫：gold_answer 非空不应出现在 B
    b_leak_gold = [r for r in rows if r["type"] == "B" and (r.get("gold_answer") or "").strip()]
    lines.extend(["", f"B_with_gold_answer: {len(b_leak_gold)}（应为 0）", ""])
    check_path.write_text("\n".join(lines), encoding="utf-8")

    man = {
        "taskset": "taskset_v1",
        "n": n,
        "counts": {
            "A": sum(1 for r in rows if r["type"] == "A"),
            "B": sum(1 for r in rows if r["type"] == "B"),
            "C": sum(1 for r in rows if r["type"] == "C"),
            "dev": sum(1 for r in rows if r["split"] == "dev"),
            "test": sum(1 for r in rows if r["split"] == "test"),
        },
        "sha256": h,
        "scope_spec_version": "v1",
        "note": "P11 配额；test 约一半（非强制 test≥200 全量，总成本约束）",
    }
    (out.parent / "TASKSET_V1_MANIFEST.yaml").write_text(
        "\n".join(
            [
                "taskset: taskset_v1",
                f"n: {n}",
                f"sha256: \"{h}\"",
                f"A: {man['counts']['A']}",
                f"B: {man['counts']['B']}",
                f"C: {man['counts']['C']}",
                f"dev: {man['counts']['dev']}",
                f"test: {man['counts']['test']}",
                "scope_spec_version: v1",
                'note: "P11 A≥80 B≥60 C≥60; ~1:1 split"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(man, ensure_ascii=False, indent=2))
    print("wrote", out)


if __name__ == "__main__":
    main()
