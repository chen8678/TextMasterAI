from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand

from apps.skills.evolution.evolver import propose_staging_change
from apps.skills.evolution.guard import draft_markdown_allowed
from apps.skills.models import Skill, SkillExecutionLog, SkillEvolutionStaging
from apps.skills.tasks import apply_staging_to_skill


@dataclass
class TrialCase:
    user_message: str
    failed_log_summary: str
    note: str


class Command(BaseCommand):
    help = "Run minimal skill evolution benchmark (guard + optional staging apply)."

    def add_arguments(self, parser):
        parser.add_argument("--skill-id", type=str, default="rag_answer")
        parser.add_argument("--trials", type=int, default=8)
        parser.add_argument("--apply", action="store_true", help="If set, apply staging to Skill.metadata.")
        parser.add_argument("--report-dir", type=str, default="", help="Output report dir (default: BASE_DIR/data/skill_bench).")

    def handle(self, *args, **options):
        skill_id = options["skill_id"]
        trials = max(1, int(options["trials"]))
        do_apply = bool(options["apply"])
        report_dir_opt = (options.get("report_dir") or "").strip()

        skill = Skill.objects.filter(id=skill_id).first()
        if not skill:
            raise SystemExit(f"Skill not found: {skill_id}")

        now = datetime.now(timezone.utc)
        report_dir = (
            report_dir_opt
            or os.path.join(str(os.getcwd()), "data", "skill_bench")
        )
        os.makedirs(report_dir, exist_ok=True)

        # 轻量固定测试集：不依赖知识库，重点覆盖 propose_staging_change 输出结构与 guard。
        base_cases: List[TrialCase] = [
            TrialCase(
                user_message="请补充引用原文片段，并说明不确定性。",
                failed_log_summary="输出缺少引用；用户反馈证据不足。",
                note="citation_missing",
            ),
            TrialCase(
                user_message="这段格式不对，请按要点列表输出并避免冗余。",
                failed_log_summary="输出结构混乱；用户要求格式修正。",
                note="format_wrong",
            ),
            TrialCase(
                user_message="请把结论前置，并给出三条可执行建议。",
                failed_log_summary="用户指出结论后置且建议不够具体。",
                note="structure_opt",
            ),
            TrialCase(
                user_message="请不要加入多模态/外部调用建议，只做纯文字知识库问答增强。",
                failed_log_summary="候选草案疑似包含超出边界内容。",
                note="boundary_guard",
            ),
        ]

        cases: List[TrialCase] = []
        while len(cases) < trials:
            for c in base_cases:
                if len(cases) >= trials:
                    break
                cases.append(c)

        results: List[Dict[str, Any]] = []
        pass_count = 0
        apply_count = 0
        forbidden_count = 0

        for idx, tc in enumerate(cases[:trials], start=1):
            draft = propose_staging_change(
                skill_id,
                user_message=tc.user_message,
                failed_log_summary=tc.failed_log_summary,
                skill_description=skill.description or "",
            )
            ok, reason = draft_markdown_allowed(draft.markdown_section)
            if ok:
                pass_count += 1
            if reason and "forbidden_marker" in reason:
                forbidden_count += 1

            st: Optional[SkillEvolutionStaging] = None
            applied = False
            if do_apply and ok:
                # 不需要真实 source_log：基准测试强调 pipeline 是否闭环。
                st = SkillEvolutionStaging.objects.create(
                    skill=skill,
                    source_log=None,
                    user=None,
                    status=SkillEvolutionStaging.Status.PENDING,
                    candidate_version=(getattr(skill, "version", 1) or 1) + 1,
                    candidate_hash=skill.build_content_hash(),
                    draft_markdown=draft.markdown_section,
                    provenance="benchmark_minimal",
                )
                applied = apply_staging_to_skill(st.id, reviewer=None)
                apply_count += 1 if applied else 0

            results.append(
                {
                    "idx": idx,
                    "note": tc.note,
                    "provenance": draft.provenance,
                    "guard_ok": ok,
                    "guard_reason": reason,
                    "applied": applied,
                    "staging_id": str(st.id) if st else None,
                    "draft_preview": (draft.markdown_section or "")[:1200],
                }
            )

        report = {
            "skill_id": skill_id,
            "trials": trials,
            "do_apply": do_apply,
            "started_at": now.isoformat(),
            "metrics": {
                "guard_pass_rate": pass_count / trials,
                "apply_pass_rate": (apply_count / max(1, pass_count)) if do_apply else None,
                "forbidden_reject_count": forbidden_count,
            },
            "results": results,
        }

        report_path = os.path.join(
            report_dir,
            f"skill_evolution_benchmark_{skill_id}_{now.strftime('%Y%m%d_%H%M%S')}.json",
        )
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(f"Benchmark done: {report_path}"))

