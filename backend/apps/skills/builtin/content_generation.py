"""
大模型驱动的内容生成 Skill（关键词触发）
参考 Keyword-Triggered Skills 模式：当用户提问包含「生成总结」「生成摘要」「生成问答集」等关键词时触发工作流
"""
from typing import Dict, Any, List, Optional

# 关键词 → 内容类型映射（参考 OpenHands triggers 模式）
CONTENT_GENERATION_TRIGGERS = {
    'summary': [
        '生成总结', '生成摘要', '总结一下', '做个总结', '内容总结',
        '帮我总结', '总结知识库', '知识库总结', '生成内容总结',
    ],
    'outline': [
        '生成大纲', '学习大纲', '生成学习大纲', '大纲', '知识大纲',
        '帮我生成大纲', '生成知识大纲',
    ],
    'key_concepts': [
        '生成关键概念', '关键概念', '提取概念', '重要术语',
        '帮我提取关键概念', '生成术语',
    ],
    'q_and_a': [
        '生成问答', '生成问答集', '问答集', '常见问题',
        '帮我生成问答', '生成FAQ', '生成常见问题',
    ],
}

# 通用触发词：匹配任意一种即触发
GENERIC_TRIGGERS = [
    '生成学习内容', '生成内容', '学习内容', '内容生成',
    '大模型生成', 'AI生成', '智能生成',
]


def _detect_content_types(question: str) -> List[str]:
    """根据问题文本检测要生成的内容类型"""
    q = (question or '').strip()
    if not q:
        return []
    detected = []
    for content_type, keywords in CONTENT_GENERATION_TRIGGERS.items():
        for kw in keywords:
            if kw in q:
                detected.append(content_type)
                break
    # 若匹配通用触发词但未指定类型，默认生成全部
    for kw in GENERIC_TRIGGERS:
        if kw in q:
            if not detected:
                return ['summary', 'outline', 'key_concepts', 'q_and_a']
            break
    return list(dict.fromkeys(detected))  # 去重保序


def _clean_overview(text: str) -> str:
    """从 overview 中提取纯文本，去除可能的 JSON 包裹"""
    if not text or not isinstance(text, str):
        return ""
    s = text.strip()
    if s.startswith("{") and '"overview"' in s[:50]:
        try:
            import json
            obj = json.loads(s[:2000])
            return (obj.get("overview") or "").strip()
        except Exception:
            pass
    return s


def _format_content_for_answer(contents: List[Dict]) -> str:
    """将生成的结构化内容格式化为可读回答"""
    from apps.workflows.models import CONTENT_TYPE_DISPLAY

    parts = []
    for item in contents:
        ct = item.get('content_type', '')
        data = item.get('content_data') or {}
        display_name = CONTENT_TYPE_DISPLAY.get(ct, ct)

        if ct == 'summary':
            overview = _clean_overview(data.get('overview', '') or "")
            sections = data.get('sections', [])
            buf = [f"## {display_name}\n\n{overview}\n"]
            for s in sections[:5]:
                buf.append(f"### {s.get('title', '')}\n{s.get('summary', '')}")
                for p in (s.get('key_points') or [])[:3]:
                    buf.append(f"- {p}")
            parts.append('\n'.join(buf))

        elif ct == 'outline':
            title = data.get('title', '')
            desc = data.get('description', '')
            chapters = data.get('chapters', [])
            buf = [f"## {display_name}\n\n**{title}**\n{desc}\n\n"]
            for ch in chapters[:8]:
                buf.append(f"### {ch.get('number', '')} {ch.get('title', '')}\n{ch.get('description', '')}")
            parts.append('\n'.join(buf))

        elif ct == 'key_concepts':
            title = data.get('title', '')
            concepts = data.get('concepts', [])
            buf = [f"## {display_name}\n\n**{title}**\n\n"]
            for c in concepts[:15]:
                buf.append(f"- **{c.get('term', '')}**：{c.get('definition', '')}")
            parts.append('\n'.join(buf))

        elif ct == 'q_and_a':
            title = data.get('title', '')
            questions = data.get('questions', [])
            buf = [f"## {display_name}\n\n**{title}**\n\n"]
            for qa in questions[:10]:
                buf.append(f"**Q：** {qa.get('question', '')}\n**A：** {qa.get('answer', '')}\n")
            parts.append('\n'.join(buf))

    return '\n\n---\n\n'.join(parts) if parts else '暂无生成内容。'


def execute(
    question: str,
    knowledge_base_id: str,
    user=None,
    ai_model: str = 'deepseek',
    config: dict = None,
    **kwargs,
) -> dict:
    """
    内容生成 Skill：关键词触发，调用大模型驱动的内容生成工作流

    输入：
        question: 用户问题（含触发关键词）
        knowledge_base_id: 知识库 ID
        user: 当前用户
        ai_model: AI 模型（默认 deepseek）
        config: 生成配置

    输出：
        {
            "triggered": bool,        # 是否被触发
            "content_types": [...],   # 生成的内容类型
            "answer": str,            # 格式化后的回答（可直接展示）
            "total_generated": int,
            "error": str | None,
        }
    """
    content_types = _detect_content_types(question)
    if not content_types:
        return {"triggered": False, "content_types": [], "answer": "", "total_generated": 0, "error": None}

    from apps.workflows.content_generation_workflow import run_content_generation_workflow
    from apps.workflows.models import GeneratedContent

    result = run_content_generation_workflow(
        knowledge_base_id=str(knowledge_base_id),
        content_types=content_types,
        ai_model=ai_model or 'deepseek',
        config=config or {},
        user=user,
    )

    if not result.get('success'):
        return {
            "triggered": True,
            "content_types": content_types,
            "answer": "内容生成失败：" + str(result.get("error") or "未知错误"),
            "total_generated": 0,
            "error": result.get("error"),
        }

    # 从 generated_contents 的 id 反查 content_data
    contents = []
    for g in result.get('generated_contents') or []:
        if g.get('success') and g.get('id'):
            obj = GeneratedContent.objects.filter(id=g['id']).first()
            if obj:
                contents.append({
                    'content_type': obj.content_type,
                    'content_data': obj.content_data,
                })

    answer = _format_content_for_answer(contents)
    return {
        "triggered": True,
        "content_types": content_types,
        "answer": answer or ("已生成 %d 种学习内容，请到知识库详情页查看。" % (result.get("total_generated") or 0)),
        "total_generated": result.get('total_generated', 0),
        "error": None,
    }
