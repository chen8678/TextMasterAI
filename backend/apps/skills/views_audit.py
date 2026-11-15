import csv
from datetime import datetime

from django.http import HttpResponse
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.skills.models import SkillExecutionLog


def _parse_ts(value: str):
    if not value:
        return None
    dt = parse_datetime(value)
    if dt is not None:
        return dt
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _build_filtered_queryset(request):
    qs = SkillExecutionLog.objects.select_related("user").order_by("-created_at")

    skill_id = (request.query_params.get("skill_id") or "").strip()
    status_v = (request.query_params.get("status") or "").strip()
    trigger_source = (request.query_params.get("trigger_source") or "").strip()
    user_id = (request.query_params.get("user_id") or "").strip()
    user_email = (request.query_params.get("user_email") or "").strip()
    started_after = _parse_ts((request.query_params.get("started_after") or "").strip())
    started_before = _parse_ts((request.query_params.get("started_before") or "").strip())

    if skill_id:
        qs = qs.filter(skill_id=skill_id)
    if status_v:
        qs = qs.filter(status=status_v)
    if trigger_source:
        qs = qs.filter(trigger_source=trigger_source)
    if user_id:
        qs = qs.filter(user_id=user_id)
    if user_email:
        qs = qs.filter(user__email=user_email)
    if started_after:
        qs = qs.filter(created_at__gte=started_after)
    if started_before:
        qs = qs.filter(created_at__lte=started_before)
    return qs


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def skill_audit_logs_list(request):
    """统一审计视图：按时间/skill/user/status 查询 SkillExecutionLog。"""
    if not getattr(request.user, "is_staff", False):
        return Response({"detail": "需要管理员"}, status=status.HTTP_403_FORBIDDEN)

    qs = _build_filtered_queryset(request)
    try:
        limit = int(request.query_params.get("limit", 100))
    except (TypeError, ValueError):
        limit = 100
    limit = max(1, min(limit, 1000))

    rows = qs[:limit]
    items = []
    for r in rows:
        items.append(
            {
                "id": str(r.id),
                "skill_id": r.skill_id,
                "skill_version": r.skill_version,
                "skill_content_hash": r.skill_content_hash,
                "status": r.status,
                "trigger_source": r.trigger_source,
                "retrieval_refs": r.retrieval_refs,
                "refusal_reason": r.refusal_reason,
                "input_summary": r.input_summary,
                "output_summary": r.output_summary,
                "session_id": str(r.session_id) if r.session_id else None,
                "user_id": str(r.user_id) if r.user_id else None,
                "user_email": getattr(r.user, "email", None) if r.user_id else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
    return Response({"count": len(items), "items": items})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def skill_audit_logs_export(request):
    """统一审计导出：CSV。过滤参数与列表接口一致。"""
    if not getattr(request.user, "is_staff", False):
        return Response({"detail": "需要管理员"}, status=status.HTTP_403_FORBIDDEN)

    qs = _build_filtered_queryset(request)[:5000]
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="skill_audit_logs.csv"'
    writer = csv.writer(resp)
    writer.writerow(
        [
            "id",
            "skill_id",
            "skill_version",
            "skill_content_hash",
            "status",
            "trigger_source",
            "retrieval_refs",
            "refusal_reason",
            "session_id",
            "user_id",
            "user_email",
            "created_at",
        ]
    )
    for r in qs:
        writer.writerow(
            [
                str(r.id),
                r.skill_id,
                r.skill_version,
                r.skill_content_hash,
                r.status,
                r.trigger_source,
                r.retrieval_refs,
                r.refusal_reason,
                str(r.session_id) if r.session_id else "",
                str(r.user_id) if r.user_id else "",
                getattr(r.user, "email", "") if r.user_id else "",
                r.created_at.isoformat() if r.created_at else "",
            ]
        )
    return resp
