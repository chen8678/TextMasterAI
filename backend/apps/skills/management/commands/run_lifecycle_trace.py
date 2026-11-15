"""跑通 A2 Staging 完整事件链并导出时间序 JSON。

链路：propose → guard pass/fail → staging → reject/apply → soft rollback
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.skills.evolution.evolver import propose_staging_change
from apps.skills.evolution.guard import draft_markdown_allowed
from apps.skills.models import Skill, SkillEvolutionStaging, SkillExecutionLog, SkillLifecycleEvent
from apps.skills.registry import SkillRegistry
from apps.skills.tasks import (
    apply_staging_to_skill,
    emit_lifecycle_event,
    reject_staging,
    soft_rollback_skill,
)

SKILL_ID = "lifecycle_trace_demo"


def _noop(**kwargs):
    return {"ok": True, "skill": SKILL_ID}


class Command(BaseCommand):
    help = "Run illustrative lifecycle trace: propose→guard→stage→reject/apply→rollback."

    def add_arguments(self, parser):
        parser.add_argument(
            "--report-dir",
            type=str,
            default="",
            help="Output directory (default: backend/data/skill_eval).",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        staff, _ = User.objects.get_or_create(
            username="lifecycle_trace_staff",
            defaults={"email": "lifecycle_trace_staff@example.com", "is_staff": True},
        )
        if not staff.is_staff:
            staff.is_staff = True
            staff.save(update_fields=["is_staff"])
        normal, _ = User.objects.get_or_create(
            username="lifecycle_trace_user",
            defaults={"email": "lifecycle_trace_user@example.com"},
        )

        SkillRegistry.register(SKILL_ID, _noop, {"name": "Lifecycle Trace Demo"})
        skill, created = Skill.objects.update_or_create(
            id=SKILL_ID,
            defaults={
                "name": "Lifecycle Trace Demo",
                "description": "A2 illustrative staging chain only",
                "permission_level": "rag",
                "is_active": False,
                "lifecycle_status": "draft",
                "evolution_enabled": True,
                "evolution_auto_apply": False,
                "metadata": {"evolution_domain": "trace_demo", "evolution_merged_markdown": ""},
                "version": 1,
            },
        )
        if created:
            emit_lifecycle_event(skill, "created", user=staff, note="trace demo skill created")

        # wipe prior events/stagings for this skill so report is a single clean chain
        SkillLifecycleEvent.objects.filter(skill=skill).delete()
        SkillEvolutionStaging.objects.filter(skill=skill).delete()
        SkillExecutionLog.objects.filter(skill_id=SKILL_ID).delete()
        emit_lifecycle_event(skill, "created", user=staff, note="trace run reset; skill ready as draft/inactive")

        source_log = SkillExecutionLog.objects.create(
            skill_id=SKILL_ID,
            user=normal,
            input_summary="user asked for citation format help",
            output_summary="failed: missing required keyword",
            status="failed",
            trigger_source="lifecycle_trace",
        )

        # --- branch A: guard fail (no staging) ---
        bad_md = (
            "## Troubleshooting\n"
            "- 建议接入 stable diffusion 与图像生成能力\n"
            "- 允许调用公网 API\n"
        )
        bad_ok, bad_reason = draft_markdown_allowed(bad_md)
        emit_lifecycle_event(
            skill,
            "propose",
            user=staff,
            note="branch=guard_fail; injected adversarial draft",
        )
        if not bad_ok:
            emit_lifecycle_event(
                skill,
                "guard_blocked",
                user=staff,
                note=f"reason={bad_reason}; no_staging_created",
            )

        # --- branch B: guard pass → staging (for apply) ---
        draft = propose_staging_change(
            SKILL_ID,
            user_message="请补充引用格式核对与参考文献字段检查步骤",
            failed_log_summary=f"{source_log.input_summary}\n{source_log.output_summary}",
            skill_description=skill.description,
        )
        emit_lifecycle_event(
            skill,
            "propose",
            user=staff,
            note=f"branch=apply; provenance={draft.provenance}",
        )
        ok_md, md_reason = draft_markdown_allowed(draft.markdown_section)
        if not ok_md:
            raise SystemExit(f"unexpected guard block on clean draft: {md_reason}")

        st_apply = SkillEvolutionStaging.objects.create(
            skill=skill,
            source_log=source_log,
            user=normal,
            status=SkillEvolutionStaging.Status.PENDING,
            draft_markdown=draft.markdown_section,
            provenance=draft.provenance or "template_mvp",
        )
        emit_lifecycle_event(
            skill,
            "staged",
            user=staff,
            note=f"staging_id={st_apply.id}; branch=apply",
        )

        # --- branch C: second pending → reject ---
        st_reject = SkillEvolutionStaging.objects.create(
            skill=skill,
            source_log=source_log,
            user=normal,
            status=SkillEvolutionStaging.Status.PENDING,
            draft_markdown="## Troubleshooting\n- 冗余草案，用于拒绝路径演示\n",
            provenance="trace_reject_branch",
        )
        emit_lifecycle_event(
            skill,
            "staged",
            user=staff,
            note=f"staging_id={st_reject.id}; branch=reject",
        )
        reject_ok = reject_staging(st_reject.id, reviewer=staff, reason="duplicate_low_value")

        # --- apply path ---
        apply_ok = apply_staging_to_skill(st_apply.id, reviewer=staff)
        skill.refresh_from_db()
        st_apply.refresh_from_db()
        after_apply = {
            "is_active": skill.is_active,
            "lifecycle_status": skill.lifecycle_status,
            "version": skill.version,
            "has_merged_markdown": bool((skill.metadata or {}).get("evolution_merged_markdown")),
            "staging_status": st_apply.status,
        }

        # --- soft rollback ---
        rb_ok, rb_reason = soft_rollback_skill(SKILL_ID, reviewer=staff)
        skill.refresh_from_db()
        after_rollback = {
            "ok": rb_ok,
            "reason": rb_reason,
            "is_active": skill.is_active,
            "lifecycle_status": skill.lifecycle_status,
            "version": skill.version,
            "merged_markdown_empty": not bool((skill.metadata or {}).get("evolution_merged_markdown")),
        }

        # export events + staging + recent logs
        events = list(
            SkillLifecycleEvent.objects.filter(skill=skill).order_by("created_at").values(
                "id",
                "event_type",
                "from_version",
                "to_version",
                "note",
                "created_at",
                "user_id",
            )
        )
        for e in events:
            e["id"] = str(e["id"])
            e["created_at"] = e["created_at"].isoformat() if e["created_at"] else None

        stagings = list(
            SkillEvolutionStaging.objects.filter(skill=skill).order_by("created_at").values(
                "id",
                "status",
                "provenance",
                "created_at",
                "reviewed_at",
                "reviewed_by_id",
            )
        )
        for s in stagings:
            s["id"] = str(s["id"])
            s["created_at"] = s["created_at"].isoformat() if s["created_at"] else None
            s["reviewed_at"] = s["reviewed_at"].isoformat() if s["reviewed_at"] else None

        logs = list(
            SkillExecutionLog.objects.filter(skill_id=SKILL_ID).order_by("created_at").values(
                "id",
                "status",
                "input_summary",
                "output_summary",
                "trigger_source",
                "created_at",
            )
        )
        for lg in logs:
            lg["id"] = str(lg["id"])
            lg["created_at"] = lg["created_at"].isoformat() if lg["created_at"] else None

        chain_ok = (
            (not bad_ok)
            and reject_ok
            and apply_ok
            and after_apply["staging_status"] == SkillEvolutionStaging.Status.APPLIED
            and after_apply["is_active"] is False
            and rb_ok
            and after_rollback["lifecycle_status"] == "rolled_back"
        )

        report: Dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "skill_id": SKILL_ID,
            "chain": "propose → guard pass/fail → staging → reject/apply → soft_rollback",
            "chain_ok": chain_ok,
            "guard_fail_branch": {"accepted": bad_ok, "reason": bad_reason},
            "reject_ok": reject_ok,
            "apply_ok": apply_ok,
            "after_apply": after_apply,
            "after_rollback": after_rollback,
            "events": events,
            "stagings": stagings,
            "execution_logs": logs,
            "notes": [
                "soft_rollback restores metadata from _pre_apply_backup; no SkillVersionSnapshot table.",
                "apply merges metadata only; does not activate skill.",
            ],
        }

        report_dir = (options.get("report_dir") or "").strip() or os.path.join(
            os.getcwd(), "data", "skill_eval"
        )
        os.makedirs(report_dir, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = os.path.join(report_dir, f"lifecycle_trace_{stamp}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        # also write a compact markdown table for paper appendix
        md_path = os.path.join(report_dir, f"lifecycle_trace_{stamp}.md")
        lines: List[str] = [
            "# Illustrative lifecycle trace",
            "",
            f"- skill_id: `{SKILL_ID}`",
            f"- chain_ok: **{chain_ok}**",
            f"- generated_at: `{report['started_at']}`",
            "",
            "| # | t (UTC) | event_type | note (truncated) |",
            "|---|---------|------------|----------------|",
        ]
        for i, e in enumerate(events, 1):
            note = (e.get("note") or "").replace("|", "/")[:80]
            lines.append(f"| {i} | {e.get('created_at')} | `{e.get('event_type')}` | {note} |")
        lines.extend(
            [
                "",
                "## Staging rows",
                "",
                "| id | status | provenance | reviewed_at |",
                "|----|--------|------------|-------------|",
            ]
        )
        for s in stagings:
            lines.append(
                f"| `{s['id'][:8]}…` | `{s['status']}` | {s.get('provenance') or ''} | {s.get('reviewed_at') or ''} |"
            )
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        style = self.style.SUCCESS if chain_ok else self.style.ERROR
        self.stdout.write(style(f"Lifecycle trace done: {path} chain_ok={chain_ok}"))
        self.stdout.write(f"Markdown table: {md_path}")
