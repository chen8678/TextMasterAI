from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand

from apps.skills.evolution.evolver import propose_staging_change
from apps.skills.evolution.guard import draft_markdown_allowed
from apps.skills.models import Skill


@dataclass
class EvalCase:
    case_id: str
    case_type: str  # static | evolution
    user_message: str
    failed_log_summary: str
    must_include_any: List[str]
    must_not_include_any: List[str]
    injected_draft: str = ""
    # expect_block=True → adversarial draft that full_system should reject
    expect_block: Optional[bool] = None


def _judge_case(case: EvalCase, candidate: str, accepted: bool) -> tuple[bool, List[str]]:
    text = (candidate or "").lower()
    reasons: List[str] = []
    if not accepted:
        reasons.append("not_accepted")
    if case.must_include_any:
        if not any(k.lower() in text for k in case.must_include_any):
            reasons.append("missing_required_keyword")
    if case.must_not_include_any:
        if any(k.lower() in text for k in case.must_not_include_any):
            reasons.append("contains_forbidden_keyword")
    return (len(reasons) == 0, reasons)


def _load_cases(taskset_path: str) -> List[EvalCase]:
    with open(taskset_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    cases = []
    for it in raw.get("cases", []):
        expect_block = it.get("expect_block", None)
        if expect_block is not None:
            expect_block = bool(expect_block)
        cases.append(
            EvalCase(
                case_id=str(it.get("id") or ""),
                case_type=str(it.get("type") or "evolution"),
                user_message=str(it.get("user_message") or ""),
                failed_log_summary=str(it.get("failed_log_summary") or ""),
                must_include_any=[str(x) for x in (it.get("must_include_any") or [])],
                must_not_include_any=[str(x) for x in (it.get("must_not_include_any") or [])],
                injected_draft=str(it.get("injected_draft") or ""),
                expect_block=expect_block,
            )
        )
    return cases


class Command(BaseCommand):
    help = "Run minimal evaluation with 3 baselines: no_evolution / no_sandbox / full_system."

    def add_arguments(self, parser):
        parser.add_argument("--skill-id", type=str, default="rag_answer")
        parser.add_argument(
            "--config",
            type=str,
            default="",
            help="Path to experiment config json (default: backend/data/eval/experiment_config.json).",
        )
        parser.add_argument(
            "--taskset",
            type=str,
            default="",
            help="Path to minimal taskset json (default: backend/data/eval/minimal_taskset.json).",
        )
        parser.add_argument(
            "--report-dir",
            type=str,
            default="",
            help="Output report dir (default: backend/data/skill_eval).",
        )

    def handle(self, *args, **options):
        skill_id = (options.get("skill_id") or "rag_answer").strip()
        skill = Skill.objects.filter(id=skill_id).first()
        if not skill:
            raise SystemExit(f"Skill not found: {skill_id}")

        default_config = os.path.join(os.getcwd(), "data", "eval", "experiment_config.json")
        config_path = (options.get("config") or "").strip() or default_config
        if not os.path.exists(config_path):
            raise SystemExit(f"Experiment config not found: {config_path}")
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        freeze = (cfg.get("skill_version_freeze") or {})
        freeze_enabled = bool(freeze.get("enabled", False))
        frozen_skill_id = str(freeze.get("skill_id") or skill_id)
        frozen_version = int(freeze.get("version") or 0)
        if freeze_enabled:
            if frozen_skill_id != skill_id:
                raise SystemExit(
                    f"Freeze skill mismatch: config skill_id={frozen_skill_id} cli skill_id={skill_id}"
                )
            if frozen_version > 0 and int(getattr(skill, "version", 0) or 0) != frozen_version:
                raise SystemExit(
                    f"Skill version mismatch: expected {frozen_version}, current {skill.version}"
                )

        default_taskset = os.path.join(os.getcwd(), "data", "eval", "minimal_taskset.json")
        taskset_path = (options.get("taskset") or "").strip() or default_taskset
        if not os.path.exists(taskset_path):
            raise SystemExit(f"Taskset not found: {taskset_path}")
        cases = _load_cases(taskset_path)
        if not cases:
            raise SystemExit("Taskset has no cases")

        baselines = ["no_evolution", "no_sandbox", "full_system"]
        now = datetime.now(timezone.utc)
        rows: List[Dict[str, Any]] = []

        for base in baselines:
            for c in cases:
                t0 = time.perf_counter()
                used_injected = False
                if base == "no_evolution":
                    candidate = ""
                    accepted = c.case_type == "static"
                    guard_reason = "skipped_no_evolution"
                else:
                    if c.injected_draft.strip():
                        candidate = c.injected_draft
                        used_injected = True
                    else:
                        draft = propose_staging_change(
                            skill_id,
                            user_message=c.user_message,
                            failed_log_summary=c.failed_log_summary,
                            skill_description=skill.description or "",
                        )
                        candidate = draft.markdown_section or ""
                    if base == "no_sandbox":
                        accepted = True
                        guard_reason = "skipped_no_sandbox"
                    else:
                        accepted, guard_reason = draft_markdown_allowed(candidate)
                ok, reasons = _judge_case(c, candidate, accepted)
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                rows.append(
                    {
                        "baseline": base,
                        "case_id": c.case_id,
                        "case_type": c.case_type,
                        "expect_block": c.expect_block,
                        "used_injected_draft": used_injected,
                        "success": ok,
                        "failure_reasons": reasons,
                        "accepted": accepted,
                        "guard_reason": guard_reason,
                        "elapsed_ms": elapsed_ms,
                        "candidate_preview": candidate[:500],
                    }
                )

        def _agg_for(base: str):
            x = [r for r in rows if r["baseline"] == base]
            succ = [r for r in x if r["success"]]
            evo = [r for r in x if r["case_type"] == "evolution"]
            sta = [r for r in x if r["case_type"] == "static"]
            return {
                "total": len(x),
                "success_rate": (len(succ) / max(1, len(x))),
                "success_rate_evolution": (len([r for r in evo if r["success"]]) / max(1, len(evo))),
                "success_rate_static": (len([r for r in sta if r["success"]]) / max(1, len(sta))),
                "avg_latency_ms": (sum(r["elapsed_ms"] for r in x) / max(1, len(x))),
            }

        def _guard_slice(expect_block: bool, base: str):
            x = [
                r
                for r in rows
                if r["baseline"] == base and r.get("expect_block") is expect_block
            ]
            if not x:
                return {"total": 0, "accepted_rate": None, "success_rate": None}
            acc = [r for r in x if r["accepted"]]
            succ = [r for r in x if r["success"]]
            return {
                "total": len(x),
                "accepted_rate": len(acc) / len(x),
                "success_rate": len(succ) / len(x),
            }

        guard_discrimination = {
            "should_block": {
                "no_sandbox": _guard_slice(True, "no_sandbox"),
                "full_system": _guard_slice(True, "full_system"),
            },
            "should_allow": {
                "no_sandbox": _guard_slice(False, "no_sandbox"),
                "full_system": _guard_slice(False, "full_system"),
            },
        }
        # Interception recall on should_block: fraction with accepted=false under full_system
        sb_fs = [
            r for r in rows if r["baseline"] == "full_system" and r.get("expect_block") is True
        ]
        sa_fs = [
            r for r in rows if r["baseline"] == "full_system" and r.get("expect_block") is False
        ]
        if sb_fs:
            guard_discrimination["block_recall_full_system"] = sum(
                1 for r in sb_fs if not r["accepted"]
            ) / len(sb_fs)
        if sa_fs:
            guard_discrimination["false_block_rate_full_system"] = sum(
                1 for r in sa_fs if not r["accepted"]
            ) / len(sa_fs)
            guard_discrimination["allow_accept_rate_full_system"] = sum(
                1 for r in sa_fs if r["accepted"]
            ) / len(sa_fs)

        failures = [r for r in rows if not r["success"]]
        report = {
            "skill_id": skill_id,
            "started_at": now.isoformat(),
            "config_path": config_path,
            "config": cfg,
            "taskset_path": taskset_path,
            "task_count": len(cases),
            "baselines": {b: _agg_for(b) for b in baselines},
            "guard_discrimination": guard_discrimination,
            "rows": rows,
            "failure_archive": failures[:200],
        }

        report_dir = (options.get("report_dir") or "").strip() or os.path.join(os.getcwd(), "data", "skill_eval")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(
            report_dir, f"minimal_evolution_eval_{skill_id}_{now.strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"Minimal eval done: {report_path}"))
        if "block_recall_full_system" in guard_discrimination:
            self.stdout.write(
                f"guard block_recall_full_system="
                f"{guard_discrimination['block_recall_full_system']:.3f} "
                f"false_block_rate_full_system="
                f"{guard_discrimination.get('false_block_rate_full_system', 'n/a')}"
            )
