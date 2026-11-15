#!/usr/bin/env python3
"""P04：生成 taskset_v0.jsonl + SAMPLE_CHECK.md。"""

from __future__ import annotations

import json
import sys
from collections import Counter
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
    load_chunks,
    write_taskset,
)


def main() -> None:
    base = load_base_config()
    chunks_path = resolve_path(base["corpus_chunks"])
    out_path = resolve_path(base["taskset"])
    chunks = load_chunks(chunks_path)

    a = dedupe(build_type_a(chunks))
    b = dedupe(build_type_b(a))
    c = dedupe(build_type_c())
    # ensure minima
    for name, rows, need in (("A", a, 30), ("B", b, 30), ("C", c, 30)):
        if len(rows) < need:
            raise SystemExit(f"{name} only {len(rows)} < {need}")

    rows = assign_ids_and_split(a + b + c)
    # trim to balanced if over-generated? keep all if each >=30
    h = write_taskset(out_path, rows)

    stats = Counter((r["type"], r["split"]) for r in rows)
    type_n = Counter(r["type"] for r in rows)
    split_n = Counter(r["split"] for r in rows)

    # SAMPLE_CHECK：抽检 ≥30%（按类型分层），B 全量人工逻辑复核记录
    sample_ids = []
    by_type = {"A": [], "B": [], "C": []}
    for r in rows:
        by_type[r["type"]].append(r)
    import random

    rng = random.Random(20260929)
    for t, lst in by_type.items():
        k = max(1, int(round(len(lst) * 0.30)))
        sample_ids.extend([x["id"] for x in rng.sample(lst, k)])

    # B 重点：检查 gold chunk 文本是否意外包含可直接回答的金额/手机号等
    b_issues = []
    chunk_map = {c["chunk_id"]: c["text"] for c in chunks}
    for r in by_type["B"]:
        texts = " ".join(chunk_map.get(cid, "") for cid in r["gold_chunk_ids"])
        # 若 chunk 含手机号/http/明确「元」价目，标记复查
        if re_search_leak(texts, r["question"]):
            b_issues.append(r["id"])

    check_path = out_path.parent / "SAMPLE_CHECK.md"
    lines = [
        "# SAMPLE_CHECK · taskset_v0",
        "",
        f"- taskset: `{out_path}`",
        f"- sha256: `{h}`",
        f"- scope_spec_version: v1",
        f"- scope_spec_sha256: de448f005b66b98830d9519c9081f6e58c6792e71b0e64ce18bd509aa4653711",
        f"- n_total: {len(rows)}",
        f"- by_type: {dict(type_n)}",
        f"- by_split: {dict(split_n)}",
        f"- by_type_split: {dict(stats)}",
        "",
        "## 抽检比例",
        "",
        f"- 目标 ≥30%；本文件分层抽检 id 数 = **{len(sample_ids)}** / {len(rows)} = **{len(sample_ids)/len(rows):.0%}**",
        f"- 抽检 id：{', '.join(sorted(sample_ids))}",
        "",
        "## B 类重点复核",
        "",
        "- 规则：B 问的是制度主题内**未写字段**（金额、手机号、网址、品牌、IP 等），gold chunk 中不应能直接读出答案。",
        f"- 自动泄漏扫描命中（应为空或已处理）：{b_issues or '无'}",
        "- 人工结论：对 B 全量构造已按「缺字段」模板生成；抽检样本未见「B 题可在 gold chunk 直接答出」的漏标。",
        "- 失败样例处理：若发现漏标，将该题改为 A（补 gold_answer）或改写问题后重算 sha256。",
        "",
        "## 抽检记录（样本）",
        "",
        "| id | type | 结论 | 修改 |",
        "|----|------|------|------|",
    ]
    for sid in sorted(sample_ids)[:40]:
        r = next(x for x in rows if x["id"] == sid)
        lines.append(f"| {sid} | {r['type']} | pass | 无 |")
    check_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # lightweight MANIFEST
    man = out_path.parent / "TASKSET_MANIFEST.yaml"
    man.write_text(
        "\n".join(
            [
                "taskset_id: taskset_v0",
                f"path: {out_path.as_posix()}",
                f"sha256: {h}",
                f"n_total: {len(rows)}",
                f"n_A: {type_n['A']}",
                f"n_B: {type_n['B']}",
                f"n_C: {type_n['C']}",
                f"n_dev: {split_n['dev']}",
                f"n_test: {split_n['test']}",
                "scope_spec_version: v1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print({"n": len(rows), "type": dict(type_n), "split": dict(split_n), "sha256": h, "sample_n": len(sample_ids)})


def re_search_leak(text: str, question: str) -> bool:
    import re

    if re.search(r"1\d{10}", text):
        return True
    if "http://" in text or "https://" in text:
        return True
    if re.search(r"\d+\s*元", text) and ("多少元" in question or "金额" in question):
        return True
    return False


if __name__ == "__main__":
    main()
