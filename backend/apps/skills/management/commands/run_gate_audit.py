"""导出 A0 门禁实测表（JSON），供论文 Experiment / 附录使用。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.skills.models import Skill, SkillEvolutionStaging
from apps.skills.registry import SkillRegistry
from apps.skills.tasks import apply_staging_to_skill

User = get_user_model()


def _noop(**kwargs):
    return {"ok": True}


class Command(BaseCommand):
    help = "Run lifecycle/permission gate audit cases and write JSON table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--report-dir",
            type=str,
            default="",
            help="Output directory (default: backend/data/skill_eval).",
        )

    def handle(self, *args, **options):
        SkillRegistry.register("gate_audit_probe", _noop, {"name": "Gate Audit Probe"})

        normal, _ = User.objects.get_or_create(
            username="gate_audit_user",
            defaults={"email": "gate_audit_user@example.com"},
        )
        if not normal.has_usable_password():
            normal.set_password("x")
            normal.save()
        staff, _ = User.objects.get_or_create(
            username="gate_audit_staff",
            defaults={"email": "gate_audit_staff@example.com", "is_staff": True},
        )
        if not staff.is_staff:
            staff.is_staff = True
            staff.save(update_fields=["is_staff"])

        rows: List[Dict[str, Any]] = []

        def ensure_skill(sid, life, active, perm="rag"):
            SkillRegistry.register(sid, _noop, {"name": sid})
            obj, _ = Skill.objects.update_or_create(
                id=sid,
                defaults={
                    "name": sid,
                    "lifecycle_status": life,
                    "is_active": active,
                    "permission_level": perm,
                    "description": "gate audit",
                },
            )
            return obj

        cases = [
            ("draft_normal", "draft", False, "rag", normal, False, "draft/inactive → denied"),
            ("draft_staff", "draft", False, "rag", staff, True, "draft trial by staff → allowed"),
            ("disabled_normal", "disabled", False, "rag", normal, False, "disabled → denied"),
            ("disabled_staff", "disabled", False, "rag", staff, False, "disabled → denied for staff"),
            ("rolled_back_normal", "rolled_back", True, "rag", normal, False, "rolled_back → denied"),
            ("active_normal", "active", True, "rag", normal, True, "active → allowed"),
            ("system_perm_normal", "active", True, "system", normal, False, "system perm → denied"),
            ("inactive_flag_normal", "active", False, "rag", normal, False, "is_active=false → denied"),
        ]

        for sid, life, active, perm, user, expect_ok, note in cases:
            ensure_skill(sid, life, active, perm)
            result, err = SkillRegistry.execute_safe(sid, user=user, question="probe")
            ok = result is not None and err is None
            rows.append(
                {
                    "case_id": sid,
                    "lifecycle_status": life,
                    "is_active": active,
                    "permission_level": perm,
                    "user": "staff" if getattr(user, "is_staff", False) else "normal",
                    "expect_allow": expect_ok,
                    "actual_allow": ok,
                    "error": err,
                    "pass": ok == expect_ok,
                    "note": note,
                }
            )

        # apply does not activate
        skill = ensure_skill("apply_no_activate", "draft", False, "rag")
        st = SkillEvolutionStaging.objects.create(
            skill=skill,
            status=SkillEvolutionStaging.Status.PENDING,
            draft_markdown="## Troubleshooting\n- audit",
            provenance="gate_audit",
        )
        applied = apply_staging_to_skill(st.id, reviewer=staff)
        skill.refresh_from_db()
        st.refresh_from_db()
        apply_pass = (
            applied
            and st.status == SkillEvolutionStaging.Status.APPLIED
            and skill.is_active is False
            and skill.lifecycle_status == "draft"
        )
        rows.append(
            {
                "case_id": "apply_staging_no_activate",
                "lifecycle_status": "draft",
                "is_active": False,
                "permission_level": "rag",
                "user": "staff",
                "expect_allow": True,
                "actual_allow": apply_pass,
                "error": None if apply_pass else "apply activated unexpectedly or failed",
                "pass": apply_pass,
                "note": "staging apply merges metadata only; does not activate",
            }
        )

        passed = sum(1 for r in rows if r["pass"])
        report = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "total": len(rows),
            "passed": passed,
            "pass_rate": passed / max(1, len(rows)),
            "rows": rows,
        }

        report_dir = (options.get("report_dir") or "").strip() or os.path.join(
            os.getcwd(), "data", "skill_eval"
        )
        os.makedirs(report_dir, exist_ok=True)
        path = os.path.join(
            report_dir,
            f"gate_audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"Gate audit done: {path} pass_rate={report['pass_rate']}"))
