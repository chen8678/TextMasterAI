from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.skills.builtin.skill_creator import execute as skill_creator_execute
from apps.skills.models import Skill, SkillEvolutionStaging
from apps.skills.tasks import apply_staging_to_skill, pro_sandbox_simulation


class Command(BaseCommand):
    help = "Run E2E demo chain: create-skill -> sandbox run -> apply (if sandbox_passed)."

    def add_arguments(self, parser):
        parser.add_argument("--staff-email", type=str, required=True, help="Staff user email for create/apply.")
        parser.add_argument("--pro-email", type=str, required=True, help="PRO user email for sandbox run.")
        parser.add_argument("--create-question", type=str, default="创建技能：合同条款结构化摘要助手")
        parser.add_argument("--sandbox-limit", type=int, default=8)
        parser.add_argument(
            "--report-dir",
            type=str,
            default="",
            help="Output report dir (default: backend/data/sandbox_demo).",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        staff_email = (options.get("staff_email") or "").strip()
        pro_email = (options.get("pro_email") or "").strip()
        question = (options.get("create_question") or "").strip() or "创建技能：合同条款结构化摘要助手"
        sandbox_limit = max(1, int(options.get("sandbox_limit") or 8))

        staff_user = User.objects.filter(email=staff_email, is_active=True).first()
        if not staff_user or not (getattr(staff_user, "is_staff", False) or getattr(staff_user, "is_superuser", False)):
            raise SystemExit(f"Invalid staff user: {staff_email}")
        pro_user = User.objects.filter(email=pro_email, is_active=True, is_pro=True).first()
        if not pro_user:
            raise SystemExit(f"Invalid PRO user: {pro_email}")

        now = datetime.now(timezone.utc)

        # 1) create-skill（治理态）
        create_payload = skill_creator_execute(
            question=question,
            user=staff_user,
            overwrite=False,
            run_after_create=False,
        )
        created_skill_id = create_payload.get("skill_id")
        created_skill = Skill.objects.filter(id=created_skill_id).first() if created_skill_id else None

        # 2) sandbox trial（当前挂载 rag_answer）
        sandbox_payload = pro_sandbox_simulation(user_id=pro_user.id, limit=sandbox_limit)
        staging_id = sandbox_payload.get("staging_id")
        staging = SkillEvolutionStaging.objects.filter(id=staging_id).first() if staging_id else None

        # 3) apply（仅 sandbox_passed）
        apply_ok = False
        apply_reason = ""
        if staging and staging.status == SkillEvolutionStaging.Status.SANDBOX_PASSED:
            apply_ok = apply_staging_to_skill(staging.id, reviewer=staff_user)
            if not apply_ok:
                apply_reason = "apply_failed"
        else:
            apply_reason = "staging_not_passed_or_missing"

        report = {
            "started_at": now.isoformat(),
            "inputs": {
                "staff_email": staff_email,
                "pro_email": pro_email,
                "create_question": question,
                "sandbox_limit": sandbox_limit,
            },
            "create_skill": {
                "payload": create_payload,
                "skill_id": created_skill_id,
                "lifecycle_status": getattr(created_skill, "lifecycle_status", None),
                "is_active": getattr(created_skill, "is_active", None),
                "version": getattr(created_skill, "version", None),
            },
            "sandbox_run": sandbox_payload,
            "staging": {
                "id": str(staging.id) if staging else None,
                "status": getattr(staging, "status", None),
                "skill_id": getattr(staging, "skill_id", None),
                "candidate_version": getattr(staging, "candidate_version", None),
            },
            "apply": {
                "ok": apply_ok,
                "reason": apply_reason,
            },
        }

        report_dir = (options.get("report_dir") or "").strip() or os.path.join(os.getcwd(), "data", "sandbox_demo")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, f"sandbox_e2e_demo_{now.strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(f"E2E demo done: {report_path}"))
