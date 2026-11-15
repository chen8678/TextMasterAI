"""单题打分：join(taskset, prediction) + A 答案归一化匹配（P09 / 02§4）。"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional


_PUNCT_RE = re.compile(r"[\s\W_]+", re.UNICODE)


def normalize_answer(text: str) -> str:
    """短答案归一化：NFKC → 小写 → 去空白与标点。"""
    s = unicodedata.normalize("NFKC", (text or "").strip()).lower()
    s = _PUNCT_RE.sub("", s)
    return s


def answers_match(pred: str, gold: str) -> bool:
    """精确/归一化匹配：归一化后相等，或一方包含另一方（短答案）。"""
    if not gold or not gold.strip():
        return False
    if not pred or not str(pred).strip():
        return False
    a, b = normalize_answer(pred), normalize_answer(gold)
    if not a or not b:
        return False
    if a == b:
        return True
    # 允许「四小时除非特批」vs「连续使用不得超过四小时，除非…特批」
    if b in a or a in b:
        return True
    return False


def _as_bool_pred(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "answerable"):
        return True
    if s in ("false", "0", "no", "not_answerable"):
        return False
    return None


def join_case(task: dict[str, Any], pred: dict[str, Any]) -> dict[str, Any]:
    """合并金标与预测；task 字段优先作金标，pred 覆盖运行结果。"""
    tid = str(task.get("id") or pred.get("id") or "")
    qtype = str(task.get("type") or pred.get("type") or "")
    gold_answer = task.get("gold_answer")
    if gold_answer is None:
        gold_answer = pred.get("gold_answer")
    gold_ans = task.get("answerable")
    if gold_ans is None:
        gold_ans = pred.get("gold_answerable")

    answerable_pred = pred.get("answerable_pred")
    if answerable_pred is None and pred.get("answerable_label"):
        answerable_pred = pred.get("answerable_label") == "answerable"
    answerable_pred = _as_bool_pred(answerable_pred)

    status = str(pred.get("status") or "")
    generated = bool(pred.get("generated"))
    answer_text = str(pred.get("answer_text") or "")

    a_correct: Optional[bool] = None
    a_success: Optional[bool] = None
    if qtype == "A":
        # 成功 = status=answer 且答案正确；拒答或答错均失败
        if status == "answer" and generated and gold_answer:
            a_correct = answers_match(answer_text, str(gold_answer))
            a_success = bool(a_correct)
        else:
            a_correct = False if gold_answer else None
            a_success = False if gold_answer else None

    return {
        "id": tid,
        "type": qtype,
        "split": task.get("split") or pred.get("split"),
        "config_id": pred.get("config_id"),
        "status": status,
        "generated": generated,
        "answer_text": answer_text,
        "gold_answer": gold_answer,
        "gold_answerable": gold_ans,
        "answerable_pred": answerable_pred,
        "answerable_prob": pred.get("answerable_prob"),
        "latency_ms": float(pred.get("latency_ms") or 0.0),
        "cost_est": float(pred.get("cost_est") or 0.0),
        "a_correct": a_correct,
        "a_success": a_success,
        "policy_hash": pred.get("policy_hash"),
        "threshold": pred.get("threshold"),
    }


def score_predictions(
    taskset: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {str(p["id"]): p for p in predictions if p.get("id") is not None}
    scored: list[dict[str, Any]] = []
    missing: list[str] = []
    for t in taskset:
        tid = str(t["id"])
        if tid not in by_id:
            missing.append(tid)
            continue
        scored.append(join_case(t, by_id[tid]))
    if missing:
        # 允许 pred 是 subset（冒烟）；仅对交集打分
        pass
    # 也纳入 pred 有但 taskset 过滤后没有的？不纳入——以传入 taskset 为准
    return scored
