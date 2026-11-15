"""根据向导 `session_state.phase` 推断占位 `node_cursor`（与 `WIZARD_GRAPH_NODE_NAMES` 对齐）。"""

from __future__ import annotations

from typing import Optional

from .nodes import WIZARD_GRAPH_NODE_NAMES


# 与 `views.merge_session_state` / `blackboard` 中 phase 取值对齐；未知 phase 不强行改游标
_PHASE_TO_CURSOR: dict[str, int] = {
    "intake": 0,
    "assessment": 2,
    "roadmap": 4,
    "roadmap_review": 6,
    "roadmap_editing": 6,
    "tutor": 8,
}


def node_cursor_for_session_phase(session_state: dict | None) -> Optional[int]:
    ph = str((session_state or {}).get("phase") or "").strip().lower()
    if not ph:
        return None
    i = _PHASE_TO_CURSOR.get(ph)
    if i is None:
        return None
    return clamp_node_cursor(i)


def clamp_node_cursor(i: int) -> int:
    n = len(WIZARD_GRAPH_NODE_NAMES)
    return min(max(0, int(i)), max(0, n - 1))


def apply_phase_cursor_to_checkpoint(
    *,
    session_state: dict | None,
    current_cursor: int,
) -> tuple[int, bool]:
    """用 `phase` 推断游标下界：只推进、不回退（避免占位 `advance_cursor` 被 intake 等阶段覆盖）。"""
    suggested = node_cursor_for_session_phase(session_state)
    if suggested is None:
        return int(current_cursor or 0), False
    cur = clamp_node_cursor(int(current_cursor or 0))
    new_cur = max(cur, suggested)
    if new_cur == cur:
        return cur, False
    return new_cur, True
