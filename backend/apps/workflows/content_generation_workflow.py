"""
大模型驱动的内容生成工作流
供系统调用：API、定时任务、其他服务
"""
import json
from typing import Dict, Any, List
from django.conf import settings

from apps.knowledge.models import KnowledgeBase, Document
from apps.chat.ai_services import AIServiceFactory


def _get_api_key(model: str) -> str:
    """从配置获取 API Key"""
    provider_key = "deepseek"
    if model.startswith("qwen"):
        provider_key = "qwen"
    elif model.startswith("glm"):
        provider_key = "glm"
    cfg = getattr(settings, "AI_ENGINE_CONFIG", {}).get(provider_key, {})
    api_key = cfg.get("api_key") or ""
    if not api_key:
        try:
            from apps.system.models import APIKeyConfig
            obj = APIKeyConfig.objects.filter(provider=provider_key, is_active=True).first()
            if obj and getattr(obj, "api_key", None):
                api_key = obj.api_key
        except Exception:
            pass
    return api_key or ""


def _model_id_to_full(model_id: str) -> str:
    mapping = {'deepseek': 'deepseek-chat', 'qwen': 'qwen-turbo', 'glm': 'glm-4'}
    return mapping.get(model_id, model_id)


def _gather_kb_text(knowledge_base_id: str, max_chars: int = 50000) -> str:
    """从知识库收集文档文本"""
    docs = Document.objects.filter(
        knowledge_base_id=knowledge_base_id
    ).order_by('-created_at')[:20]
    parts = []
    total = 0
    for d in docs:
        if total >= max_chars:
            break
        chunk = (d.content or "")[:max_chars - total]
        parts.append(f"【{d.title}】\n{chunk}")
        total += len(chunk)
    return "\n\n---\n\n".join(parts)


def _call_ai(prompt: str, system: str, model: str, max_tokens: int = 2000) -> str:
    """调用 AI 生成"""
    api_key = _get_api_key(model)
    if not api_key:
        return ""
    full_model = _model_id_to_full(model)
    ai = AIServiceFactory.create_service(full_model, api_key)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    return (ai.generate_response(messages) or "").strip()


def _strip_json_block(raw: str) -> str:
    """去除 AI 返回的 ```json ... ``` 包裹，便于解析"""
    if not raw or not isinstance(raw, str):
        return raw or ""
    s = raw.strip()
    for prefix in ("```json", "```JSON", "```"):
        if s.startswith(prefix):
            s = s[len(prefix):].lstrip()
            break
    if s.endswith("```"):
        s = s[:-3].rstrip()
    return s


def _generate_summary(text: str, model: str, config: dict) -> dict:
    """生成内容总结"""
    prompt = f"""基于以下知识库内容，生成结构化的内容总结。要求：
1. overview: 一段概述（100字内），纯文本不要 JSON 格式
2. sections: 数组，每项含 title, summary, key_points（3-5个要点）

内容：
---
{text[:15000]}
---

请输出 JSON 格式，不要 markdown 代码块，overview 为普通字符串。"""
    system = "你是专业的知识整理助手。只输出合法 JSON，不要 ```json 包裹。"
    raw = _call_ai(prompt, system, model, config.get('max_tokens', 2000))
    try:
        cleaned = _strip_json_block(raw) if raw else ""
        return json.loads(cleaned) if cleaned else {"overview": "", "sections": []}
    except json.JSONDecodeError:
        overview = (raw or "").replace("```json", "").replace("```", "").strip()
        if overview.startswith("{"):
            try:
                obj = json.loads(overview[:2000])
                return {"overview": obj.get("overview", overview[:200]), "sections": obj.get("sections", [])}
            except Exception:
                pass
        return {"overview": overview[:300] if overview else "", "sections": []}


def _generate_outline(text: str, model: str, config: dict) -> dict:
    """生成学习大纲"""
    prompt = f"""基于以下知识库内容，生成学习大纲。要求：
1. title: 大纲标题
2. description: 简要说明
3. chapters: 数组，每项含 number, title, description, estimated_time, key_topics

内容：
---
{text[:15000]}
---

请输出 JSON 格式。"""
    system = "你是专业的学习设计助手。只输出合法 JSON。"
    raw = _call_ai(prompt, system, model, config.get('max_tokens', 2000))
    try:
        cleaned = _strip_json_block(raw) if raw else ""
        return json.loads(cleaned) if cleaned else {"title": "", "description": "", "chapters": []}
    except json.JSONDecodeError:
        return {"title": "大纲", "description": (raw or "")[:200], "chapters": []}


