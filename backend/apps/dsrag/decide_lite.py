"""廉价决策头 lite_rule：无 LLM，供 M07 「决策小 / 生成大」对照。

- Scope：关键词与服务范围说明书粗匹配
- Answerable：max(retrieve_score) 与词重叠启发式
不调 τ；只换决策实现。生成仍走 deepseek-chat。
"""

from __future__ import annotations

import re
from typing import Any

from apps.dsrag.schema import AnswerableDecision, Candidate, ScopeDecision

_SCOPE_POS = (
    "实验室",
    "气瓶",
    "危废",
    "化学品",
    "灭火",
    "门禁",
    "仪器",
    "辐射",
    "生物安全",
    "应急",
    "安全",
    "培训",
    "废液",
    "预约",
    "领用",
)
_SCOPE_NEG = (
    "股票",
    "基金",
    "天气",
    "电影",
    "足球",
    "代码",
    "Python",
    "肺炎",
    "吃药",
    "星座",
    "游戏",
    "信用卡",
    "GDP",
    "简历",
    "请假",
)


def decide_scope_lite(question: str, *, scope_spec: str = "") -> tuple[ScopeDecision, bool, float, float, str]:
    q = question or ""
    neg = sum(1 for w in _SCOPE_NEG if w.lower() in q.lower() or w in q)
    pos = sum(1 for w in _SCOPE_POS if w in q)
    # 说明书命中加权
    if scope_spec:
        toks = set(re.findall(r"[\u4e00-\u9fff]{2,}", q))
        hit = sum(1 for t in toks if t in scope_spec)
        if hit >= 2:
            pos += 2
    in_scope = pos > 0 and neg == 0
    if neg > 0 and pos == 0:
        in_scope = False
    if neg > 0 and pos > 0:
        in_scope = neg < pos  # 擦边偏严：否定词多则超纲
        if neg >= 1 and "实验室" not in q and "安全" not in q:
            in_scope = False
    prob = 0.85 if in_scope else 0.15
    d = ScopeDecision(label="in_scope" if in_scope else "out_of_scope", prob=prob)
    return d, in_scope, 0.5, 0.0, "lite_rule_scope"


def decide_answerable_lite(
    question: str,
    candidates: list[Candidate],
    *,
    threshold: float = 0.5,
) -> tuple[AnswerableDecision, bool, float, float, str]:
    max_score = max((c.score for c in candidates), default=0.0)
    q_toks = set(re.findall(r"[\u4e00-\u9fff]{2,}", question or ""))
    ctx = " ".join((c.text or "")[:800] for c in candidates[:3])
    overlap = sum(1 for t in q_toks if t in ctx)
    # 问未写字段常见模式 → 不可答
    missing_cues = ("多少元", "手机号", "网址", "IP", "编号是", "地址在哪", "单价", "支付宝", "下载链接")
    if any(c in (question or "") for c in missing_cues):
        ans = False
        prob = 0.2
        reason = "missing_field_cue"
    elif max_score < 0.12:
        ans = False
        prob = 0.25
        reason = f"low_score={max_score:.3f}"
    elif overlap >= 2 and max_score >= 0.15:
        ans = True
        prob = 0.8
        reason = f"overlap={overlap};score={max_score:.3f}"
    else:
        ans = False
        prob = 0.35
        reason = f"weak_evidence;overlap={overlap}"
    # 与官方一致：pred = (prob >= τ)；lite 直接给出与 ans 一致的 prob
    if ans and prob < threshold:
        prob = threshold
    if (not ans) and prob >= threshold:
        prob = max(0.0, threshold - 0.01)
    pred = prob >= threshold
    d = AnswerableDecision(
        label="answerable" if pred else "not_answerable",
        prob=float(prob),
        reason_short=reason[:40],
    )
    return d, pred, 0.5, 0.0, f"lite_rule_ans;{reason}"
