"""BIM/IFC JSON → construction schema（确定性，要求 source_ref；禁 LLM 标签单独入金标）。"""

from __future__ import annotations

import re
from typing import Any, Optional

from apps.scar.services.schema_compiler import ALIAS_TO_KEY, FIELD_CN

# 属性名 → 字段键（仅白名单；不得由 LLM 任意发明）
_PROP_KEY_ALIASES = {
    **{k: k for k in FIELD_CN.keys()},
    **ALIAS_TO_KEY,
    "窗宽mm": "window_width_mm",
    "窗高mm": "window_height_mm",
    "层高mm": "floor_height_mm",
    "Width": "window_width_mm",
    "Height": "window_height_mm",
    "OverallWidth": "window_width_mm",
    "OverallHeight": "window_height_mm",
}


def _norm_field_key(name: str) -> Optional[str]:
    s = (name or "").strip()
    if not s:
        return None
    if s in _PROP_KEY_ALIASES:
        return _PROP_KEY_ALIASES[s]
    low = s.lower().replace(" ", "_")
    if low in _PROP_KEY_ALIASES:
        return _PROP_KEY_ALIASES[low]
    return None


def _parse_numeric(val: Any) -> Optional[tuple[float, str]]:
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val), "mm"
    if isinstance(val, dict) and "value" in val:
        try:
            v = float(val["value"])
        except (TypeError, ValueError):
            return None
        unit = str(val.get("unit") or "mm")
        return v, unit
    if isinstance(val, str):
        m = re.match(r"^\s*([-+]?\d+(?:\.\d+)?)\s*(mm|m|厘米|cm)?\s*$", val, re.I)
        if not m:
            return None
        v = float(m.group(1))
        unit = (m.group(2) or "mm").lower()
        if unit in {"cm", "厘米"}:
            v *= 10
            unit = "mm"
        if unit == "m":
            v *= 1000
            unit = "mm"
        return v, "mm"
    return None


def is_construction_shaped(payload: dict) -> bool:
    return isinstance(payload.get("buildings"), list) and bool(payload.get("buildings"))


def bim_payload_to_construction_site(bim_json: dict) -> dict:
    """
    将 BIM 统一 JSON 转为 construction site dict。
    - 已是 construction 形：原样返回（编译器会生成 source_ref）
    - 否则从 elements/items.properties 白名单字段抽取，每条必须有可追溯 source_ref
    - 带 llm_label / suggested 且无 source_ref 的属性一律跳过
    """
    if not isinstance(bim_json, dict):
        raise ValueError("bim_json 必须是 object")

    # 若嵌套了 construction
    for key in ("construction", "site", "scar_site"):
        nested = bim_json.get(key)
        if isinstance(nested, dict) and is_construction_shaped(nested):
            return nested

    if is_construction_shaped(bim_json):
        return {
            "site_id": bim_json.get("site_id") or "bim_site",
            "site_name": bim_json.get("site_name") or bim_json.get("bim_meta", {}).get("source_file") or "BIM站点",
            "buildings": bim_json["buildings"],
        }

    elements = bim_json.get("elements") or bim_json.get("items") or []
    if not isinstance(elements, list):
        raise ValueError("BIM JSON 缺少 elements/items 或 buildings")

    # 按「楼栋/楼层」粗分组；无法识别则归入 BIM楼/默认层
    buildings: dict[str, dict] = {}
    measure_count = 0

    for ei, el in enumerate(elements):
        if not isinstance(el, dict):
            continue
        # 拒绝纯 LLM 标签元素（无 id/source 且标记为 llm）
        if el.get("provenance") in {"llm", "llm_suggest", "LLM_SUGGEST"} and not el.get("id"):
            continue
        if el.get("llm_label") and not (el.get("id") or el.get("source_ref") or el.get("GlobalId")):
            continue

        bname = str(el.get("building") or el.get("Building") or el.get("building_name") or "BIM楼")
        fname = str(el.get("floor") or el.get("Floor") or el.get("Storey") or el.get("floor_name") or "默认层")
        bid = str(el.get("building_id") or bname)
        fid = str(el.get("floor_id") or fname)

        props = el.get("properties") or el.get("Properties") or {}
        if not isinstance(props, dict):
            props = {}

        # 也扫描顶层白名单键
        flat_props = dict(props)
        for k in list(el.keys()):
            if _norm_field_key(k):
                flat_props[k] = el[k]

        for pk, pv in flat_props.items():
            # 禁止 LLM 建议值单独入金标
            if isinstance(pv, dict) and (
                pv.get("provenance") in {"llm", "llm_suggest", "LLM_SUGGEST"}
                or pv.get("llm_label")
            ):
                if not pv.get("source_ref"):
                    continue
            field_key = _norm_field_key(str(pk))
            if not field_key:
                continue
            parsed = _parse_numeric(pv)
            if not parsed:
                continue
            value, unit = parsed

            elem_id = el.get("id") or el.get("GlobalId") or ei
            source_ref = None
            if isinstance(pv, dict) and pv.get("source_ref"):
                source_ref = str(pv["source_ref"])
            elif el.get("source_ref"):
                source_ref = f"{el['source_ref']}.{pk}"
            else:
                source_ref = f"$.elements[{ei}].properties.{pk}#id={elem_id}"

            if not source_ref:
                continue

            b = buildings.setdefault(
                bid,
                {"building_id": bid, "name": bname, "floors": {}},
            )
            floors = b["floors"]
            f = floors.setdefault(
                fid,
                {"floor_id": fid, "name": fname, "measures": {}},
            )
            # 同字段后写覆盖前写，但保留 source_ref
            f["measures"][field_key] = {
                "value": value,
                "unit": unit,
                "source_ref": source_ref,
            }
            measure_count += 1

    if measure_count == 0:
        raise ValueError(
            "无法从 BIM 提取可编译字段：需要 construction.buildings 或 "
            "elements[].properties 中的白名单量测字段，且必须可追溯 source_ref"
        )

    out_buildings = []
    for b in buildings.values():
        floors_list = list(b["floors"].values())
        out_buildings.append(
            {
                "building_id": b["building_id"],
                "name": b["name"],
                "floors": floors_list,
            }
        )

    meta = bim_json.get("bim_meta") or {}
    return {
        "site_id": str(bim_json.get("site_id") or meta.get("source_file") or "bim_site"),
        "site_name": str(bim_json.get("site_name") or meta.get("source_file") or "BIM站点"),
        "buildings": out_buildings,
        "bim_bridge": {
            "source_file": meta.get("source_file"),
            "source_format": meta.get("source_format"),
            "measure_count": measure_count,
        },
    }
