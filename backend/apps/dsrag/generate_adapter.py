"""生成适配器：DeepSeek chat/completion（P06）。密钥仅来自环境变量/现网配置。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from apps.dsrag.config import load_base_config
from apps.dsrag.index import build_context
from apps.dsrag.schema import Candidate

# DeepSeek chat 粗略单价（USD / 1M tokens）；cost_est 记单题美元
_INPUT_USD_PER_1M = 0.27
_OUTPUT_USD_PER_1M = 1.10

SYSTEM_PROMPT = (
    "你是私有知识库问答助手。只根据用户提供的【上下文】作答；"
    "不得使用外部常识补全。若上下文不足以回答，明确说「根据现有资料无法回答」。"
    "回答简洁、直接，不要编造引用编号以外的条款。"
)

# R0-prompt：仅靠提示拒答（无独立 D0/D3）。拒答句必须与 REFUSE_TEMPLATE 字面一致，便于规则解析。
REFUSE_TEMPLATE = "根据现有资料无法回答。"
SYSTEM_PROMPT_R0_PROMPT = (
    "你是私有知识库问答助手。只根据【上下文】作答；禁止使用外部常识；禁止编造。"
    "若问题明显超出实验室安全/仪器管理制度服务范围，或上下文不足以给出正确具体答案，"
    f"则整段回答必须且只能输出下面这一句（不要加任何其它字、标点变体或解释）：\n{REFUSE_TEMPLATE}\n"
    "否则用简洁中文直接作答。不得输出拒答句以外的拒绝理由。"
)


def is_template_refuse(text: str, template: str = REFUSE_TEMPLATE) -> bool:
    """口径 A 配套：生成 API 已调用；用固定拒答句识别「实质未答」。"""
    s = (text or "").strip().replace(" ", "").replace("　", "")
    t = (template or "").strip().replace(" ", "").replace("　", "")
    if not s or not t:
        return False
    if s == t:
        return True
    # 允许模型偶发加句号/引号
    s2 = s.strip("「」\"'。．")
    return s2 == t.strip("。．") or t in s and len(s) <= len(t) + 4


@dataclass
class GenerateResult:
    text: str
    latency_ms: float
    cost_est: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.text)


def _resolve_api_key() -> str:
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if key:
        return key
    try:
        from django.conf import settings

        cfg = getattr(settings, "AI_ENGINE_CONFIG", {}).get("deepseek", {}) or {}
        key = (cfg.get("api_key") or "").strip()
        if key:
            return key
    except Exception:
        pass
    return ""


def _api_base() -> str:
    env = (os.getenv("DEEPSEEK_API_BASE") or "").strip()
    if env:
        return env.rstrip("/")
    try:
        from django.conf import settings

        cfg = getattr(settings, "AI_ENGINE_CONFIG", {}).get("deepseek", {}) or {}
        base = (cfg.get("api_base") or cfg.get("base_url") or "").strip()
        if base:
            # settings 可能是完整 /v1/chat/completions
            if base.endswith("/chat/completions"):
                return base[: -len("/chat/completions")].rstrip("/")
            return base.rstrip("/")
    except Exception:
        pass
    return "https://api.deepseek.com"


def _chat_url() -> str:
    base = _api_base()
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def estimate_cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens * _INPUT_USD_PER_1M / 1_000_000.0
        + completion_tokens * _OUTPUT_USD_PER_1M / 1_000_000.0
    )


def build_user_prompt(question: str, context: str) -> str:
    return (
        f"【上下文】\n{context or '（无检索结果）'}\n\n"
        f"【问题】\n{question.strip()}\n\n"
        "请仅依据上下文回答。"
    )


def generate(
    question: str,
    candidates: list[Candidate],
    *,
    base: dict[str, Any] | None = None,
    max_context_chars: int = 4000,
    retries: int = 2,
    timeout: tuple[float, float] = (15.0, 120.0),
    system_prompt: str | None = None,
) -> GenerateResult:
    """检索候选 → 截断上下文 → LLM；始终计一次生成调用意图。"""
    base = base or load_base_config()
    context = build_context(candidates, max_chars=max_context_chars)
    return generate_with_context(
        question,
        context,
        base=base,
        retries=retries,
        timeout=timeout,
        system_prompt=system_prompt,
    )


def chat_completion(
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 512,
    retries: int = 2,
    timeout: tuple[float, float] = (15.0, 120.0),
    base: dict[str, Any] | None = None,
) -> GenerateResult:
    """底层 chat；供 generate / D3 共用。"""
    base = base or load_base_config()
    api_key = _resolve_api_key()
    if not api_key:
        return GenerateResult(text="", latency_ms=0.0, cost_est=0.0, error="missing_DEEPSEEK_API_KEY")

    model_name = model or str(base.get("generator_model") or "deepseek-chat")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": float(temperature),
        "max_tokens": int(max_tokens),
        "stream": False,
    }
    url = _chat_url()
    last_err: Optional[str] = None
    t0 = time.perf_counter()
    for attempt in range(retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code != 200:
                last_err = f"http_{resp.status_code}:{resp.text[:240]}"
                if resp.status_code in (429, 500, 502, 503) and attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                latency_ms = (time.perf_counter() - t0) * 1000.0
                return GenerateResult(text="", latency_ms=latency_ms, cost_est=0.0, error=last_err)
            body = resp.json()
            text = (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""
            usage = body.get("usage") or {}
            pt = int(usage.get("prompt_tokens") or 0)
            ct = int(usage.get("completion_tokens") or 0)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            return GenerateResult(
                text=text.strip(),
                latency_ms=latency_ms,
                cost_est=estimate_cost_usd(pt, ct),
                prompt_tokens=pt,
                completion_tokens=ct,
                error=None if text.strip() else "empty_completion",
            )
        except requests.Timeout:
            last_err = "timeout"
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
        except Exception as e:
            last_err = str(e)
            if attempt < retries:
                time.sleep(1.0 * (attempt + 1))
                continue
    latency_ms = (time.perf_counter() - t0) * 1000.0
    return GenerateResult(text="", latency_ms=latency_ms, cost_est=0.0, error=last_err or "unknown")


def generate_with_context(
    question: str,
    context: str,
    *,
    base: dict[str, Any] | None = None,
    retries: int = 2,
    timeout: tuple[float, float] = (15.0, 120.0),
    system_prompt: str | None = None,
) -> GenerateResult:
    base = base or load_base_config()
    temperature = float(base.get("temperature") if base.get("temperature") is not None else 0)
    max_tokens = int(base.get("max_tokens") or 1024)
    model = str(base.get("generator_model") or "deepseek-chat")
    user = build_user_prompt(question, context)
    return chat_completion(
        system_prompt or SYSTEM_PROMPT,
        user,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        retries=retries,
        timeout=timeout,
        base=base,
    )
