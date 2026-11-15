"""
文档对比 Skill：对比多份文档的异同
"""
from typing import List, Any
from django.conf import settings
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


def execute(
    documents: List[Any],
    query: str = "",
    model: str = "deepseek-chat",
    max_per_doc: int = 3000,
    **kwargs
) -> dict:
    """
    对比多份文档的异同
    
    Args:
        documents: 文档列表（需有 title、content 属性）
        query: 可选，指定对比维度（如「条款差异」「数据一致性」）
    
    Returns:
        {"comparison": str, "doc_count": int}
    """
    if not documents or len(documents) < 2:
        return {
            "comparison": "需要至少 2 份文档才能进行对比",
            "doc_count": len(documents) if documents else 0,
        }
    
    parts = []
    for i, doc in enumerate(documents[:5], 1):
        title = getattr(doc, "title", f"文档{i}")
        content = (getattr(doc, "content", "") or "")[:max_per_doc]
        parts.append(f"【{title}】\n{content}")
    
    docs_text = "\n\n---\n\n".join(parts)
    aspect = f"，重点对比：{query}" if query else ""
    
    prompt = f"""请对比以下 {len(documents)} 份文档的异同{aspect}。输出结构化的对比分析，包括：
1. 共同点
2. 差异点
3. 简要结论

---
{docs_text}
---

对比分析："""
    
    try:
        api_key = _get_api_key(model)
        if not api_key:
            return {
                "comparison": "[对比失败: 未配置 AI API Key]",
                "doc_count": len(documents),
            }
        ai_service = AIServiceFactory.create_service(model, api_key)
        messages = [
            {"role": "system", "content": "你是一个专业的文档分析助手，擅长对比多份文档的异同。"},
            {"role": "user", "content": prompt},
        ]
        comparison = (ai_service.generate_response(messages) or "").strip()
        return {
            "comparison": comparison,
            "doc_count": len(documents),
        }
    except Exception as e:
        return {
            "comparison": f"[对比生成失败: {str(e)}]",
            "doc_count": len(documents),
        }
