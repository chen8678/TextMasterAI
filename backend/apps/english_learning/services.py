from typing import Optional

from django.db import transaction

from apps.knowledge.models import KnowledgeBase

from .blackboard import normalize_quiet_hours_dict
from .models import EnglishLearningProfile


class SessionStateVersionConflict(Exception):
    """PATCH 携带的 session_state_version 与当前不一致（乐观锁）。"""

    def __init__(self, current_version: int):
        self.current_version = int(current_version)
        super().__init__("session_state version mismatch")


def get_or_create_profile(user) -> EnglishLearningProfile:
    profile, created = EnglishLearningProfile.objects.get_or_create(user=user)
    if profile.default_kb_id is None:
        kb = KnowledgeBase.objects.create(
            title=f"英语学习 · {getattr(user, 'username', None) or user.pk}",
            owner=user,
            category="education",
            description="英语学习定制：个人学习路线与定稿文档（系统自动创建，非教材库）",
        )
        profile.default_kb = kb
        profile.save(update_fields=["default_kb", "updated_at"])
    try:
        from .curriculum.services import ensure_user_curriculum_access

        ensure_user_curriculum_access(user)
    except Exception:
        pass
    return profile


def merge_session_state(
    profile: EnglishLearningProfile,
    patch: dict,
    expect_version: Optional[int] = None,
) -> dict:
    """合并 session_state；在事务内加行锁。每次成功合并后递增 _merge_version（供 PATCH 乐观锁）。"""
    with transaction.atomic():
        locked = EnglishLearningProfile.objects.select_for_update().get(pk=profile.pk)
        state = dict(locked.session_state or {})
        current_ver = int(state.get("_merge_version") or 0)
        if expect_version is not None:
            try:
                ev = int(expect_version)
            except (TypeError, ValueError):
                ev = None
            if ev is not None and ev != current_ver:
                raise SessionStateVersionConflict(current_ver)

        patch = dict(patch or {})
        patch.pop("_merge_version", None)
        old_phase = str(state.get("phase") or "").strip().lower() if "phase" in patch else None
        # 浅合并顶层键的前提下，对 reminder_prefs / quiet_hours 做子字典合并，避免 PATCH 误删其它偏好。
        if isinstance(patch.get("reminder_prefs"), dict):
            rp_prev = state.get("reminder_prefs")
            rp_prev = rp_prev if isinstance(rp_prev, dict) else {}
            merged_rp = dict(rp_prev)
            for k, v in patch["reminder_prefs"].items():
                if k == "quiet_hours" and isinstance(v, dict):
                    qh_prev = merged_rp.get("quiet_hours")
                    qh_prev = qh_prev if isinstance(qh_prev, dict) else {}
                    merged_rp["quiet_hours"] = {**qh_prev, **v}
                else:
                    merged_rp[k] = v
            if isinstance(merged_rp.get("quiet_hours"), dict):
                merged_rp["quiet_hours"] = normalize_quiet_hours_dict(merged_rp["quiet_hours"])
            patch = {**patch, "reminder_prefs": merged_rp}
        state.update(patch)
        state["_merge_version"] = current_ver + 1
        locked.session_state = state
        locked.save(update_fields=["session_state", "updated_at"])
        from .graph.checkpoint_store import (
            apply_graph_projection_to_session_state_dict,
            sync_session_overlay_into_existing_checkpoint,
        )

        sync_session_overlay_into_existing_checkpoint(locked.pk, state)
        locked.refresh_from_db()
        st2 = dict(locked.session_state or {})
        if apply_graph_projection_to_session_state_dict(locked.pk, st2):
            locked.session_state = st2
            locked.save(update_fields=["session_state", "updated_at"])
        if old_phase is not None:
            new_phase = str((locked.session_state or {}).get("phase") or "").strip().lower()
            if new_phase != old_phase:
                from .graph.langgraph_sync import maybe_sync_langgraph_on_phase_change

                maybe_sync_langgraph_on_phase_change(locked)
    profile.refresh_from_db()
    return dict(profile.session_state or {})
