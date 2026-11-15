# 与设计稿《英语学习定制框架-设计稿-对齐仓库》§2 节点顺序一致（逻辑名）
from __future__ import annotations

WIZARD_GRAPH_NODE_NAMES = (
    "intake_tags",
    "placement_or_confirm",
    "assessment_run",
    "assessment_score",
    "gap_feedback",
    "roadmap_draft_skill",
    "roadmap_hitl",
    "roadmap_finalize_skill",
    "tutor_runtime",
)


def wizard_node_name_at(cursor: int) -> str | None:
    names = WIZARD_GRAPH_NODE_NAMES
    i = int(cursor or 0)
    if i < 0 or i >= len(names):
        return None
    return names[i]
