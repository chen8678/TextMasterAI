"""编译质量门：与金标 unit 表对比。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_gold_units(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("units") or [])


def compare_to_gold(
    compiled: list[dict[str, Any]],
    gold: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    """返回 (ok, errors)。按 path 对齐 value。"""
    errors: list[str] = []
    gold_by_path = {g["path"]: g for g in gold}
    compiled_by_path = {c["path"]: c for c in compiled}
    for path, g in gold_by_path.items():
        c = compiled_by_path.get(path)
        if not c:
            errors.append(f"missing path: {path}")
            continue
        try:
            gv = float(g["value"])
            cv = float(c["value_norm"])
        except (TypeError, ValueError):
            if str(g["value"]) != str(c["value_norm"]):
                errors.append(f"value mismatch at {path}: gold={g['value']} got={c['value_norm']}")
            continue
        if abs(gv - cv) > 1e-6:
            errors.append(f"value mismatch at {path}: gold={gv} got={cv}")
        if (g.get("unit") or "mm") != (c.get("unit") or "mm"):
            errors.append(f"unit mismatch at {path}")
    for path in compiled_by_path:
        if path not in gold_by_path:
            errors.append(f"unexpected path: {path}")
    return (len(errors) == 0, errors)
