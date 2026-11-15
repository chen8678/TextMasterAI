"""G2：checkpoint 读写与从 `session_state` 单向覆盖部分图状态键。"""

from __future__ import annotations

from typing import Any, Tuple

from django.db import IntegrityError, transaction

from ..models import EnglishLearningGraphCheckpoint, EnglishLearningProfile
from .phase_cursor import apply_phase_cursor_to_checkpoint, node_cursor_for_session_phase

# 与 `session_state` 对齐、便于断线续跑与后续 LangGraph channel 映射的顶层键
_SESSION_TO_GRAPH_KEYS: Tuple[str, ...] = (
    "phase",
    "learner_constraints",
    "placement_choice",
    "assessment_id",
)


def default_thread_id(profile_pk) -> str:
    return f"el:{profile_pk}"


_GRAPH_SESSION_KEYS: Tuple[str, ...] = ("graph_thread_id", "graph_node_cursor", "graph_current_node")


def apply_graph_projection_to_session_state_dict(profile_pk: int, state: dict) -> bool:
    """将默认线程 checkpoint 投影写入 `state`（就地修改）。若无 checkpoint 则移除 `graph_*` 键。返回是否相对原状有变化。"""
    from .nodes import wizard_node_name_at

    tid = default_thread_id(profile_pk)
    before = {k: state.get(k) for k in _GRAPH_SESSION_KEYS}
    cp = EnglishLearningGraphCheckpoint.objects.filter(profile_id=profile_pk, thread_id=tid).first()
    if cp is None:
        for k in _GRAPH_SESSION_KEYS:
            state.pop(k, None)
    else:
        state["graph_thread_id"] = tid
        state["graph_node_cursor"] = int(cp.node_cursor or 0)
        nm = wizard_node_name_at(int(cp.node_cursor or 0))
        if nm:
            state["graph_current_node"] = nm
        else:
            state.pop("graph_current_node", None)
    after = {k: state.get(k) for k in _GRAPH_SESSION_KEYS}
    return before != after


def sync_graph_projection_into_profile_session(profile: EnglishLearningProfile) -> bool:
    """把 checkpoint 投影写入档案 `session_state`（不修改 `_merge_version`）。"""
    with transaction.atomic():
        locked = EnglishLearningProfile.objects.select_for_update().get(pk=profile.pk)
        st = dict(locked.session_state or {})
        if not apply_graph_projection_to_session_state_dict(profile.pk, st):
            return False
        locked.session_state = st
        locked.save(update_fields=["session_state", "updated_at"])
    return True


def _overlay_session_into_graph_state(
    session_state: dict | None, graph_state: dict | None
) -> Tuple[dict[str, Any], bool]:
    ss = session_state if isinstance(session_state, dict) else {}
    gs = dict(graph_state) if isinstance(graph_state, dict) else {}
    changed = False
    for k in _SESSION_TO_GRAPH_KEYS:
        if k not in ss:
            continue
        if gs.get(k) != ss[k]:
            gs[k] = ss[k]
            changed = True
    # 组卷接口写 `active_assessment_id`，设计稿 channel 名为 `assessment_id`
    aid = ss.get("active_assessment_id") or ss.get("last_assessment_id")
    if aid is not None and aid != "":
        av = str(aid)
        if gs.get("assessment_id") != av:
            gs["assessment_id"] = av
            changed = True
    return gs, changed


def _sync_node_cursor_from_phase(
    session_state: dict | None, node_cursor: int
) -> tuple[int, bool]:
    return apply_phase_cursor_to_checkpoint(
        session_state=session_state, current_cursor=node_cursor
    )


def reconcile_checkpoint_node_cursor(profile: EnglishLearningProfile, cp: EnglishLearningGraphCheckpoint) -> None:
    """按当前 `profile.session_state.phase` 推进 `cp.node_cursor`（只进不退），有变化则保存。"""
    new_cur, changed = _sync_node_cursor_from_phase(profile.session_state, cp.node_cursor)
    if changed:
        cp.node_cursor = new_cur
        cp.save(update_fields=["node_cursor", "updated_at"])


