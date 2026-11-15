"""半结构轨（T7.3 二期骨架）：无 span 绑定不得入定案索引。"""

from __future__ import annotations

from typing import Any


class SemiStructureError(ValueError):
    pass


def parse_semi_structure_spans(
    text: str,
    *,
    spans: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    PDF/MD 半结构解析入口。

    纪律（防名存实亡 §2.1）：
    - 每个定案单元必须绑定原文 span（start/end 或 anchor）
    - 无 span 的候选一律丢弃，不得写入 StructureUnit / IndexEntry
    - 本函数不调用 LLM 生成数值
    """
    spans = spans or []
    if not text or not str(text).strip():
        raise SemiStructureError("空文本，无法半结构解析")
    if not spans:
        raise SemiStructureError(
            "半结构轨拒绝：未提供 span 绑定；无 span 不得入定案索引（T7.3）"
        )

    units: list[dict[str, Any]] = []
    for i, sp in enumerate(spans):
        if not isinstance(sp, dict):
            continue
        start = sp.get("start")
        end = sp.get("end")
        anchor = sp.get("anchor") or sp.get("source_ref")
        if (start is None or end is None) and not anchor:
            # 无绑定 → 跳过
            continue
        field_key = sp.get("field_key")
        value = sp.get("value")
        if field_key is None or value is None:
            continue
        if sp.get("provenance") in {"llm", "llm_suggest", "LLM_SUGGEST"} and not anchor and start is None:
            continue
        source_ref = anchor or f"span[{i}:{start}:{end}]"
        path = sp.get("path") or f"semi/{field_key}"
        units.append(
            {
                "unit_id": sp.get("unit_id") or f"semi/{i}/{field_key}",
                "path": path,
                "unit_type": "field",
                "value_norm": str(value),
                "unit": str(sp.get("unit") or ""),
                "source_ref": source_ref,
                "provenance": "parser",
                "metadata": {
                    "field_key": field_key,
                    "span_start": start,
                    "span_end": end,
                    "semi_structure": True,
                },
            }
        )

    if not units:
        raise SemiStructureError("半结构轨：所有候选均缺少有效 span 绑定，未产生定案单元")
    return units
