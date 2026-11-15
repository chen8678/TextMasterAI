"""
english_roadmap_draft：根据测评与加强维度生成学习路线 Markdown + outline_json。
"""

import json
import re

from .llm_utils import stream_chat_completion


_DIM_ZH = {
    "vocabulary": "词汇",
    "grammar": "语法",
    "reading": "阅读",
    "listening": "听力",
    "writing": "写作",
}


def _fallback_markdown(scores, gap_summary, focus_dimensions, learner_constraints):
    lc = learner_constraints or {}
    tags = ", ".join(lc.get("level_tags") or []) or "通用"
    focus = ", ".join(_DIM_ZH.get(d, d) for d in (focus_dimensions or [])) or "均衡"
    overall = (scores or {}).get("overall_percent", 0)
    weekly = lc.get("weekly_minutes") or 120
    exam_goal = (lc.get("exam_goal") or "").strip()
    learner_note = (lc.get("learner_note") or "").strip()
    lines = [
        "# 大学英语四级 · 学习报告与路线（草案）",
        "",
        f"- **目标**：{exam_goal or '大学英语四级'}",
        f"- **学段标签**：{tags}",
        f"- **测评得分（约）**：{overall}%",
        f"- **加强维度**：{focus}",
        f"- **每周可投入**：约 {weekly} 分钟",
    ]
    if learner_note:
        lines.append(f"- **你想补充学习的内容**：{learner_note}")
    lines.extend(
        [
            "",
            "## 第 1–2 周：四级基础巩固",
            "- 每天：20 分钟四级核心词汇（结合预置词库）",
            "- 每周 3 次：针对薄弱维度的语法/阅读练习",
            "",
            "## 第 3–4 周：题型与应用",
            "- 每周 2 次：四级阅读短文 + 中文/英文摘要",
            "- 每周 1 次：听力跟读或写作提纲练习",
            "",
            "## 测评反馈摘要",
            gap_summary or "（暂无）",
        ]
    )
    md = "\n".join(lines)
    outline = {
        "weeks": [
            {"week": "1-2", "theme": "foundation", "tasks": ["vocabulary", "grammar"]},
            {"week": "3-4", "theme": "application", "tasks": ["reading", "writing_or_listening"]},
        ]
    }
    return md, outline


def _extract_json_object(text: str):
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text, flags=re.MULTILINE)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


def execute(
    scores=None,
    gap_summary: str = "",
    focus_dimensions=None,
    learner_constraints=None,
    model: str = "deepseek-chat",
    **kwargs,
) -> dict:
    focus_dimensions = list(focus_dimensions or [])
    scores = scores or {}
    payload = json.dumps(
        {
            "scores": scores,
            "gap_summary": gap_summary,
            "focus_dimensions": focus_dimensions,
            "learner_constraints": learner_constraints or {},
        },
        ensure_ascii=False,
        indent=2,
    )
    system = """你是一位面向中国大学生的四级（CET-4）学习规划师。根据输入的测评分数、薄弱项、学段标签，以及 learner_constraints.learner_note（学生自己想学的补充内容），生成「学习报告 + 可执行路线」。

输出要求：仅输出合法 JSON，包含两个键：
  "roadmap_markdown": string —— Markdown 正文，**全部使用简体中文**（标题、说明、任务描述均用中文；英文单词/短语作为学习内容可以出现，但不要用英文写章节标题或说明句）。开头用简短报告总结测评表现，再给出分周路线。
  "outline_json": object —— 供下游 Agent 使用的结构化大纲（weeks/phases、tasks 等，键名可用英文）。

路线应紧扣四级，结合 weekly_minutes、focus_dimensions 与 learner_note，给出可执行任务（听力、阅读、词汇、写作、真题练习等）。
不要输出 markdown 代码块，不要输出 JSON 以外的任何文字。"""

    raw = stream_chat_completion(system=system, user=payload, model=model, max_chars=8000)
    parsed = _extract_json_object(raw) if raw else None

    if isinstance(parsed, dict) and parsed.get("roadmap_markdown"):
        return {
            "roadmap_markdown": str(parsed["roadmap_markdown"]).strip(),
            "outline_json": parsed.get("outline_json") or {},
        }

    md, outline = _fallback_markdown(scores, gap_summary, focus_dimensions, learner_constraints)
    return {"roadmap_markdown": md, "outline_json": outline}