def _generate_key_concepts(text: str, model: str, config: dict) -> dict:
    """生成关键概念"""
    prompt = f"""基于以下知识库内容，提取关键概念。要求：
1. title: 概念列表标题
2. concepts: 数组，每项含 term, definition, related_docs（可选）

内容：
---
{text[:15000]}
---

请输出 JSON 格式。"""
    system = "你是专业的知识提炼助手。只输出合法 JSON。"
    raw = _call_ai(prompt, system, model, config.get('max_tokens', 2000))
    try:
        cleaned = _strip_json_block(raw) if raw else ""
        return json.loads(cleaned) if cleaned else {"title": "", "concepts": []}
    except json.JSONDecodeError:
        return {"title": "关键概念", "concepts": []}


def _generate_q_and_a(text: str, model: str, config: dict) -> dict:
    """生成问答集"""
    prompt = f"""基于以下知识库内容，生成常见问答。要求：
1. title: 问答集标题
2. questions: 数组，每项含 question, answer

内容：
---
{text[:15000]}
---

请输出 JSON 格式。"""
    system = "你是专业的问答整理助手。只输出合法 JSON。"
    raw = _call_ai(prompt, system, model, config.get('max_tokens', 2000))
    try:
        cleaned = _strip_json_block(raw) if raw else ""
        return json.loads(cleaned) if cleaned else {"title": "", "questions": []}
    except json.JSONDecodeError:
        return {"title": "问答集", "questions": []}


_GENERATORS = {
    'summary': _generate_summary,
    'outline': _generate_outline,
    'key_concepts': _generate_key_concepts,
    'q_and_a': _generate_q_and_a,
}


def run_content_generation_workflow(
    knowledge_base_id: str,
    content_types: List[str],
    ai_model: str = 'deepseek',
    config: dict = None,
    user=None,
) -> Dict[str, Any]:
    """
    执行内容生成工作流（供系统调用）
    
    Returns:
        {
            "success": bool,
            "total_generated": int,
            "generated_contents": [...],
            "error": str | None,
        }
    """
    from .models import WorkflowRun, GeneratedContent, CONTENT_TYPE_DISPLAY
    from django.utils import timezone

    config = config or {}
    kb = KnowledgeBase.objects.filter(id=knowledge_base_id).first()
    if not kb:
        return {"success": False, "total_generated": 0, "generated_contents": [], "error": "知识库不存在"}

    run = WorkflowRun.objects.create(
        workflow_id='content_generation',
        knowledge_base_id=knowledge_base_id,
        user=user,
        status='running',
        input_params={
            'content_types': content_types,
            'ai_model': ai_model,
            'config': config,
        },
    )

    try:
        text = _gather_kb_text(str(knowledge_base_id))
        if not text.strip():
            run.status = 'failed'
            run.error_message = '知识库无文档内容'
            run.finished_at = timezone.now()
            run.save()
            return {"success": False, "total_generated": 0, "generated_contents": [], "error": "知识库无文档内容"}

        generated = []
        for ct in content_types:
            if ct not in _GENERATORS:
                continue
            try:
                data = _GENERATORS[ct](text, ai_model, config)
                obj = GeneratedContent.objects.create(
                    knowledge_base=kb,
                    content_type=ct,
                    content_data=data,
                    ai_model=_model_id_to_full(ai_model),
                    workflow_run=run,
                )
                generated.append({
                    "content_type": ct,
                    "success": True,
                    "id": str(obj.id),
                    "created": True,
                })
            except Exception as e:
                generated.append({"content_type": ct, "success": False, "error": str(e)})

        run.status = 'success'
        run.output_summary = {"total_generated": len([g for g in generated if g.get("success")]), "generated": generated}
        run.finished_at = timezone.now()
        run.save()

        return {
            "success": True,
            "total_generated": len([g for g in generated if g.get("success")]),
            "generated_contents": generated,
        }
    except Exception as e:
        run.status = 'failed'
        run.error_message = str(e)
        run.finished_at = timezone.now()
        run.save()
        return {"success": False, "total_generated": 0, "generated_contents": [], "error": str(e)}
