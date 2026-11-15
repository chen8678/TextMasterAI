"""
摘要生成 Skill：对给定文本生成摘要
"""
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
    text: str,
    max_length: int = 500,
    model: str = "deepseek-chat",
    **kwargs
) -> dict:
    """
    对文本生成摘要
    
    Args:
        text: 待摘要的文本
        max_length: 摘要最大长度（字符）
    
    Returns:
        {"summary": str, "original_length": int, "summary_length": int}
    """
    if not text or not text.strip():
        return {
            "summary": "",
            "original_length": 0,
            "summary_length": 0,
        }
    
    prompt = f"""请对以下内容生成简洁摘要，控制在 {max_length} 字以内，保留核心要点：

---
{text[:15000]}
---

摘要："""
    
    try:
        api_key = _get_api_key(model)
        if not api_key:
            return {
                "summary": "[摘要生成失败: 未配置 AI API Key]",
                "original_length": len(text),
                "summary_length": 0,
            }
        ai_service = AIServiceFactory.create_service(model, api_key)
        messages = [
            {"role": "system", "content": "你是一个专业的摘要助手，请简洁准确地概括内容要点。"},
            {"role": "user", "content": prompt},
        ]
        summary = (ai_service.generate_response(messages) or "").strip()
        return {
            "summary": summary,
            "original_length": len(text),
            "summary_length": len(summary),
        }
    except Exception as e:
        return {
            "summary": f"[摘要生成失败: {str(e)}]",
            "original_length": len(text),
            "summary_length": 0,
        }
