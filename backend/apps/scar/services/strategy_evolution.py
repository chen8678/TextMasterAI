"""SCAR 召回策略进化：Staging + heldout 准确率门禁（T6.2 / T6.3）。"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from django.utils import timezone

from apps.scar.services.eval_runner import run_field_eval
from apps.scar.services.strategy_patch import (
    empty_patch,
    parse_patch_text,
    validate_strategy_patch,
)

logger = logging.getLogger(__name__)

SCAR_RETRIEVE_SKILL_ID = "scar_retrieve"


def ensure_scar_retrieve_skill():
    from apps.skills.models import Skill

    skill, _ = Skill.objects.get_or_create(
        id=SCAR_RETRIEVE_SKILL_ID,
        defaults={
            "name": "SCAR结构召回",
            "description": "结构编译 Agentic RAG 召回 → EvidencePack",
            "permission_level": "rag",
            "lifecycle_status": "active",
            "is_active": True,
            "evolution_enabled": True,
            "metadata": {
                "evolution_domain": "scar_retrieval",
                "use_case": "SCAR 召回策略受控进化",
                "scar_strategy_patch": empty_patch(),
                "primary_env": "rag",
            },
        },
    )
    meta = dict(skill.metadata or {})
    if meta.get("evolution_domain") != "scar_retrieval":
        meta["evolution_domain"] = "scar_retrieval"
        skill.metadata = meta
        skill.save(update_fields=["metadata"])
    return skill


def propose_scar_strategy_patch(
    patch: dict[str, Any],
    *,
    user=None,
    note: str = "",
):
    """写入 PENDING Staging；未审批前不改线上 scar_strategy_patch。"""
    from apps.skills.evolution.guard import draft_markdown_allowed, skill_allowed_for_evolution
    from apps.skills.models import SkillEvolutionStaging
    from apps.skills.tasks import emit_lifecycle_event

    skill = ensure_scar_retrieve_skill()
    ok_dom, dom_reason = skill_allowed_for_evolution(skill)
    if not ok_dom:
        raise ValueError(f"evolution_domain_blocked:{dom_reason}")

    ok, reason = validate_strategy_patch(patch)
    if not ok:
        raise ValueError(f"invalid_patch:{reason}")

    draft_text = json.dumps(patch, ensure_ascii=False, indent=2)
    ok_md, md_reason = draft_markdown_allowed(draft_text)
    if not ok_md:
        raise ValueError(f"guard_blocked:{md_reason}")

    staging = SkillEvolutionStaging.objects.create(
        skill=skill,
        user=user,
        status=SkillEvolutionStaging.Status.PENDING,
        draft_markdown=draft_text,
        provenance="scar_strategy_evolution",
    )
    emit_lifecycle_event(
        skill,
        "staged",
        user=user,
        note=f"staging_id={staging.id}; scar_strategy; {note}".strip(),
    )
    return staging


def apply_scar_strategy_with_heldout_gate(
    staging_id: str,
    *,
    knowledge_base_id: str = "",
    reviewer=None,
    epsilon: float = 0.0,
    skip_gate: bool = False,
) -> dict[str, Any]:
    """
    门禁：heldout Field Accuracy(S1) 不得下降超过 epsilon。
    先临时写入补丁评测，不通过则恢复并 REJECT；通过则 APPLIED 且 version+1。
    """
    from apps.skills.models import SkillEvolutionStaging
    from apps.skills.tasks import emit_lifecycle_event

    try:
        st = SkillEvolutionStaging.objects.select_related("skill").get(id=staging_id)
    except SkillEvolutionStaging.DoesNotExist:
        return {"ok": False, "error": "staging_not_found"}

    if st.skill_id != SCAR_RETRIEVE_SKILL_ID:
        return {"ok": False, "error": "not_scar_retrieve_staging"}
    if st.status != SkillEvolutionStaging.Status.PENDING:
        return {"ok": False, "error": f"bad_status:{st.status}"}

    try:
        patch = parse_patch_text(st.draft_markdown)
    except Exception as e:
        return {"ok": False, "error": f"parse_failed:{e}"}
    ok, reason = validate_strategy_patch(patch)
    if not ok:
        return {"ok": False, "error": f"invalid_patch:{reason}"}

    skill = st.skill
    meta = dict(skill.metadata or {})
    prev_patch = meta.get("scar_strategy_patch") if isinstance(meta.get("scar_strategy_patch"), dict) else empty_patch()
    prev_ver = int(skill.version or 1)
    prev_active = skill.is_active
    prev_life = skill.lifecycle_status

    baseline = None
    candidate = None
    if not skip_gate:
        if not knowledge_base_id:
            return {"ok": False, "error": "knowledge_base_id_required_for_gate"}
        baseline = run_field_eval(
            config="S1",
            split="heldout",
            knowledge_base_id=knowledge_base_id,
        )

    # 临时应用候选补丁做评测
    meta["_pre_apply_backup"] = {
        "staging_id": str(st.id),
        "scar_strategy_patch": prev_patch,
        "evolution_merged_markdown": meta.get("evolution_merged_markdown") or "",
        "lifecycle_status": prev_life,
        "is_active": prev_active,
        "version": prev_ver,
    }
    meta["scar_strategy_patch"] = patch
    skill.metadata = meta
    skill.save(update_fields=["metadata"])

    if not skip_gate:
        candidate = run_field_eval(
            config="S1",
            split="heldout",
            knowledge_base_id=knowledge_base_id,
        )
        base_acc = float(baseline["field_accuracy"])
        cand_acc = float(candidate["field_accuracy"])
        if cand_acc + 1e-12 < base_acc - float(epsilon):
            # 回滚补丁，拒绝上线；保持 skill active（避免问答整体被关掉）
            meta = dict(skill.metadata or {})
            meta["scar_strategy_patch"] = prev_patch
            meta["last_gate_failure"] = {
                "staging_id": str(st.id),
                "baseline_field_accuracy": base_acc,
                "candidate_field_accuracy": cand_acc,
                "epsilon": float(epsilon),
            }
            skill.metadata = meta
            skill.save(update_fields=["metadata"])
            st.status = SkillEvolutionStaging.Status.REJECTED
            st.reviewed_at = timezone.now()
            st.reviewed_by = reviewer
            st.save(update_fields=["status", "reviewed_at", "reviewed_by"])
            emit_lifecycle_event(
                skill,
                "rejected",
                user=reviewer,
                note=(
                    f"staging_id={st.id}; heldout_gate_failed; "
                    f"baseline={base_acc:.4f}; candidate={cand_acc:.4f}; epsilon={epsilon}"
                ),
            )
            return {
                "ok": False,
                "error": "heldout_accuracy_dropped",
                "baseline_field_accuracy": base_acc,
                "candidate_field_accuracy": cand_acc,
                "epsilon": float(epsilon),
                "staging_id": str(st.id),
            }

    # 通过门禁：确认合并 + bump version（apply ≠ 改变 lifecycle）
    skill.refresh_from_db()
    meta = dict(skill.metadata or {})
    meta["scar_strategy_patch"] = patch
    meta["evolution_merged_markdown"] = (meta.get("evolution_merged_markdown") or "") + (
        f"\n\n## scar_strategy_patch v{prev_ver + 1}\n```json\n"
        + json.dumps(patch, ensure_ascii=False, indent=2)
        + "\n```\n"
    )
    skill.metadata = meta
    skill.version = prev_ver + 1
    skill.is_active = prev_active
    skill.lifecycle_status = prev_life
    skill.save(update_fields=["metadata", "version", "is_active", "lifecycle_status"])

    st.status = SkillEvolutionStaging.Status.APPLIED
    st.reviewed_at = timezone.now()
    st.reviewed_by = reviewer
    st.save(update_fields=["status", "reviewed_at", "reviewed_by"])
    emit_lifecycle_event(
        skill,
        "applied",
        user=reviewer,
        from_version=prev_ver,
        to_version=skill.version,
        note=f"staging_id={st.id}; scar_strategy; heldout_gate_ok; apply≠activate",
    )
    return {
        "ok": True,
        "staging_id": str(st.id),
        "version": skill.version,
        "baseline_field_accuracy": None if not baseline else baseline["field_accuracy"],
        "candidate_field_accuracy": None if not candidate else candidate["field_accuracy"],
        "patch": patch,
    }
