"""Construction JSON → StructureUnit dicts（确定性解析，无 LLM）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIELD_CN = {
    "window_width_mm": "窗宽",
    "window_height_mm": "窗高",
    "floor_height_mm": "层高",
    "spacing_mm": "间距",
    "slab_thickness_mm": "板厚",
}

ALIAS_TO_KEY = {
    "窗宽": "window_width_mm",
    "窗高": "window_height_mm",
    "层高": "floor_height_mm",
    "间距": "spacing_mm",
    "板厚": "slab_thickness_mm",
    "window_width": "window_width_mm",
    "window_height": "window_height_mm",
    "floor_height": "floor_height_mm",
}


class CompileError(ValueError):
    pass


def load_site_dict(raw: str | bytes | dict) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    text = str(raw).strip()
    if not text:
        raise CompileError("空内容，无法编译 construction JSON")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise CompileError(f"JSON 解析失败: {e}") from e
    if not isinstance(data, dict):
        raise CompileError("根节点必须是 object")
    return data


def validate_minimal(site: dict) -> None:
    if "buildings" not in site or not isinstance(site["buildings"], list):
        raise CompileError("缺少 buildings 数组")
    if not site["buildings"]:
        raise CompileError("buildings 为空")


def compile_construction_units(raw: str | bytes | dict, *, template_version: int = 1) -> list[dict[str, Any]]:
    """返回可写入 StructureUnit 的字典列表（尚未落库）。"""
    site = load_site_dict(raw)
    validate_minimal(site)
    units: list[dict[str, Any]] = []
    for bi, b in enumerate(site["buildings"]):
        if not isinstance(b, dict):
            raise CompileError(f"buildings[{bi}] 非法")
        bid = str(b.get("building_id") or f"B{bi}")
        bname = str(b.get("name") or bid)
        floors = b.get("floors") or []
        if not isinstance(floors, list):
            raise CompileError(f"{bid} floors 非法")
        for fi, f in enumerate(floors):
            if not isinstance(f, dict):
                raise CompileError(f"{bid} floors[{fi}] 非法")
            fid = str(f.get("floor_id") or f"F{fi}")
            fname = str(f.get("name") or fid)
            measures = f.get("measures") or {}
            if not isinstance(measures, dict):
                raise CompileError(f"{bid}/{fid} measures 非法")
            for key, m in measures.items():
                if not isinstance(m, dict) or "value" not in m:
                    raise CompileError(f"{bid}/{fid}/{key} 缺少 value")
                value = m["value"]
                unit = str(m.get("unit") or "mm")
                # 简单单位归一：m → mm
                if unit == "m":
                    value = float(value) * 1000.0
                    unit = "mm"
                unit_id = f"{bid}/{fid}/{key}"
                path = f"{bname}/{fname}/{FIELD_CN.get(key, key)}"
                source_ref = str(m.get("source_ref") or f"$.buildings[{bi}].floors[{fi}].measures.{key}")
                if not source_ref.strip():
                    raise CompileError(f"{bid}/{fid}/{key} 缺少 source_ref，拒绝入定案")
                units.append(
                    {
                        "unit_id": unit_id,
                        "path": path,
                        "unit_type": "field",
                        "value_norm": str(value),
                        "unit": unit,
                        "source_ref": source_ref,
                        "provenance": "parser",
                        "template_version": template_version,
                        "metadata": {
                            "field_key": key,
                            "building_name": bname,
                            "floor_name": fname,
                        },
                    }
                )
    if not units:
        raise CompileError("未解析出任何结构单元")
    return units


def default_construction_template_spec() -> dict:
    return {
        "version": "2026-09-07-v1",
        "field_cn": FIELD_CN,
        "alias_to_key": ALIAS_TO_KEY,
        "index_whitelist_keys": list(FIELD_CN.keys()),
        "unit_base": "mm",
    }


def repo_construction_data_dir() -> Path:
    # backend/apps/scar/services/schema_compiler.py → 上溯到仓库根
    return Path(__file__).resolve().parents[4] / "SCAR" / "data" / "construction"
