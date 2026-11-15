from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal


Coverage = Literal["enough", "insufficient", "conflict"]


@dataclass
class EvidenceItem:
    file_id: str
    unit_id: str
    path: str
    value: str
    unit: str = ""
    source_type: str = "structure"  # vector | structure | open
    score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvidencePack:
    question: str
    items: list[EvidenceItem] = field(default_factory=list)
    coverage: Coverage = "insufficient"
    trace_steps: list[str] = field(default_factory=list)
    domain: str = "construction"
    ablation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "items": [i.to_dict() for i in self.items],
            "coverage": self.coverage,
            "trace_steps": list(self.trace_steps),
            "domain": self.domain,
            "ablation": self.ablation,
        }

    def primary(self) -> EvidenceItem | None:
        return self.items[0] if self.items else None
