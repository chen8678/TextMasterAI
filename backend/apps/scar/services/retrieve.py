"""SCAR 召回：向量候选 → path 消歧 → EvidencePack。"""

from __future__ import annotations

import re
from typing import Optional

from django.conf import settings
from django.db.models import Q

from apps.scar.models import IndexEntry, StructureUnit
from apps.scar.services.evidence import EvidenceItem, EvidencePack
from apps.scar.services.schema_compiler import ALIAS_TO_KEY
from apps.scar.services.strategy_patch import (
    apply_disambiguation,
    load_active_strategy_patch,
    merge_alias_map,
)


def _detect_field_key(question: str, patch: dict | None = None) -> Optional[str]:
    q = question.lower()
    patch = patch or {}
    # 中文优先（避免「窗」同时命中）
    ordered = [
        ("窗宽", "window_width_mm"),
        ("窗高", "window_height_mm"),
        ("层高", "floor_height_mm"),
        ("间距", "spacing_mm"),
        ("板厚", "slab_thickness_mm"),
        ("window_width", "window_width_mm"),
        ("window_height", "window_height_mm"),
        ("floor_height", "floor_height_mm"),
    ]
    prefer = patch.get("prefer_field_order") or []
    if isinstance(prefer, list) and prefer:
        # 将补丁优先字段对应的中文别名提到前面
        boosted = []
        for key in prefer:
            for alias, k in ordered:
                if k == key and (alias, k) not in boosted:
                    boosted.append((alias, k))
        for item in ordered:
            if item not in boosted:
                boosted.append(item)
        ordered = boosted

    for alias, key in ordered:
        if alias.lower() in q or alias in question:
            return key

    alias_map = merge_alias_map(ALIAS_TO_KEY, patch)
    for alias, key in alias_map.items():
        if alias.lower() in q or alias in question:
            return key
    return None


def _detect_building_floor(question: str) -> tuple[Optional[str], Optional[str]]:
    b = None
    f = None
    m = re.search(r"(\d+)\s*号楼", question)
    if m:
        b = f"{m.group(1)}号楼"
    m = re.search(r"(\d+)\s*层", question)
    if m:
        f = f"{m.group(1)}层"
    return b, f


def retrieve_evidence_pack(
    question: str,
    *,
    knowledge_base_id: str,
    domain: str | None = None,
    top_k: int = 8,
    ablation: str | None = None,
    document_title: str | None = None,
) -> EvidencePack:
    domain = domain or getattr(settings, "SCAR_DEFAULT_DOMAIN", "construction")
    ablation = (ablation or getattr(settings, "SCAR_ABLATION", "") or "").strip().lower()
    pack = EvidencePack(question=question, domain=domain, ablation=ablation)
    max_steps = int(getattr(settings, "SCAR_RETRIEVE_MAX_STEPS", 6) or 6)
    steps = 0

    patch = load_active_strategy_patch("scar_retrieve")
    if patch.get("alias_overrides") or patch.get("disambiguation_priority"):
        pack.trace_steps.append("strategy_patch:active")

    steps += 1
    field_key = _detect_field_key(question, patch)
    building, floor = _detect_building_floor(question)
    pack.trace_steps.append(f"classify:field={field_key},building={building},floor={floor}")

    qs = StructureUnit.objects.filter(
        document__knowledge_base_id=knowledge_base_id,
        domain=domain,
        document__compile_status="ok",
    ).exclude(provenance=StructureUnit.Provenance.LLM_SUGGEST)
    # 多 site 同名楼栋时：评测可按 document.title（site_id）收窄
    if document_title:
        qs = qs.filter(document__title=document_title)
        pack.trace_steps.append(f"document_title={document_title}")

    steps += 1
    # 结构优先过滤
    if building:
        qs = qs.filter(path__startswith=f"{building}/")
    if floor:
        qs = qs.filter(path__contains=f"/{floor}/")
    if field_key and ablation != "scar_no_structure":
        qs = qs.filter(Q(metadata__field_key=field_key) | Q(unit_id__endswith=f"/{field_key}"))
    pack.trace_steps.append("structure_filter")

    # 向量候选（可选增强）：按 embed_text 简单包含
    steps += 1
    effective_top_k = top_k
    if ablation != "scar_no_structure":
        candidates = list(qs[: effective_top_k * 3])
    else:
        # 消融：忽略 path 定案，退化为 IndexEntry 文本匹配
        entries = IndexEntry.objects.filter(
            document__knowledge_base_id=knowledge_base_id,
            domain=domain,
        )[: effective_top_k * 3]
        candidates = [e.unit for e in entries]
    pack.trace_steps.append(f"candidates={len(candidates)}")

    if not candidates:
        pack.coverage = "insufficient"
        pack.trace_steps.append("empty")
        return pack

    # 消歧：字段键精确优先 + 策略补丁
    ranked = candidates
    if field_key and ablation != "scar_no_structure":
        exact = [u for u in candidates if (u.metadata or {}).get("field_key") == field_key]
        if exact:
            ranked = exact
        ranked = apply_disambiguation(ranked, field_key=field_key, patch=patch)
    pack.trace_steps.append("disambiguate")

    if steps >= max_steps:
        pack.trace_steps.append("max_steps")

    items: list[EvidenceItem] = []
    for u in ranked[:effective_top_k]:
        items.append(
            EvidenceItem(
                file_id=str(u.document_id),
                unit_id=u.unit_id,
                path=u.path,
                value=u.value_norm,
                unit=u.unit,
                source_type="structure" if ablation != "scar_no_open" else "vector",
            )
        )
    pack.items = items
    pack.coverage = "enough" if items else "insufficient"
    # 冲突：同问窗宽但 top2 落在窗高
    if field_key == "window_width_mm" and len(items) >= 2:
        if "窗高" in items[0].path:
            pack.coverage = "conflict"

    # 重试规则：冲突时扩大 top_k 再取一次（仍用 StructureUnit，不含数值）
    # A2(scar_no_open)：关闭 expand_top_k，与 PROTOCOL / 实验方案一致
    if (
        pack.coverage == "conflict"
        and ablation not in ("scar_no_structure", "scar_no_open")
    ):
        for rule in patch.get("retry_rules") or []:
            if not isinstance(rule, dict):
                continue
            if rule.get("on_coverage") == "conflict" and rule.get("action") == "expand_top_k":
                expand = int(rule.get("expand_top_k") or (effective_top_k * 2))
                more = list(qs[: expand * 3])
                more = apply_disambiguation(more, field_key=field_key, patch=patch)
                if field_key:
                    more = [u for u in more if (u.metadata or {}).get("field_key") == field_key] or more
                items = [
                    EvidenceItem(
                        file_id=str(u.document_id),
                        unit_id=u.unit_id,
                        path=u.path,
                        value=u.value_norm,
                        unit=u.unit,
                        source_type="structure",
                    )
                    for u in more[:expand]
                ]
                pack.items = items
                pack.coverage = "enough" if items else "insufficient"
                pack.trace_steps.append(f"retry:expand_top_k={expand}")
                break
    elif pack.coverage == "conflict" and ablation == "scar_no_open":
        pack.trace_steps.append("ablation:scar_no_open:skip_expand_top_k")

    return pack
