"""从中文问答答案中抽取 path / value（统一解析器，B0′/S1′ 共用）。"""

from __future__ import annotations

import re
from typing import Any

from apps.scar.services.schema_compiler import FIELD_CN

_CN_TO_FIELD = {v: k for k, v in FIELD_CN.items()}
_FIELD_ALIASES = {
    "窗宽": "窗宽",
    "窗口宽度": "窗宽",
    "窗户宽度": "窗宽",
    "窗高": "窗高",
    "窗口高度": "窗高",
    "窗户高度": "窗高",
    "层高": "层高",
    "楼层高度": "层高",
    "间距": "间距",
    "板厚": "板厚",
    "楼板厚度": "板厚",
}


def parse_answer_path_value(answer: str, *, gold_path: str | None = None) -> dict[str, Any]:
    """返回 pred_path / pred_value；失败则为 None。

    优先匹配「X号楼/Y层/字段」或「X号楼Y层的字段…数值」。
    """
    text = (answer or "").strip()
    if not text:
        return {"pred_path": None, "pred_value": None, "parse_ok": False, "notes": "empty"}

    # 显式路径：2号楼/3层/窗宽
    m = re.search(r"(\d+号楼)\s*/\s*(\d+层)\s*/\s*(窗宽|窗高|层高|间距|板厚)", text)
    if m:
        path = f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
        val = _extract_number_near(text, m.end()) or _extract_first_number(text)
        return {"pred_path": path, "pred_value": val, "parse_ok": val is not None, "notes": "slash_path"}

    # 口语：2号楼3层的窗宽是1500
    m2 = re.search(
        r"(\d+号楼)\s*(\d+层)\s*(?:的)?\s*(窗宽|窗高|层高|间距|板厚|窗口宽度|窗户宽度|窗口高度|窗户高度|楼层高度|楼板厚度)",
        text,
    )
    if m2:
        cn = _FIELD_ALIASES.get(m2.group(3), m2.group(3))
        path = f"{m2.group(1)}/{m2.group(2)}/{cn}"
        val = _extract_number_near(text, m2.end()) or _extract_first_number(text)
        return {"pred_path": path, "pred_value": val, "parse_ok": val is not None, "notes": "oral_path"}

    # 回退：若能抽出字段名+数值，用 gold 的楼栋楼层拼（弱）
    field_cn = None
    for alias, cn in _FIELD_ALIASES.items():
        if alias in text:
            field_cn = cn
            break
    val = _extract_first_number(text)
    if field_cn and gold_path and val is not None:
        parts = gold_path.split("/")
        if len(parts) >= 2:
            path = f"{parts[0]}/{parts[1]}/{field_cn}"
            return {
                "pred_path": path,
                "pred_value": val,
                "parse_ok": True,
                "notes": "field_value_with_gold_object",
            }

    if val is not None and gold_path:
        # 仅数值：path 记 gold 会虚高——改为 None path，避免假阳性
        return {"pred_path": None, "pred_value": val, "parse_ok": False, "notes": "value_only"}

    return {"pred_path": None, "pred_value": None, "parse_ok": False, "notes": "unparsed"}


def _extract_first_number(text: str) -> float | None:
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:mm|毫米|m)?", text, flags=re.I)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _extract_number_near(text: str, pos: int, window: int = 80) -> float | None:
    snippet = text[pos : pos + window]
    return _extract_first_number(snippet) or _extract_first_number(text)
