"""D3 Answerable：证据充分性判断（P07）。

决策规则（写死进 policy）：`answerable_pred = (prob >= τ)`。
JSON 解析失败（含重试后）：默认 **拒答**（not_answerable, prob=0）。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from apps.dsrag.config import load_base_config, load_policy
from apps.dsrag.generate_adapter import chat_completion
from apps.dsrag.index import build_context
from apps.dsrag.schema import AnswerableDecision, Candidate

ANSWERABLE_SYSTEM = """你是私有知识库的「证据充分性」判定器（Answerable）。
给定用户问题与检索上下文 C'，判断：仅凭 C' 是否足以给出正确、具体的答案。
规则：
- 主题相近但缺少关键事实/数值/条款 → 不可答（answerable=false）
- 复合问中任一部分缺证据 → 整体不可答
- 上下文与问题无关 / 明确超纲 → 不可答
- 上下文明确包含可直接作答的全部关键信息 → 可答（answerable=true）
- 禁止用外部常识补全；禁止臆测库外内容
- 只输出一个 JSON 对象，不要 markdown 围栏，不要其它文字
字段语义（必须遵守）：
- answerable: 布尔，是否可答
- prob: **P(可答)=P(answerable=true)**，取值 0~1；不可答时必须给低值（建议 ≤0.35），可答时给高值（建议 ≥0.65）
  禁止把 prob 写成「对本次判断的置信度」；它永远是「可答」的概率
- reason_short: 不超过40字中文理由
JSON schema:
{"answerable": true|false, "prob": 0.0到1.0的小数, "reason_short": "..."}
"""

# 解析失败默认拒答（省生成成本、偏保守）
PARSE_FAIL_DEFAULT_REFUSE = True


@dataclass
class AnswerableResult:
    decision: AnswerableDecision
    pred: bool  # answerable_pred = (prob >= τ)
    latency_ms: float
    cost_est: float
    raw_text: str = ""
    parse_ok: bool = True
    notes: str = ""


def _extract_json_obj(text: str) -> dict[str, Any] | None:
    text = (text or "").strip()
    if not text:
        return None
    # strip ```json fences
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
    if "answerable" not in obj or "prob" not in obj:
        return None
    ans = obj["answerable"]
    if isinstance(ans, str):
        ans_l = ans.strip().lower()
        if ans_l in ("true", "yes", "1", "answerable"):
            ans = True
        elif ans_l in ("false", "no", "0", "not_answerable"):
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


def decide_answerable(
    question: str,
    candidates: list[Candidate],
    *,
    threshold: float | None = None,
    base: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    max_context_chars: int = 4000,
    parse_retries: int = 2,
) -> AnswerableResult:
    """question + 与 Generate 相同的 C' → AnswerableDecision。"""
    base = base or load_base_config()
    policy = policy or load_policy()
    τ = float(threshold if threshold is not None else policy.get("answerable_threshold") or 0.5)
    model = str(base.get("answerable_model") or base.get("generator_model") or "deepseek-chat")
    if model.strip().lower() in {"lite_rule", "lite", "rule_lite"}:
        from apps.dsrag.decide_lite import decide_answerable_lite

        d, pred, lat, cost, notes = decide_answerable_lite(question, candidates, threshold=τ)
        return AnswerableResult(
            decision=d,
            pred=pred,
            latency_ms=lat,
            cost_est=cost,
            raw_text="lite_rule",
            parse_ok=True,
            notes=f"{notes};τ={τ}",
        )

    context = build_context(candidates, max_chars=max_context_chars)
    user = (
        f"【上下文 C'】\n{context or '（无检索结果）'}\n\n"
        f"【问题】\n{question.strip()}\n\n"
        "请输出 JSON。"
    )

    last_raw = ""
    total_lat = 0.0
    total_cost = 0.0
    # HTTP 级重试在 chat_completion；此处对「解析失败」再问最多 parse_retries 次
    for attempt in range(parse_retries + 1):
        sys_prompt = ANSWERABLE_SYSTEM
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
        _bool_hint, prob_raw, reason = validated
        # 校准为 p_yes = P(answerable=true)：
        # - 若 bool 与 prob 一致（可答且 prob≥0.5 / 不可答且 prob<0.5）→ 直接用 prob
        # - 若不可答但 prob≥0.5（模型把 prob 当「判断置信度」）→ p_yes = 1-prob
        # - 若可答但 prob<0.5（少见）→ p_yes = 1-prob
        if _bool_hint:
            p_yes = float(prob_raw) if prob_raw >= 0.5 else float(1.0 - prob_raw)
        else:
            p_yes = float(prob_raw) if prob_raw < 0.5 else float(1.0 - prob_raw)
        p_yes = max(0.0, min(1.0, p_yes))
        pred = p_yes >= τ
        label = "answerable" if pred else "not_answerable"
        return AnswerableResult(
            decision=AnswerableDecision(label=label, prob=p_yes, reason_short=reason),
            pred=pred,
            latency_ms=total_lat,
            cost_est=total_cost,
            raw_text=last_raw,
            parse_ok=True,
            notes=(
                f"rule=calibrated_prob_threshold;τ={τ};"
                f"json_answerable={_bool_hint};prob_raw={prob_raw};p_yes={p_yes:.4f}"
            ),
        )

    # 默认拒答
    assert PARSE_FAIL_DEFAULT_REFUSE
    return AnswerableResult(
        decision=AnswerableDecision(
            label="not_answerable",
            prob=0.0,
            reason_short="解析失败默认拒答",
        ),
        pred=False,
        latency_ms=total_lat,
        cost_est=total_cost,
        raw_text=last_raw,
        parse_ok=False,
        notes=f"parse_fail_default=refuse;τ={τ}",
    )
