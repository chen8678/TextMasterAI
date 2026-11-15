"""英语学习 Skill 共用：调用默认对话模型生成文本（含 G3+ token 流式）。"""

from __future__ import annotations

import json
from typing import Callable, Optional

import requests
from django.conf import settings

from apps.chat.ai_services import AIServiceFactory

from .stream_context import get_wizard_token_callback


def _get_api_key(model: str) -> str:
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


def _model_config(model: str) -> dict:
    provider_key = "deepseek"
    if model.startswith("qwen"):
        provider_key = "qwen"
    elif model.startswith("glm"):
        provider_key = "glm"
    return getattr(settings, "AI_ENGINE_CONFIG", {}).get(provider_key, {})


def _emit_token(text: str, on_token: Optional[Callable[[str], None]]) -> None:
    if not text:
        return
    if on_token:
        on_token(text)


def _stream_openai_compatible(
    *,
    api_base: str,
    api_key: str,
    model: str,
    messages: list,
    max_tokens: int,
    temperature: float,
    on_token: Optional[Callable[[str], None]],
) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    full = ""
    with requests.post(
        f"{api_base.rstrip('/')}/chat/completions",
        headers=headers,
        json=data,
        stream=True,
        timeout=(15, 120),
    ) as resp:
        resp.raise_for_status()
        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line or not raw_line.startswith("data:"):
                continue
            payload = raw_line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = (choices[0].get("delta") or {}).get("content") or ""
            if delta:
                full += delta
                _emit_token(delta, on_token)
    return full.strip()


def stream_chat_completion(
    system: str,
    user: str,
    model: str = "deepseek-chat",
    max_chars: int = 12000,
    *,
    on_token: Optional[Callable[[str], None]] = None,
) -> str:
    """
    对话补全；若存在 on_token 或 contextvar 回调且 API 支持 stream，则逐 token 推送。
    失败时返回空串。
    """
    text = (user or "")[:max_chars]
    api_key = _get_api_key(model)
    if not api_key:
        return ""

    ctx_cb = get_wizard_token_callback()

    def sink(chunk: str) -> None:
        if on_token:
            on_token(chunk)
        elif ctx_cb:
            ctx_cb(chunk, "roadmap_draft_skill")

    token_sink = on_token or ctx_cb
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]

    try:
        if token_sink and (model.startswith("deepseek") or model.startswith("glm")):
            cfg = _model_config(model)
            model_name = model if not model.startswith("deepseek") else "deepseek-chat"
            return _stream_openai_compatible(
                api_base=cfg.get("api_base", ""),
                api_key=api_key,
                model=model_name,
                messages=messages,
                max_tokens=int(cfg.get("max_tokens") or 4000),
                temperature=float(cfg.get("temperature") or 0.2),
                on_token=sink if token_sink else None,
            )
    except Exception:
        pass

    try:
        ai = AIServiceFactory.create_service(model, api_key)
        result = (ai.generate_response(messages) or "").strip()
        if result and token_sink:
            sink(result)
        return result
    except Exception:
        return ""


def chat_completion(system: str, user: str, model: str = "deepseek-chat", max_chars: int = 12000) -> str:
    """单次对话补全，失败返回空串。"""
    return stream_chat_completion(system=system, user=user, model=model, max_chars=max_chars)
