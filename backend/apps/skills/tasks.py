"""Celery 任务（autodiscover_tasks 会加载本模块）。"""
from __future__ import annotations

import logging
from typing import Optional

try:
    from celery import shared_task
except ImportError:

    def shared_task(*args, **kwargs):
        def decorator(f):
            return f

        return decorator(args[0]) if args and callable(args[0]) else decorator


logger = logging.getLogger(__name__)


@shared_task(bind=True, acks_late=True)
def run_skill_evolution_task(
    self,
    skill_id: str,
    source_log_id: str,
    user_id: Optional[int],
    user_message: str,
):
    """生成草案、写入 SkillEvolutionStaging + JSON 履历。"""
    from django.contrib.auth import get_user_model

    from apps.skills.evolution.evolver import propose_staging_change
    from apps.skills.evolution.guard import draft_markdown_allowed
    from apps.skills.evolution.storage import append_record
    from apps.skills.models import Skill, SkillEvolutionStaging, SkillExecutionLog

    User = get_user_model()
    user = User.objects.filter(id=user_id).first() if user_id else None

    try:
        log = SkillExecutionLog.objects.get(id=source_log_id)
    except SkillExecutionLog.DoesNotExist:
        logger.warning("SkillExecutionLog %s not found", source_log_id)
        return

    try:
        skill = Skill.objects.get(id=skill_id)
    except Skill.DoesNotExist:
        return

    draft = propose_staging_change(
        skill_id,
        user_message=user_message,
        failed_log_summary=f"{log.input_summary}\n{log.output_summary}",
        skill_description=skill.description,
    )

    ok_md, md_reason = draft_markdown_allowed(draft.markdown_section)
    if not ok_md:
        logger.warning("skill evolution staging skipped: skill_id=%s reason=%s", skill_id, md_reason)
        emit_lifecycle_event(
            skill,
            "guard_blocked",
            user=user,
            note=f"source_log={source_log_id}; reason={md_reason}",
        )
        return

    emit_lifecycle_event(
        skill,
        "propose",
        user=user,
        note=f"provenance={draft.provenance}; source_log={source_log_id}",
    )

    staging = SkillEvolutionStaging.objects.create(
        skill=skill,
        source_log=log,
        user=user,
        status=SkillEvolutionStaging.Status.PENDING,
        draft_markdown=draft.markdown_section,
        provenance=draft.provenance,
    )

    emit_lifecycle_event(
        skill,
        "staged",
        user=user,
        note=f"staging_id={staging.id}; provenance={draft.provenance}",
    )

    append_record(
        skill_id,
        {
            "staging_id": str(staging.id),
            "source_log_id": str(log.id),
            "provenance": draft.provenance,
            "status": staging.status,
        },
    )

    if getattr(skill, "evolution_auto_apply", False):
        _apply_to_skill_metadata(skill, draft.markdown_section)
        staging.status = SkillEvolutionStaging.Status.APPLIED
        staging.save(update_fields=["status"])
        emit_lifecycle_event(
            skill,
            "applied",
            user=user,
            note=f"staging_id={staging.id}; auto_apply=true",
        )


def emit_lifecycle_event(
    skill,
    event_type: str,
    *,
    user=None,
    note: str = "",
    from_version: int = 0,
    to_version: int = 0,
    content_hash: str = "",
):
    """写入 SkillLifecycleEvent；失败时静默（不影响主路径）。"""
    try:
        from apps.skills.models import SkillLifecycleEvent

        SkillLifecycleEvent.objects.create(
            skill=skill,
            user=user if user and getattr(user, "is_authenticated", False) else None,
            event_type=event_type,
            from_version=from_version or int(getattr(skill, "version", 0) or 0),
            to_version=to_version or int(getattr(skill, "version", 0) or 0),
            content_hash=(content_hash or getattr(skill, "content_hash", "") or "")[:64],
            note=(note or "")[:4000],
        )
    except Exception:
        logger.exception("emit_lifecycle_event failed skill=%s type=%s", getattr(skill, "id", None), event_type)


def _apply_to_skill_metadata(skill, markdown: str) -> None:
    """仅合并进化 Markdown 到 metadata；不改 is_active / lifecycle_status（A0.2）。"""
    meta = dict(skill.metadata or {})
    prev = meta.get("evolution_merged_markdown") or ""
    merged = (prev + "\n\n" + markdown).strip()
    meta["evolution_merged_markdown"] = merged[:20000]
    skill.metadata = meta
    skill.save(update_fields=["metadata"])


def reject_staging(staging_id, reviewer=None, reason: str = "") -> bool:
    """人工拒绝 pending 草案。"""
    from django.utils import timezone

    from apps.skills.models import SkillEvolutionStaging

    try:
        st = SkillEvolutionStaging.objects.select_related("skill").get(id=staging_id)
    except SkillEvolutionStaging.DoesNotExist:
        return False
    if st.status != SkillEvolutionStaging.Status.PENDING:
        return False
    st.status = SkillEvolutionStaging.Status.REJECTED
    st.reviewed_at = timezone.now()
    st.reviewed_by = reviewer
    st.save(update_fields=["status", "reviewed_at", "reviewed_by"])
    emit_lifecycle_event(
        st.skill,
        "rejected",
        user=reviewer,
        note=f"staging_id={st.id}; reason={reason or 'manual_reject'}",
    )
    return True


