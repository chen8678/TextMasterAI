"""Skill 自进化草案查询与人工批准（MVP）。"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.skills.models import Skill, SkillEvolutionStaging
from apps.skills.tasks import apply_staging_to_skill
from apps.skills.tasks import pro_sandbox_simulation, run_pro_sandbox_daily
from apps.system.throttles import SandboxTriggerRateThrottle


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def skill_meta_list(request):
    """下拉用：Skill 简要列表（管理员）。"""
    if not getattr(request.user, "is_staff", False):
        return Response({"detail": "需要管理员"}, status=status.HTTP_403_FORBIDDEN)
    rows = (
        Skill.objects.filter(is_active=True)
        .order_by("id")
        .values("id", "name", "permission_level", "evolution_enabled", "metadata")[:500]
    )
    items = []
    for r in rows:
        meta = r.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        items.append(
            {
                "id": r.get("id"),
                "name": r.get("name"),
                "permission_level": r.get("permission_level"),
                "evolution_enabled": bool(r.get("evolution_enabled")),
                "evolution_domain": str(meta.get("evolution_domain") or "unknown"),
            }
        )
    return Response({"items": items})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def skill_evolution_history(request):
    """P3-T10：用于前端时间线的进化历史聚合（管理员）。"""
    if not getattr(request.user, "is_staff", False):
        return Response({"detail": "需要管理员"}, status=status.HTTP_403_FORBIDDEN)

    domain = str(request.query_params.get("domain", "")).strip().lower()
    skill_id = str(request.query_params.get("skill_id", "")).strip()
    try:
        limit = int(request.query_params.get("limit", 300))
    except (TypeError, ValueError):
        limit = 300
    limit = max(20, min(limit, 1000))

    qs = (
        SkillEvolutionStaging.objects.select_related("skill")
        .filter(skill__is_active=True)
        .order_by("-created_at")
    )
    if skill_id:
        qs = qs.filter(skill_id=skill_id)
    if domain:
        # metadata 为 JSONField，Django 支持 __key 访问
        qs = qs.filter(skill__metadata__evolution_domain=domain)

    rows = qs[:limit]
    events = []
    domains = set()
    for r in rows:
        meta = (r.skill.metadata or {}) if r.skill_id else {}
        if not isinstance(meta, dict):
            meta = {}
        evo_domain = str(meta.get("evolution_domain") or "unknown")
        domains.add(evo_domain)
        events.append(
            {
                "id": str(r.id),
                "skill_id": str(r.skill_id),
                "skill_name": str(getattr(r.skill, "name", r.skill_id)),
                "domain": evo_domain,
                "status": r.status,
                "provenance": r.provenance or "",
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            }
        )
    return Response(
        {
            "items": events,
            "summary": {
                "total": len(events),
                "domains": sorted(list(domains)),
            },
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def skill_evolution_staging_list(request, skill_id: str):
    if not getattr(request.user, "is_staff", False):
        return Response({"detail": "需要管理员"}, status=status.HTTP_403_FORBIDDEN)
    rows = SkillEvolutionStaging.objects.filter(skill_id=skill_id).order_by("-created_at")[:50]
    data = [
        {
            "id": str(r.id),
            "status": r.status,
            "draft_markdown": r.draft_markdown[:8000],
            "provenance": r.provenance,
            "created_by": getattr(getattr(r, "user", None), "username", None),
            "reviewed_by": getattr(getattr(r, "reviewed_by", None), "username", None),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        }
        for r in rows
    ]
    return Response({"skill_id": skill_id, "items": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def skill_evolution_staging_overview(request):
    """P3-T11：审批总览（Skill 草案）。"""
    if not getattr(request.user, "is_staff", False):
        return Response({"detail": "需要管理员"}, status=status.HTTP_403_FORBIDDEN)
    try:
        limit = int(request.query_params.get("limit", 120))
    except (TypeError, ValueError):
        limit = 120
    limit = max(20, min(limit, 500))
    status_filter = str(request.query_params.get("status", "")).strip()

    qs = SkillEvolutionStaging.objects.select_related("skill", "user", "reviewed_by").order_by("-created_at")
    if status_filter:
        qs = qs.filter(status=status_filter)
    rows = qs[:limit]
    items = []
    for r in rows:
        items.append(
            {
                "id": str(r.id),
                "skill_id": str(r.skill_id),
                "skill_name": str(getattr(r.skill, "name", r.skill_id)),
                "status": r.status,
                "provenance": r.provenance,
                "created_by": getattr(getattr(r, "user", None), "username", None),
                "reviewed_by": getattr(getattr(r, "reviewed_by", None), "username", None),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            }
        )
    return Response({"items": items})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def skill_evolution_staging_apply(request, skill_id: str, staging_id: str):
    if not getattr(request.user, "is_staff", False):
        return Response({"detail": "需要管理员"}, status=status.HTTP_403_FORBIDDEN)
    st = SkillEvolutionStaging.objects.filter(id=staging_id, skill_id=skill_id).first()
    if not st:
        return Response({"error": "草案不存在"}, status=status.HTTP_404_NOT_FOUND)
    ok = apply_staging_to_skill(st.id, reviewer=request.user)
    if not ok:
        return Response({"error": "无法合并（状态非 pending 或记录无效）"}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"ok": True, "staging_id": staging_id})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([SandboxTriggerRateThrottle])
def pro_sandbox_run(request):
    """手动触发一次 PRO 沙盒模拟（P2-T23 MVP 入口）。"""
    from django.conf import settings as dj_settings

    if not getattr(dj_settings, "ENABLE_PRO_SANDBOX", False):
        return Response({"detail": "沙盒功能未启用"}, status=status.HTTP_403_FORBIDDEN)
    if not getattr(request.user, "is_pro", False):
        return Response({"detail": "仅 PRO 用户可用"}, status=status.HTTP_403_FORBIDDEN)
    try:
        limit = int(request.data.get("limit", 12))
    except (TypeError, ValueError):
        limit = 12

    # 开发期默认同步执行（CELERY_TASK_ALWAYS_EAGER=true）；生产可走异步 worker。
    r = pro_sandbox_simulation.delay(request.user.id, limit=limit)
    payload = r.get(timeout=60) if hasattr(r, "get") else {"ok": True}
    return Response(payload)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([SandboxTriggerRateThrottle])
def pro_sandbox_run_daily(request):
    """管理员手动触发一次全量 PRO 沙盒调度（P2-T24）。"""
    from django.conf import settings as dj_settings

    if not getattr(dj_settings, "ENABLE_PRO_SANDBOX", False):
        return Response({"detail": "沙盒功能未启用"}, status=status.HTTP_403_FORBIDDEN)
    if not getattr(request.user, "is_staff", False):
        return Response({"detail": "需要管理员"}, status=status.HTTP_403_FORBIDDEN)
    try:
        limit = int(request.data.get("limit_per_user", 8))
    except (TypeError, ValueError):
        limit = 8
    try:
        max_users = int(request.data.get("max_users", 20))
    except (TypeError, ValueError):
        max_users = 20
    r = run_pro_sandbox_daily.delay(limit_per_user=limit, max_users=max_users)
    payload = r.get(timeout=180) if hasattr(r, "get") else {"ok": True}
    return Response(payload)
