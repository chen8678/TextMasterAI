"""
english_assessment_build：从内置题库抽取试题（MVP）。
"""

import json
import random
from pathlib import Path

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "sample_questions.json"


def _load_bank():
    try:
        raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
        return raw.get("default") or []
    except Exception:
        return []


def execute(
    learner_constraints=None,
    question_count: int = 5,
    dimensions=None,
    level_target: str = "",
    **kwargs,
) -> dict:
    lc = learner_constraints or {}
    tags = lc.get("level_tags") or []
    dim_filter = list(dimensions or [])
    n = max(1, min(int(question_count or 5), 20))

    bank = _load_bank()
    level_hint = (level_target or "").strip().upper() or _infer_level(tags)

    candidates = []
    for item in bank:
        if level_hint and item.get("level") and item["level"].upper() != level_hint:
            continue
        if dim_filter and item.get("dimension") not in dim_filter:
            continue
        candidates.append(item)

    if not candidates:
        candidates = list(bank)

    random.shuffle(candidates)
    picked = candidates[:n]

    items_public = []
    for p in picked:
        public = {k: v for k, v in p.items() if k != "answer_key"}
        items_public.append(public)

    return {
        "items": items_public,
        "items_scoring": picked,
        "level_used": level_hint or "mixed",
        "count": len(items_public),
    }


def _infer_level(tags):
    joined = " ".join(str(t) for t in tags).lower()
    if any(k in joined for k in ("cet6", "六级", "stage:cet6")):
        return "B2"
    if any(k in joined for k in ("cet4", "四级", "goal:cet", "stage:cet4")):
        return "B2"
    if any(k in joined for k in ("senior", "高中", "stage:senior")):
        return "B2"
    if any(k in joined for k in ("junior", "初中", "stage:junior")):
        return "B1"
    if any(k in joined for k in ("primary", "小学", "stage:primary")):
        return "A2"
    for t in tags:
        u = str(t).upper()
        if "A2" in u:
            return "A2"
        if "B1" in u:
            return "B1"
        if "B2" in u:
            return "B2"
        if "C1" in u:
            return "C1"
    return ""
