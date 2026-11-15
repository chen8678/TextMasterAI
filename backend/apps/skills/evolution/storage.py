"""每 Skill 一份 JSON 进化履历（与文档中 skill_evolutions.json 一致，按 skill_id 分文件）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from django.conf import settings


def _evolution_dir() -> Path:
    raw = (getattr(settings, "SKILL_EVOLUTION_DATA_DIR", "") or "").strip()
    if raw:
        p = Path(raw)
    else:
        p = Path(settings.BASE_DIR) / "data" / "skill_evolutions"
    p.mkdir(parents=True, exist_ok=True)
    return p


def append_record(skill_id: str, record: Dict[str, Any]) -> None:
    path = _evolution_dir() / f"{skill_id}.json"
    data: List[Dict[str, Any]] = []
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except (json.JSONDecodeError, OSError):
            data = []
    rec = dict(record)
    rec.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    data.append(rec)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
