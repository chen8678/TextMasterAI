#!/usr/bin/env python3
"""
合并 KB 采集 JSONL、过滤低质量样本、划分 train/val。

默认使用五库全量采集的最新 JSON 文件（含元数据），导出 Alpaca 格式 JSONL。

用法:
  python scripts/prepare_sft_dataset.py
  python scripts/prepare_sft_dataset.py --val-ratio 0.15 --seed 42
  python scripts/prepare_sft_dataset.py --include-low-quality
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = PROJECT_ROOT / "backend" / "data" / "training_datasets"
SFT_DIR = PROJECT_ROOT / "backend" / "data" / "sft"

# 五库全量采集（最新一轮）对应的 JSON 文件
DEFAULT_SOURCE_JSONS = [
    "kb_qa_4fe6ed80_20260710_090842_a561f695.json",  # 小学
    "kb_qa_6178a9c2_20260710_090914_02cc8ae5.json",  # 初中
    "kb_qa_fdba18e8_20260710_092203_e007e7b8.json",  # 高中
    "kb_qa_e34d217d_20260710_092231_d635f33d.json",  # 四级
    "kb_qa_e3535603_20260710_092302_fd10337f.json",  # 六级
]

LOW_QUALITY_PATTERNS = [
    r"常识补充",
    r"非来自知识库",
    r"并非来自知识库",
    r"未包含",
    r"无法基于知识库",
    r"均未出现",
    r"均未收录",
    r"均未涉及",
    r"没有检索到",
    r"无法从知识库",
    r"无法直接回答",
    r"通用英语常识",
    r"通用英语知识",
    r"常识性补充",
    r"基于通用英语",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_persona_key(record: Dict[str, Any], meta: Dict[str, Any]) -> str:
    return (
        record.get("persona_id")
        or meta.get("persona_id")
        or record.get("role_name")
        or meta.get("role_name")
        or "unknown"
    )


def is_low_quality(answer: str, strict: bool = True) -> Tuple[bool, List[str]]:
    if not answer or len(answer.strip()) < 20:
        return True, ["empty_or_too_short"]
    reasons = []
    for pat in LOW_QUALITY_PATTERNS:
        if re.search(pat, answer):
            reasons.append(pat)
    if strict and reasons:
        return True, reasons
    return False, reasons


def load_records_from_json(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    meta = data.get("meta") or {}
    out = []
    for rec in data.get("records") or []:
        if rec.get("dry_run"):
            continue
        sft = rec.get("sft") or {}
        item = {
            "instruction": sft.get("instruction") or "",
            "input": sft.get("input") or rec.get("question") or "",
            "output": sft.get("output") or rec.get("answer") or "",
            "meta": {
                "source_file": path.name,
                "persona_id": infer_persona_key(rec, meta),
                "role_name": rec.get("role_name") or meta.get("role_name"),
                "knowledge_base_id": rec.get("knowledge_base_id") or meta.get("knowledge_base_id"),
                "knowledge_base_title": meta.get("knowledge_base_title"),
                "question": rec.get("question"),
            },
        }
        if not item["instruction"] or not item["output"]:
            continue
        low, reasons = is_low_quality(item["output"])
        item["meta"]["low_quality"] = low
        item["meta"]["low_quality_reasons"] = reasons
        out.append(item)
    return out


def stratified_split(
    items: List[Dict[str, Any]],
    val_ratio: float,
    seed: int,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """按 persona 分层划分，保证 val 里各角色尽量都有样本。"""
    rng = random.Random(seed)
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for it in items:
        key = it["meta"].get("persona_id") or "unknown"
        buckets[key].append(it)

    train, val = [], []
    for _, group in buckets.items():
        rng.shuffle(group)
        n = len(group)
        if n <= 1:
            train.extend(group)
            continue
        n_val = max(1, round(n * val_ratio))
        if n_val >= n:
            n_val = n - 1
        val.extend(group[:n_val])
        train.extend(group[n_val:])
    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def write_jsonl(path: Path, rows: List[Dict[str, Any]], with_meta: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            if with_meta:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            else:
                slim = {
                    "instruction": row["instruction"],
                    "input": row["input"],
                    "output": row["output"],
                }
                f.write(json.dumps(slim, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="准备 SFT 训练集：合并、过滤、划分 train/val")
    parser.add_argument("--val-ratio", type=float, default=0.15, help="验证集比例，默认 0.15")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--include-low-quality",
        action="store_true",
        help="不过滤低质量样本（默认会过滤）",
    )
    parser.add_argument(
        "--out-dir",
        default=str(SFT_DIR),
        help="输出目录，默认 backend/data/sft",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    all_items: List[Dict[str, Any]] = []
    missing = []
    for name in DEFAULT_SOURCE_JSONS:
        p = DATASET_DIR / name
        if not p.is_file():
            missing.append(name)
            continue
        all_items.extend(load_records_from_json(p))

    if missing:
        print("警告: 以下源文件不存在，已跳过:")
        for m in missing:
            print(f"  - {m}")

    if not all_items:
        print("错误: 没有可用样本")
        return 1

    total = len(all_items)
    low_items = [x for x in all_items if x["meta"].get("low_quality")]
    kept = all_items if args.include_low_quality else [x for x in all_items if not x["meta"].get("low_quality")]

    if not kept:
        print("错误: 过滤后无样本，可加 --include-low-quality 重试")
        return 1

    train, val = stratified_split(kept, args.val_ratio, args.seed)

    # 输出
    write_jsonl(out_dir / "train.jsonl", train, with_meta=False)
    write_jsonl(out_dir / "val.jsonl", val, with_meta=False)
    write_jsonl(out_dir / "train_with_meta.jsonl", train, with_meta=True)
    write_jsonl(out_dir / "val_with_meta.jsonl", val, with_meta=True)
    write_jsonl(out_dir / "all_filtered.jsonl", kept, with_meta=False)

    stats = {
        "generated_at": _utc_now(),
        "source_files": [n for n in DEFAULT_SOURCE_JSONS if (DATASET_DIR / n).is_file()],
        "total_raw": total,
        "low_quality_count": len(low_items),
        "kept_count": len(kept),
        "train_count": len(train),
        "val_count": len(val),
        "val_ratio": args.val_ratio,
        "seed": args.seed,
        "filtered_low_quality": not args.include_low_quality,
        "persona_train": dict(Counter(x["meta"].get("persona_id") for x in train)),
        "persona_val": dict(Counter(x["meta"].get("persona_id") for x in val)),
        "low_quality_examples": [
            {
                "question": x["meta"].get("question"),
                "reasons": x["meta"].get("low_quality_reasons"),
                "persona_id": x["meta"].get("persona_id"),
            }
            for x in low_items[:20]
        ],
        "outputs": {
            "train": str(out_dir / "train.jsonl"),
            "val": str(out_dir / "val.jsonl"),
            "all_filtered": str(out_dir / "all_filtered.jsonl"),
        },
    }
    (out_dir / "split_stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("=" * 50)
    print("SFT 数据集准备完成")
    print("=" * 50)
    print(f"原始样本: {total}")
    print(f"低质量样本: {len(low_items)}")
    print(f"保留样本: {len(kept)}")
    print(f"train: {len(train)} | val: {len(val)} (ratio={args.val_ratio}, seed={args.seed})")
    print("\ntrain 角色分布:", stats["persona_train"])
    print("val 角色分布:", stats["persona_val"])
    print("\n输出:")
    print(f"  {out_dir / 'train.jsonl'}")
    print(f"  {out_dir / 'val.jsonl'}")
    print(f"  {out_dir / 'split_stats.json'}")
    if low_items and not args.include_low_quality:
        print(f"\n已过滤 {len(low_items)} 条低质量样本，详见 split_stats.json")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