def apply_staging_to_skill(staging_id, reviewer=None) -> bool:
    """供 Admin 或 API：将待审核草案合并进 Skill.metadata（不自动激活 Skill）。"""
    from django.utils import timezone

    from apps.skills.models import SkillEvolutionStaging

    try:
        st = SkillEvolutionStaging.objects.select_related("skill").get(id=staging_id)
    except SkillEvolutionStaging.DoesNotExist:
        return False
    if st.status != SkillEvolutionStaging.Status.PENDING:
        return False
    skill = st.skill
    # 显式保持治理边界：apply ≠ activate
    prev_active = skill.is_active
    prev_life = skill.lifecycle_status
    prev_ver = int(skill.version or 1)
    meta = dict(skill.metadata or {})
    meta["_pre_apply_backup"] = {
        "staging_id": str(st.id),
        "evolution_merged_markdown": meta.get("evolution_merged_markdown") or "",
        "lifecycle_status": prev_life,
        "is_active": prev_active,
        "version": prev_ver,
    }
    skill.metadata = meta
    skill.save(update_fields=["metadata"])

    _apply_to_skill_metadata(skill, st.draft_markdown)
    skill.refresh_from_db()
    if skill.is_active != prev_active or skill.lifecycle_status != prev_life:
        skill.is_active = prev_active
        skill.lifecycle_status = prev_life
        skill.save(update_fields=["is_active", "lifecycle_status"])
    # 合并后 bump version（仍不激活）
    skill.version = prev_ver + 1
    skill.save(update_fields=["version"])

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
        note=f"staging_id={st.id}; apply≠activate; is_active={skill.is_active}; life={skill.lifecycle_status}",
    )
    return True


def soft_rollback_skill(skill_id: str, reviewer=None) -> tuple:
    """
    软回滚（无 SkillVersionSnapshot 表时的诚实实现）：
    从 metadata._pre_apply_backup 恢复 evolution_merged_markdown，
    并将 lifecycle_status 置为 rolled_back、is_active=False。
    """
    from apps.skills.models import Skill

    skill = Skill.objects.filter(id=skill_id).first()
    if not skill:
        return False, "skill_not_found"
    meta = dict(skill.metadata or {})
    backup = meta.get("_pre_apply_backup")
    if not isinstance(backup, dict):
        return False, "no_pre_apply_backup"
    prev_ver = int(skill.version or 1)
    meta["evolution_merged_markdown"] = backup.get("evolution_merged_markdown") or ""
    if "scar_strategy_patch" in backup:
        meta["scar_strategy_patch"] = backup.get("scar_strategy_patch") or {}
    meta["last_rollback"] = {
        "from_staging_id": backup.get("staging_id"),
        "restored_version_hint": backup.get("version"),
    }
    skill.metadata = meta
    skill.lifecycle_status = "rolled_back"
    skill.is_active = False
    skill.version = prev_ver + 1
    skill.save(update_fields=["metadata", "lifecycle_status", "is_active", "version"])
    emit_lifecycle_event(
        skill,
        "rolled_back",
        user=reviewer,
        from_version=prev_ver,
        to_version=skill.version,
        note=f"soft_rollback from staging_id={backup.get('staging_id')}; restored markdown from _pre_apply_backup",
    )
    return True, None


def rollback_skill_to_version(skill_id: str, target_version=None, reviewer=None) -> tuple:
    """兼容旧 API：当前无版本快照表，转发 soft_rollback_skill。"""
    return soft_rollback_skill(skill_id, reviewer=reviewer)


@shared_task(bind=True, acks_late=True)
def pro_sandbox_simulation(self, user_id: int, limit: int = 12):
    """
    PRO 沙盒最小任务（P2-T23）：
    - 从用户知识库采样纯文本段落
    - 生成候选草案并过 guard
    - 写入 SkillEvolutionStaging（默认挂到 rag_answer）
    """
    from django.contrib.auth import get_user_model
    from apps.skills.models import Skill, SkillEvolutionStaging
    from apps.skills.simulation.test_generator import sample_user_kb_segments
    from apps.skills.simulation.sandbox_runner import run_sandbox
    from apps.skills.evolution.storage import append_record

    User = get_user_model()
    user = User.objects.filter(id=user_id).first()
    if not user:
        return {"ok": False, "reason": "user_not_found"}
    if not getattr(user, "is_pro", False):
        return {"ok": False, "reason": "not_pro"}

    # 先挂到通用 skill，后续可按 mode/领域拆分。
    skill = Skill.objects.filter(id="rag_answer").first()
    if not skill:
        return {"ok": False, "reason": "skill_not_found"}

    cases = sample_user_kb_segments(user=user, limit=max(1, min(int(limit), 30)))
    result = run_sandbox(cases)
    if not result.accepted:
        return {"ok": False, "reason": result.reason, "used_cases": result.used_cases}

    st = SkillEvolutionStaging.objects.create(
        skill=skill,
        source_log=None,
        user=user,
        status=SkillEvolutionStaging.Status.PENDING,
        draft_markdown=result.markdown,
        provenance="pro_sandbox_simulation",
    )

    append_record(
        skill.id,
        {
            "staging_id": str(st.id),
            "provenance": "pro_sandbox_simulation",
            "used_cases": result.used_cases,
            "status": st.status,
        },
    )
    return {"ok": True, "staging_id": str(st.id), "used_cases": result.used_cases}


@shared_task(bind=True, acks_late=True)
def run_pro_sandbox_daily(self, limit_per_user: int = 8, max_users: int = 20):
    """按日批量触发 PRO 沙盒（P2-T24）。"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    users = User.objects.filter(is_pro=True, is_active=True).order_by("-date_joined")[:max(1, int(max_users))]
    ok_count = 0
    fail_count = 0
    for u in users:
        try:
            r = pro_sandbox_simulation.delay(u.id, limit=max(1, int(limit_per_user)))
            payload = r.get(timeout=120) if hasattr(r, "get") else {"ok": True}
            if payload.get("ok"):
                ok_count += 1
            else:
                fail_count += 1
        except Exception:
            fail_count += 1
    return {"ok": True, "total_users": len(users), "success": ok_count, "failed": fail_count}
