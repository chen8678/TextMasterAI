"""基于 EvidencePack 的生成（证据不足则拒答）。"""

from __future__ import annotations

from typing import Any


def execute(
    query: str,
    evidence_pack: dict | None = None,
    **kwargs: Any,
) -> dict:
    pack = evidence_pack or {}
    items = pack.get("items") or []
    coverage = pack.get("coverage") or "insufficient"
    if coverage == "insufficient" or not items:
        return {
            "answer": "证据不足：未能在已编译结构单元中定位到可靠字段，请核对楼栋/楼层/字段名后重试。",
            "abstained": True,
            "citations": [],
        }
    primary = items[0]
    path = primary.get("path")
    value = primary.get("value")
    unit = primary.get("unit") or ""
    answer = f"{path} = {value}{unit}。依据结构单元 `{primary.get('unit_id')}`（文件 {primary.get('file_id')}）。"
    if coverage == "conflict":
        answer = "检测到可能的字段冲突，请人工核对。当前最优候选：" + answer
    citations = [
        {
            "file_id": it.get("file_id"),
            "unit_id": it.get("unit_id"),
            "path": it.get("path"),
        }
        for it in items[:5]
    ]
    return {
        "answer": answer,
        "abstained": False,
        "citations": citations,
        "skills_note": "scar_generate",
    }
