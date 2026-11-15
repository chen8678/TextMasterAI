"""D0 Scope：服务范围判定（P11）。

决策：先校准为 p_in = P(in_scope)，再 in_scope_pred = (p_in >= τ_scope)。
解析失败默认 **out_of_scope**（拒答，不检索/不生成——由 pipeline 短路）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.dsrag.config import load_base_config, load_policy, resolve_path
from apps.dsrag.generate_adapter import chat_completion
from apps.dsrag.schema import ScopeDecision

SCOPE_SYSTEM = """你是私有知识库问答的「服务范围」判定器（Scope）。
依据【服务范围说明书】判断用户问题是否属于纳入范围。
规则：
- 只根据说明书的纳入/排除/边界句判断，不要根据「库里有没有答案」
- 字面相似但问题本身不在纳入范围 → out_of_scope
- 排除列表中的闲聊、医疗、编程代写、投资等 → out_of_scope
- 实验室安全与仪器管理制度内的制度理解/流程要点 → in_scope
- 只输出一个 JSON，不要 markdown 围栏
字段语义：
- in_scope: 布尔
- prob: **P(in_scope=true)**（不是「判断置信度」）；超纲时给低值≤0.35，在范围内给高值≥0.65
- reason_short: ≤40字中文
JSON schema:
{"in_scope": true|false, "prob": 0.0到1.0, "reason_short": "..."}
"""


@dataclass
class ScopeResult:
    decision: ScopeDecision
    pred: bool  # in_scope
    latency_ms: float
    cost_est: float
    raw_text: str = ""
    parse_ok: bool = True
    notes: str = ""


def load_scope_spec(path: Path | str | None = None, *, base: dict[str, Any] | None = None) -> str:
    base = base or load_base_config()
    p = Path(path) if path else resolve_path(base["scope_spec"])
    return p.read_text(encoding="utf-8")


def _extract_json_obj(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _validate_payload(obj: dict[str, Any]) -> tuple[bool, float, str] | None:
    if "in_scope" not in obj or "prob" not in obj:
        return None
    ans = obj["in_scope"]
    if isinstance(ans, str):
        ans_l = ans.strip().lower()
        if ans_l in ("true", "yes", "1", "in_scope"):
            ans = True
        elif ans_l in ("false", "no", "0", "out_of_scope"):
            ans = False
        else:
            return None
    if not isinstance(ans, bool):
        return None
    try:
        prob = float(obj["prob"])
    except (TypeError, ValueError):
        return None
    if not (0.0 <= prob <= 1.0):
        return None
    reason = str(obj.get("reason_short") or "").strip()[:80]
    return bool(ans), prob, reason


def decide_scope(
    question: str,
    *,
    scope_spec: str | None = None,
    threshold: float | None = None,
    base: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    parse_retries: int = 2,
) -> ScopeResult:
    base = base or load_base_config()
    policy = policy or load_policy()
    τ = float(
        threshold
        if threshold is not None
        else policy.get("scope_threshold")
        if policy.get("scope_threshold") is not None
        else 0.5
    )
    model = str(base.get("answerable_model") or base.get("generator_model") or "deepseek-chat")
    if model.strip().lower() in {"lite_rule", "lite", "rule_lite"}:
        from apps.dsrag.decide_lite import decide_scope_lite

        spec = scope_spec if scope_spec is not None else load_scope_spec(base=base)
        d, pred, lat, cost, notes = decide_scope_lite(question, scope_spec=spec)
        # 对齐 τ：用 decision.prob
        pred = d.prob >= τ
        d = ScopeDecision(label="in_scope" if pred else "out_of_scope", prob=d.prob)
        return ScopeResult(
            decision=d,
            pred=pred,
            latency_ms=lat,
            cost_est=cost,
            raw_text="lite_rule",
            parse_ok=True,
            notes=f"{notes};τ={τ}",
        )
    spec = scope_spec if scope_spec is not None else load_scope_spec(base=base)
    # 截断说明书以免爆上下文
    if len(spec) > 6000:
        spec = spec[:6000] + "\n…(truncated)"

    user = f"【服务范围说明书】\n{spec}\n\n【用户问题】\n{question.strip()}\n\n请输出 JSON。"

    last_raw = ""
    total_lat = 0.0
    total_cost = 0.0
    for attempt in range(parse_retries + 1):
        sys_prompt = SCOPE_SYSTEM
        if attempt > 0:
            sys_prompt += "\n上次输出无法解析，请严格只输出一行合法 JSON。"
        raw = chat_completion(
            sys_prompt,
            user,
            model=model,
            temperature=0.0,
            max_tokens=256,
            retries=1,
            base=base,
        )
        total_lat += raw.latency_ms
        total_cost += raw.cost_est
        last_raw = raw.text or ""
        if raw.error:
            continue
        obj = _extract_json_obj(last_raw)
        if not obj:
            continue
        validated = _validate_payload(obj)
        if not validated:
            continue
        bool_hint, prob_raw, reason = validated
        if bool_hint:
            p_in = float(prob_raw) if prob_raw >= 0.5 else float(1.0 - prob_raw)
        else:
            p_in = float(prob_raw) if prob_raw < 0.5 else float(1.0 - prob_raw)
        p_in = max(0.0, min(1.0, p_in))
        pred = p_in >= τ
        label = "in_scope" if pred else "out_of_scope"
        return ScopeResult(
            decision=ScopeDecision(label=label, prob=p_in),
            pred=pred,
            latency_ms=total_lat,
            cost_est=total_cost,
            raw_text=last_raw,
            parse_ok=True,
            notes=(
                f"rule=calibrated_scope_threshold;τ={τ};"
                f"json_in_scope={bool_hint};prob_raw={prob_raw};p_in={p_in:.4f};reason={reason}"
            ),
        )

    return ScopeResult(
        decision=ScopeDecision(label="out_of_scope", prob=0.0),
        pred=False,
        latency_ms=total_lat,
        cost_est=total_cost,
        raw_text=last_raw,
        parse_ok=False,
        notes=f"parse_fail_default=out_of_scope;τ={τ}",
    )
