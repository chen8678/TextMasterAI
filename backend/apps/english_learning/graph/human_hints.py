"""向导图人机暂停点：面向前端的文案与建议步骤。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .nodes import WIZARD_GRAPH_NODE_NAMES

# pending_human_node（刚执行完、等待用户）→ 说明
_PENDING_HINTS: Dict[str, Dict[str, str]] = {
    "placement_or_confirm": {
        "title": "确认测评方式",
        "detail": "请选择「完整测评」或「快速定级」，然后点击组卷。",
        "suggested_step": "1",
    },
    "assessment_run": {
        "title": "完成测评作答",
        "detail": "题目已生成，请逐题选择答案后提交评分。",
        "suggested_step": "1",
    },
    "roadmap_draft_skill": {
        "title": "审阅路线草案",
        "detail": "系统已生成路线草案，请检查加强维度与正文，可在定稿页继续编辑后入库。",
        "suggested_step": "2",
    },
}

# next_nodes[0] → 若尚未执行，补充提示
_NEXT_HINTS: Dict[str, Dict[str, str]] = {
    "assessment_run": {
        "title": "开始组卷",
        "detail": "确认测评方式后将自动抽题。",
        "suggested_step": "1",
    },
    "assessment_score": {
        "title": "提交答案并评分",
        "detail": "作答完成后提交，系统将生成薄弱项说明。",
        "suggested_step": "1",
    },
    "gap_feedback": {
        "title": "查看测评反馈",
        "detail": "即将进入反馈与路线规划步骤。",
        "suggested_step": "2",
    },
    "roadmap_draft_skill": {
        "title": "生成学习路线",
        "detail": "选择加强维度后生成 Markdown 路线草案。",
        "suggested_step": "2",
    },
    "roadmap_hitl": {
        "title": "编辑路线",
        "detail": "可修改路线正文后保存或定稿。",
        "suggested_step": "3",
    },
    "roadmap_finalize_skill": {
        "title": "定稿入库",
        "detail": "确认后将写入您的私有知识库。",
        "suggested_step": "3",
    },
}


def human_action_hint(
    *,
    pending_human_node: Optional[str] = None,
    next_nodes: Optional[List[str]] = None,
    completed: bool = False,
    phase: Optional[str] = None,
) -> Dict[str, Any]:
    """合成前端展示用 `human_action` 对象。"""
    if completed or str(phase or "").lower() == "tutor":
        return {
            "kind": "done",
            "title": "向导已完成",
            "detail": "可前往智能问答或知识库继续学习。",
            "suggested_step": 3,
            "cta_chat": True,
        }
    pending = (pending_human_node or "").strip()
    if pending and pending in _PENDING_HINTS:
        h = dict(_PENDING_HINTS[pending])
        h["kind"] = "wait_input"
        h["pending_node"] = pending
        h["suggested_step"] = int(h.get("suggested_step") or 0)
        return h
    nxt = list(next_nodes or [])
    if nxt:
        nm = nxt[0]
        if nm in _NEXT_HINTS:
            h = dict(_NEXT_HINTS[nm])
            h["kind"] = "next_node"
            h["next_node"] = nm
            h["suggested_step"] = int(h.get("suggested_step") or 0)
            return h
    return {
        "kind": "idle",
        "title": "继续向导",
        "detail": "按当前步骤操作，或查看图观测区状态。",
        "suggested_step": 0,
        "wizard_nodes": list(WIZARD_GRAPH_NODE_NAMES),
    }
