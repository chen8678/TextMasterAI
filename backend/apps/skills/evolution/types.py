from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ChangeDraft:
    """结构化进化增量（MVP：以 Markdown 区块为主，可扩展为 JSON patch）。"""

    skill_id: str
    markdown_section: str
    provenance: str = "heuristic_mvp"
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EvolutionEnqueueResult:
    scheduled: bool
    reason: str = ""
