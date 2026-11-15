"""
english_profile_from_tags：将用户标签整理为 learner_constraints（MVP 规则为主，可后续接 LLM）。
"""


def execute(
    level_tags=None,
    exam_goal: str = "",
    weekly_minutes: int = 120,
    **kwargs,
) -> dict:
    tags = list(level_tags or [])
    normalized = []
    for t in tags:
        s = str(t).strip()
        if s:
            normalized.append(s)

    cefr = None
    stage_label = None
    for t in normalized:
        u = t.upper()
        low = t.lower()
        if u.startswith("CEFR:"):
            cefr = u.split(":", 1)[-1].strip()
        elif len(u) == 2 and u[0] in "ABC" and u[1] in "12":
            cefr = u
        if low.startswith("stage:primary") or "小学" in low:
            stage_label = "小学"
        elif low.startswith("stage:junior") or "初中" in low or "初一" in low or "初二" in low or "初三" in low:
            stage_label = "初中"
        elif low.startswith("stage:senior") or "高中" in low or "高一" in low or "高二" in low or "高三" in low:
            stage_label = "高中"
        elif low.startswith("stage:cet4") or "四级" in low:
            stage_label = "大学英语四级"
        elif low.startswith("stage:cet6") or "六级" in low:
            stage_label = "大学英语六级"

    learner_constraints = {
        "level_tags": normalized,
        "cefr_estimate": cefr or "unspecified",
        "stage_label": stage_label or "unspecified",
        "exam_goal": (exam_goal or "").strip(),
        "weekly_minutes": max(15, int(weekly_minutes or 120)),
    }
    summary = (
        f"目标标签：{', '.join(normalized) or '（未指定）'}；"
        f"考试/目标：{learner_constraints['exam_goal'] or '无'}；"
        f"每周约 {learner_constraints['weekly_minutes']} 分钟。"
    )
    return {"learner_constraints": learner_constraints, "summary_for_user": summary}
