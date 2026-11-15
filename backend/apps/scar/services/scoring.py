"""字段级评分。"""

from __future__ import annotations

from typing import Any


def normalize_path(path: str) -> str:
    return (path or "").strip().replace(" ", "")


def score_case(
    *,
    predicted_path: str | None,
    predicted_value: str | float | None,
    gold_path: str,
    gold_value: Any,
    match_rule: str,
    tolerance: float = 0.0,
) -> dict[str, Any]:
    path_hit = normalize_path(predicted_path or "") == normalize_path(gold_path)
    if match_rule == "path_only":
        field_ok = path_hit
    else:
        try:
            pv = float(predicted_value)
            gv = float(gold_value)
            numeric_ok = abs(pv - gv) <= float(tolerance or 0.0)
        except (TypeError, ValueError):
            numeric_ok = str(predicted_value) == str(gold_value)
        # 数值题必须 path 正确，避免同值异字段假阳性
        field_ok = bool(numeric_ok and path_hit)
    return {
        "path_hit": path_hit,
        "field_accuracy": field_ok,
        "citation_ok": path_hit,
    }