def sync_session_overlay_into_existing_checkpoint(profile_pk, session_state: dict) -> bool:
    """若已存在默认线程 checkpoint，则用当前 `session_state` 覆盖约定键；不自动建表（避免未访问图 API 的用户落库）。"""
    tid = default_thread_id(profile_pk)
    obj = EnglishLearningGraphCheckpoint.objects.filter(profile_id=profile_pk, thread_id=tid).first()
    if obj is None:
        return False
    gs, changed = _overlay_session_into_graph_state(session_state, obj.graph_state)
    new_cur, cur_changed = _sync_node_cursor_from_phase(session_state, obj.node_cursor)
    fields = []
    if changed:
        obj.graph_state = gs
        fields.append("graph_state")
    if cur_changed:
        obj.node_cursor = new_cur
        fields.append("node_cursor")
    if fields:
        fields.append("updated_at")
        obj.save(update_fields=fields)
    return bool(changed or cur_changed)


def get_or_create_default_checkpoint(profile: EnglishLearningProfile) -> EnglishLearningGraphCheckpoint:
    """取或建默认 `thread_id` 的 checkpoint，并把 `session_state` 中约定键合并进 `graph_state`。"""
    tid = default_thread_id(profile.pk)
    obj = EnglishLearningGraphCheckpoint.objects.filter(profile_id=profile.pk, thread_id=tid).first()
    if obj is not None:
        gs, changed = _overlay_session_into_graph_state(profile.session_state, obj.graph_state)
        new_cur, cur_changed = _sync_node_cursor_from_phase(profile.session_state, obj.node_cursor)
        fields = []
        if changed:
            obj.graph_state = gs
            fields.append("graph_state")
        if cur_changed:
            obj.node_cursor = new_cur
            fields.append("node_cursor")
        if fields:
            fields.append("updated_at")
            obj.save(update_fields=fields)
        sync_graph_projection_into_profile_session(profile)
        return obj
    gs, _ = _overlay_session_into_graph_state(profile.session_state, {})
    init_cursor = node_cursor_for_session_phase(profile.session_state) or 0
    try:
        out = EnglishLearningGraphCheckpoint.objects.create(
            profile=profile,
            thread_id=tid,
            graph_state=gs,
            node_cursor=init_cursor,
        )
    except IntegrityError:
        obj = EnglishLearningGraphCheckpoint.objects.get(profile_id=profile.pk, thread_id=tid)
        gs2, changed = _overlay_session_into_graph_state(profile.session_state, obj.graph_state)
        new_cur, cur_changed = _sync_node_cursor_from_phase(profile.session_state, obj.node_cursor)
        fields = []
        if changed:
            obj.graph_state = gs2
            fields.append("graph_state")
        if cur_changed:
            obj.node_cursor = new_cur
            fields.append("node_cursor")
        if fields:
            fields.append("updated_at")
            obj.save(update_fields=fields)
        out = obj
    sync_graph_projection_into_profile_session(profile)
    return out


@transaction.atomic
def save_checkpoint_graph_state(
    profile: EnglishLearningProfile,
    *,
    thread_id: str | None = None,
    graph_state: dict[str, Any],
    node_cursor: int | None = None,
) -> EnglishLearningGraphCheckpoint:
    """在事务内更新整张 checkpoint（供后续 LangGraph 回填或 Worker 使用）。"""
    tid = thread_id or default_thread_id(profile.pk)
    cp = EnglishLearningGraphCheckpoint.objects.select_for_update().filter(
        profile_id=profile.pk, thread_id=tid
    ).first()
    if cp is None:
        cp = EnglishLearningGraphCheckpoint.objects.create(
            profile=profile,
            thread_id=tid,
            graph_state=dict(graph_state or {}),
            node_cursor=int(node_cursor or 0),
        )
    else:
        cp.graph_state = dict(graph_state or {})
        if node_cursor is not None:
            cp.node_cursor = int(node_cursor)
        cp.save(update_fields=["graph_state", "node_cursor", "updated_at"])
    sync_graph_projection_into_profile_session(profile)
    return cp
