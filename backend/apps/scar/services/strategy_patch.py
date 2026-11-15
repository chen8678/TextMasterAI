"""SCAR 召回策略补丁（T6.1）。

只允许消歧 / 别名 / 重试规则；禁止写入任何工程数值或字段真值。
生效载体：Skill(scar_retrieve).metadata['scar_strategy_patch']（仅 active 合并结果，
PENDING staging 不进线上召回）。
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

ALLOWED_TOP_KEYS = frozenset(
    {
        "patch_type",
        "alias_overrides",
        "disambiguation_priority",
        "retry_rules",
        "prefer_field_order",
        "notes",
    }
)

# 禁止在补丁中出现的「像工程数值」键名
_FORBIDDEN_VALUE_KEYS = frozenset(
    {
        "value",
        "gold_value",
        "window_width_mm",
        "window_height_mm",
        "floor_height_mm",
        "spacing_mm",
        "slab_thickness_mm",
    }
)


def empty_patch() -> dict[str, Any]:
    return {
        "patch_type": "recall_strategy",
        "alias_overrides": {},
        "disambiguation_priority": [],
        "retry_rules": [],
        "prefer_field_order": [],
        "notes": "",
    }


def parse_patch_text(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return empty_patch()
    # 允许 ```scar_strategy_patch ... ``` 围栏
    m = re.search(r"```(?:scar_strategy_patch|json)?\s*([\s\S]*?)```", raw, re.I)
    if m:
        raw = m.group(1).strip()
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("patch must be a JSON object")
    return data


def validate_strategy_patch(patch: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(patch, dict):
        return False, "patch_not_object"
    unknown = set(patch.keys()) - ALLOWED_TOP_KEYS
    if unknown:
        return False, f"unknown_keys:{sorted(unknown)}"

    # 递归扫描禁止数值真值键
    def _walk(obj: Any, path: str = "") -> Optional[str]:
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = str(k)
                if key in _FORBIDDEN_VALUE_KEYS:
                    return f"forbidden_value_key:{path}.{key}".strip(".")
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    # 允许 top_k 类小整数出现在 retry_rules.expand_top_k
                    if key not in {"expand_top_k", "max_retries", "top_k"}:
                        return f"numeric_literal_forbidden:{path}.{key}".strip(".")
                err = _walk(v, f"{path}.{key}" if path else key)
                if err:
                    return err
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                err = _walk(item, f"{path}[{i}]")
                if err:
                    return err
        return None

    bad = _walk(patch)
    if bad:
        return False, bad

    aliases = patch.get("alias_overrides") or {}
    if aliases and not isinstance(aliases, dict):
        return False, "alias_overrides_not_object"
    for a, k in aliases.items():
        if not isinstance(a, str) or not isinstance(k, str):
            return False, "alias_overrides_must_be_str_str"
        if k in _FORBIDDEN_VALUE_KEYS and k.endswith("_mm"):
            # 别名目标可以是字段键名（语义指针），不能是数值
            pass

    pri = patch.get("disambiguation_priority") or []
    if pri and not isinstance(pri, list):
        return False, "disambiguation_priority_not_list"
    for rule in pri:
        if not isinstance(rule, dict):
            return False, "disambiguation_rule_not_object"
        if set(rule.keys()) - {"when_field", "prefer_over", "notes"}:
            return False, "disambiguation_rule_bad_keys"

    retries = patch.get("retry_rules") or []
    if retries and not isinstance(retries, list):
        return False, "retry_rules_not_list"
    for rule in retries:
        if not isinstance(rule, dict):
            return False, "retry_rule_not_object"
        if set(rule.keys()) - {"on_coverage", "action", "expand_top_k", "max_retries", "notes"}:
            return False, "retry_rule_bad_keys"

    patch_type = patch.get("patch_type") or "recall_strategy"
    if patch_type != "recall_strategy":
        return False, f"unsupported_patch_type:{patch_type}"

    return True, "ok"


def load_active_strategy_patch(skill_id: str = "scar_retrieve") -> dict[str, Any]:
    """仅读取已合并到 Skill.metadata 的补丁；忽略 PENDING staging。"""
    try:
        from apps.skills.models import Skill

        skill = Skill.objects.filter(id=skill_id).first()
        if not skill:
            return empty_patch()
        meta = skill.metadata if isinstance(skill.metadata, dict) else {}
        patch = meta.get("scar_strategy_patch")
        if not isinstance(patch, dict):
            return empty_patch()
        ok, _ = validate_strategy_patch(patch)
        return patch if ok else empty_patch()
    except Exception:
        return empty_patch()


def merge_alias_map(base: dict[str, str], patch: dict[str, Any]) -> dict[str, str]:
    out = dict(base)
    overrides = patch.get("alias_overrides") or {}
    if isinstance(overrides, dict):
        for k, v in overrides.items():
            if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                out[k.strip()] = v.strip()
    return out


def apply_disambiguation(
    ranked: list,
    *,
    field_key: Optional[str],
    patch: dict[str, Any],
) -> list:
    """按补丁优先剔除易混淆字段（如窗宽题剔除窗高候选）。"""
    if not field_key or not ranked:
        return ranked
    rules = patch.get("disambiguation_priority") or []
    demote: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("when_field") == field_key and rule.get("prefer_over"):
            demote.add(str(rule["prefer_over"]))
    if not demote:
        return ranked

    def _key(u) -> str:
        if isinstance(u, dict):
            return str((u.get("metadata") or {}).get("field_key") or "")
        return str((getattr(u, "metadata", None) or {}).get("field_key") or "")

    kept = [u for u in ranked if _key(u) not in demote]
    return kept or ranked
