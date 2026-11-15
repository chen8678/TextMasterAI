"""DS-RAG 管道：R0 / R1 / R2 / R3。"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from apps.dsrag.config import load_merged
from apps.dsrag.decide_answerable import decide_answerable
from apps.dsrag.decide_scope import decide_scope
from apps.dsrag.generate_adapter import (
    SYSTEM_PROMPT_R0_PROMPT,
    generate,
    is_template_refuse,
)
from apps.dsrag.retrieve_adapter import retrieve_chunks
from apps.dsrag.schema import AnswerableDecision, Trace


def run_r0(
    case: dict[str, Any],
    *,
    merged: dict[str, Any] | None = None,
    index_dir: Path | str | None = None,
) -> Trace:
    """R0: retrieve → always generate。"""
    merged = merged or load_merged()
    base = merged["base"]
    policy_hash = str(merged["policy_hash"])
    qid = str(case["id"])
    question = str(case.get("question") or "")

    t0 = time.perf_counter()
    cands = retrieve_chunks(question, base=base, index_dir=index_dir)
    gen = generate(question, cands, base=base)
    wall_ms = (time.perf_counter() - t0) * 1000.0

    notes = ""
    if gen.error:
        notes = f"generate_error:{gen.error}"
        answer_text = gen.text or f"[generate_failed] {gen.error}"
    else:
        answer_text = gen.text

    return Trace(
        id=qid,
        config_id="R0",
        status="answer",
        question=question,
        retrieve_ids=[c.chunk_id for c in cands],
        retrieve_scores=[c.score for c in cands],
        candidates=cands,
        scope=None,
        answerable=None,
        generated=True,
        answer_text=answer_text,
        latency_ms=float(gen.latency_ms or wall_ms),
        cost_est=float(gen.cost_est or 0.0),
        policy_hash=policy_hash,
        notes=notes,
    )


def run_r0_prompt(
    case: dict[str, Any],
    *,
    merged: dict[str, Any] | None = None,
    index_dir: Path | str | None = None,
) -> Trace:
    """
    R0-prompt：retrieve → always generate（强拒答 system prompt）；无独立 D0/D3。
    Gen 口径 A：凡调用生成 API 则 generated=true。
    用固定拒答句规则解析，写入 answerable_*，以便汇总 B leak / A block / C 实质答案率。
    """
    merged = merged or load_merged()
    base = merged["base"]
    policy_hash = str(merged["policy_hash"])
    qid = str(case["id"])
    question = str(case.get("question") or "")

    t0 = time.perf_counter()
    cands = retrieve_chunks(question, base=base, index_dir=index_dir)
    gen = generate(question, cands, base=base, system_prompt=SYSTEM_PROMPT_R0_PROMPT)
    wall_ms = (time.perf_counter() - t0) * 1000.0

    notes = "gen_rule=A;refuse_parse=template"
    if gen.error:
        notes = f"generate_error:{gen.error};{notes}"
        answer_text = gen.text or f"[generate_failed] {gen.error}"
    else:
        answer_text = gen.text

    refused = is_template_refuse(answer_text)
    ans = AnswerableDecision(
        label="not_answerable" if refused else "answerable",
        prob=0.0 if refused else 1.0,
        reason_short="template_refuse" if refused else "substantive_answer",
    )
    notes = f"{notes};template_refuse={str(refused).lower()}"

    return Trace(
        id=qid,
        config_id="R0-prompt",
        status="answer",
        question=question,
        retrieve_ids=[c.chunk_id for c in cands],
        retrieve_scores=[c.score for c in cands],
        candidates=cands,
        scope=None,
        answerable=ans,
        generated=True,
        answer_text=answer_text,
        latency_ms=float(gen.latency_ms or wall_ms),
        cost_est=float(gen.cost_est or 0.0),
        policy_hash=policy_hash,
        notes=notes,
    )


def run_r1(
    case: dict[str, Any],
    *,
    scope_threshold: float | None = None,
    merged: dict[str, Any] | None = None,
    index_dir: Path | str | None = None,
) -> Trace:
    """R1: Scope? → retrieve → generate。"""
    merged = merged or load_merged()
    base = merged["base"]
    policy = merged["policy"]
    policy_hash = str(merged["policy_hash"])
    qid = str(case["id"])
    question = str(case.get("question") or "")

    t0 = time.perf_counter()
    d0 = decide_scope(
        question,
        threshold=scope_threshold,
        base=base,
        policy=policy,
    )
    if not d0.pred:
        wall_ms = (time.perf_counter() - t0) * 1000.0
        return Trace(
            id=qid,
            config_id="R1",
            status="refuse_scope",
            question=question,
            retrieve_ids=[],
            retrieve_scores=[],
            candidates=[],
            scope=d0.decision,
            answerable=None,
            generated=False,
            answer_text="",
            latency_ms=float(d0.latency_ms or wall_ms),
            cost_est=float(d0.cost_est or 0.0),
            policy_hash=policy_hash,
            notes=f"d0_short_circuit;generate_invoked=false;{d0.notes}",
        )

    cands = retrieve_chunks(question, base=base, index_dir=index_dir)
    gen = generate(question, cands, base=base)
    wall_ms = (time.perf_counter() - t0) * 1000.0
    notes = f"generate_invoked=true;{d0.notes}"
    if gen.error:
        notes = f"generate_error:{gen.error};{notes}"
        answer_text = gen.text or f"[generate_failed] {gen.error}"
    else:
        answer_text = gen.text

    return Trace(
        id=qid,
        config_id="R1",
        status="answer",
        question=question,
        retrieve_ids=[c.chunk_id for c in cands],
        retrieve_scores=[c.score for c in cands],
        candidates=cands,
        scope=d0.decision,
        answerable=None,
        generated=True,
        answer_text=answer_text,
        latency_ms=float((d0.latency_ms or 0.0) + (gen.latency_ms or 0.0) or wall_ms),
        cost_est=float((d0.cost_est or 0.0) + (gen.cost_est or 0.0)),
        policy_hash=policy_hash,
        notes=notes,
    )


def run_r2(
    case: dict[str, Any],
    *,
    threshold: float | None = None,
    merged: dict[str, Any] | None = None,
    index_dir: Path | str | None = None,
) -> Trace:
    """R2: retrieve → Answerable? → generate。"""
    merged = merged or load_merged()
    base = merged["base"]
    policy = merged["policy"]
    policy_hash = str(merged["policy_hash"])
    qid = str(case["id"])
    question = str(case.get("question") or "")
    τ = float(
        threshold
        if threshold is not None
        else policy.get("answerable_threshold")
        if policy.get("answerable_threshold") is not None
        else 0.5
    )

    t0 = time.perf_counter()
    cands = retrieve_chunks(question, base=base, index_dir=index_dir)
    d3 = decide_answerable(
        question,
        cands,
        threshold=τ,
        base=base,
        policy=policy,
    )

    if not d3.pred:
        wall_ms = (time.perf_counter() - t0) * 1000.0
        return Trace(
            id=qid,
            config_id="R2",
            status="refuse_evidence",
            question=question,
            retrieve_ids=[c.chunk_id for c in cands],
            retrieve_scores=[c.score for c in cands],
            candidates=cands,
            scope=None,
            answerable=d3.decision,
            generated=False,
            answer_text="",
            latency_ms=float(d3.latency_ms or wall_ms),
            cost_est=float(d3.cost_est or 0.0),
            policy_hash=policy_hash,
            notes=f"d3_short_circuit;generate_invoked=false;{d3.notes}",
        )

    gen = generate(question, cands, base=base)
    wall_ms = (time.perf_counter() - t0) * 1000.0
    notes = f"generate_invoked=true;{d3.notes}"
    if gen.error:
        notes = f"generate_error:{gen.error};{notes}"
        answer_text = gen.text or f"[generate_failed] {gen.error}"
    else:
        answer_text = gen.text

    return Trace(
        id=qid,
        config_id="R2",
        status="answer",
        question=question,
        retrieve_ids=[c.chunk_id for c in cands],
        retrieve_scores=[c.score for c in cands],
        candidates=cands,
        scope=None,
        answerable=d3.decision,
        generated=True,
        answer_text=answer_text,
        latency_ms=float((d3.latency_ms or 0.0) + (gen.latency_ms or 0.0) or wall_ms),
        cost_est=float((d3.cost_est or 0.0) + (gen.cost_est or 0.0)),
        policy_hash=policy_hash,
        notes=notes,
    )


def run_r3(
    case: dict[str, Any],
    *,
    scope_threshold: float | None = None,
    threshold: float | None = None,
    merged: dict[str, Any] | None = None,
    index_dir: Path | str | None = None,
) -> Trace:
    """R3: Scope? → retrieve → Answerable? → generate。"""
    merged = merged or load_merged()
    base = merged["base"]
    policy = merged["policy"]
    policy_hash = str(merged["policy_hash"])
    qid = str(case["id"])
    question = str(case.get("question") or "")
    τ = float(
        threshold
        if threshold is not None
        else policy.get("answerable_threshold")
        if policy.get("answerable_threshold") is not None
        else 0.5
    )

    t0 = time.perf_counter()
    d0 = decide_scope(
        question,
        threshold=scope_threshold,
        base=base,
        policy=policy,
    )
    if not d0.pred:
        wall_ms = (time.perf_counter() - t0) * 1000.0
        return Trace(
            id=qid,
            config_id="R3",
            status="refuse_scope",
            question=question,
            retrieve_ids=[],
            retrieve_scores=[],
            candidates=[],
            scope=d0.decision,
            answerable=None,
            generated=False,
            answer_text="",
            latency_ms=float(d0.latency_ms or wall_ms),
            cost_est=float(d0.cost_est or 0.0),
            policy_hash=policy_hash,
            notes=f"d0_short_circuit;generate_invoked=false;{d0.notes}",
        )

    cands = retrieve_chunks(question, base=base, index_dir=index_dir)
    d3 = decide_answerable(
        question,
        cands,
        threshold=τ,
        base=base,
        policy=policy,
    )
    if not d3.pred:
        wall_ms = (time.perf_counter() - t0) * 1000.0
        return Trace(
            id=qid,
            config_id="R3",
            status="refuse_evidence",
            question=question,
            retrieve_ids=[c.chunk_id for c in cands],
            retrieve_scores=[c.score for c in cands],
            candidates=cands,
            scope=d0.decision,
            answerable=d3.decision,
            generated=False,
            answer_text="",
            latency_ms=float((d0.latency_ms or 0.0) + (d3.latency_ms or 0.0) or wall_ms),
            cost_est=float((d0.cost_est or 0.0) + (d3.cost_est or 0.0)),
            policy_hash=policy_hash,
            notes=f"d3_short_circuit;generate_invoked=false;{d0.notes};{d3.notes}",
        )

    gen = generate(question, cands, base=base)
    wall_ms = (time.perf_counter() - t0) * 1000.0
    notes = f"generate_invoked=true;{d0.notes};{d3.notes}"
    if gen.error:
        notes = f"generate_error:{gen.error};{notes}"
        answer_text = gen.text or f"[generate_failed] {gen.error}"
    else:
        answer_text = gen.text

    return Trace(
        id=qid,
        config_id="R3",
        status="answer",
        question=question,
        retrieve_ids=[c.chunk_id for c in cands],
        retrieve_scores=[c.score for c in cands],
        candidates=cands,
        scope=d0.decision,
        answerable=d3.decision,
        generated=True,
        answer_text=answer_text,
        latency_ms=float(
            (d0.latency_ms or 0.0) + (d3.latency_ms or 0.0) + (gen.latency_ms or 0.0) or wall_ms
        ),
        cost_est=float((d0.cost_est or 0.0) + (d3.cost_est or 0.0) + (gen.cost_est or 0.0)),
        policy_hash=policy_hash,
        notes=notes,
    )


def run_r2_rule(
    case: dict[str, Any],
    *,
    tau_rule: float | None = None,
    merged: dict[str, Any] | None = None,
    index_dir: Path | str | None = None,
) -> Trace:
    """
    R2-rule: retrieve → if max(score) < τ_rule → refuse_evidence else generate。
    不走 Answerable LLM；对照证明 D3 不是 max(score) 马甲。
    """
    merged = merged or load_merged()
    base = merged["base"]
    policy = merged["policy"]
    policy_hash = str(merged["policy_hash"])
    qid = str(case["id"])
    question = str(case.get("question") or "")
    τ = float(
        tau_rule
        if tau_rule is not None
        else policy.get("score_threshold")
        if policy.get("score_threshold") is not None
        else 0.15
    )

    t0 = time.perf_counter()
    cands = retrieve_chunks(question, base=base, index_dir=index_dir)
    max_score = max((c.score for c in cands), default=0.0)
    pass_gate = max_score >= τ

    if not pass_gate:
        wall_ms = (time.perf_counter() - t0) * 1000.0
        return Trace(
            id=qid,
            config_id="R2-rule",
            status="refuse_evidence",
            question=question,
            retrieve_ids=[c.chunk_id for c in cands],
            retrieve_scores=[c.score for c in cands],
            candidates=cands,
            scope=None,
            answerable=None,
            generated=False,
            answer_text="",
            latency_ms=float(wall_ms),
            cost_est=0.0,
            policy_hash=policy_hash,
            notes=f"r2_rule_short_circuit;generate_invoked=false;max_score={max_score:.6f};τ_rule={τ}",
        )

    gen = generate(question, cands, base=base)
    wall_ms = (time.perf_counter() - t0) * 1000.0
    notes = f"generate_invoked=true;max_score={max_score:.6f};τ_rule={τ}"
    if gen.error:
        notes = f"generate_error:{gen.error};{notes}"
        answer_text = gen.text or f"[generate_failed] {gen.error}"
    else:
        answer_text = gen.text

    return Trace(
        id=qid,
        config_id="R2-rule",
        status="answer",
        question=question,
        retrieve_ids=[c.chunk_id for c in cands],
        retrieve_scores=[c.score for c in cands],
        candidates=cands,
        scope=None,
        answerable=None,
        generated=True,
        answer_text=answer_text,
        latency_ms=float(gen.latency_ms or wall_ms),
        cost_est=float(gen.cost_est or 0.0),
        policy_hash=policy_hash,
        notes=notes,
    )


RUNNERS = {
    "R0": run_r0,
    "R0-prompt": run_r0_prompt,
    "R1": run_r1,
    "R2": run_r2,
    "R3": run_r3,
    "R2-rule": run_r2_rule,
}
