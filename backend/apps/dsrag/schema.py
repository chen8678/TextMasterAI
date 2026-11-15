"""DS-RAG 数据契约：Candidate / Decision / Trace（与 P05 对齐）。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Literal, Optional

Status = Literal["answer", "refuse_scope", "refuse_evidence"]


@dataclass
class Candidate:
    chunk_id: str
    score: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Candidate":
        return cls(
            chunk_id=str(d["chunk_id"]),
            score=float(d.get("score") or 0.0),
            text=str(d.get("text") or ""),
        )


@dataclass
class ScopeDecision:
    label: str  # in_scope | out_of_scope
    prob: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Optional["ScopeDecision"]:
        if not d:
            return None
        return cls(label=str(d["label"]), prob=float(d.get("prob") or 0.0))


@dataclass
class AnswerableDecision:
    label: str  # answerable | not_answerable
    prob: float
    reason_short: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> Optional["AnswerableDecision"]:
        if not d:
            return None
        return cls(
            label=str(d["label"]),
            prob=float(d.get("prob") or 0.0),
            reason_short=str(d.get("reason_short") or ""),
        )


@dataclass
class Trace:
    """单题运行轨迹；可 json 序列化往返。"""

    id: str
    config_id: str  # R0 | R1 | R2 | R3 | ...
    status: Status
    question: str = ""
    retrieve_ids: list[str] = field(default_factory=list)
    retrieve_scores: list[float] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    scope: Optional[ScopeDecision] = None
    answerable: Optional[AnswerableDecision] = None
    generated: bool = False
    answer_text: str = ""
    latency_ms: float = 0.0
    cost_est: float = 0.0
    policy_hash: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "config_id": self.config_id,
            "status": self.status,
            "question": self.question,
            "retrieve_ids": list(self.retrieve_ids),
            "retrieve_scores": list(self.retrieve_scores),
            "candidates": [c.to_dict() for c in self.candidates],
            "scope": self.scope.to_dict() if self.scope else None,
            "answerable": self.answerable.to_dict() if self.answerable else None,
            "generated": self.generated,
            "answer_text": self.answer_text,
            "latency_ms": self.latency_ms,
            "cost_est": self.cost_est,
            "policy_hash": self.policy_hash,
            "notes": self.notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Trace":
        status = d.get("status") or "answer"
        if status not in ("answer", "refuse_scope", "refuse_evidence"):
            raise ValueError(f"invalid status: {status}")
        cands = [Candidate.from_dict(x) for x in (d.get("candidates") or [])]
        return cls(
            id=str(d["id"]),
            config_id=str(d["config_id"]),
            status=status,  # type: ignore[arg-type]
            question=str(d.get("question") or ""),
            retrieve_ids=[str(x) for x in (d.get("retrieve_ids") or [])],
            retrieve_scores=[float(x) for x in (d.get("retrieve_scores") or [])],
            candidates=cands,
            scope=ScopeDecision.from_dict(d.get("scope")),
            answerable=AnswerableDecision.from_dict(d.get("answerable")),
            generated=bool(d.get("generated")),
            answer_text=str(d.get("answer_text") or ""),
            latency_ms=float(d.get("latency_ms") or 0.0),
            cost_est=float(d.get("cost_est") or 0.0),
            policy_hash=str(d.get("policy_hash") or ""),
            notes=str(d.get("notes") or ""),
        )

    @classmethod
    def from_json(cls, s: str) -> "Trace":
        return cls.from_dict(json.loads(s))

    def prediction_row(self) -> dict[str, Any]:
        """predictions.jsonl 一行（键名预留 scope_*）。"""
        row = {
            "id": self.id,
            "config_id": self.config_id,
            "status": self.status,
            "question": self.question,
            "retrieve_ids": self.retrieve_ids,
            "retrieve_scores": self.retrieve_scores,
            "scope_label": self.scope.label if self.scope else None,
            "scope_prob": self.scope.prob if self.scope else None,
            "answerable_label": self.answerable.label if self.answerable else None,
            "answerable_prob": self.answerable.prob if self.answerable else None,
            "answerable_pred": (
                (self.answerable.label == "answerable") if self.answerable else None
            ),
            "answerable_reason": self.answerable.reason_short if self.answerable else None,
            "generated": self.generated,
            "answer_text": self.answer_text,
            "latency_ms": self.latency_ms,
            "cost_est": self.cost_est,
            "policy_hash": self.policy_hash,
        }
        return row


TRACE_FIELD_NAMES = {f.name for f in fields(Trace)}
