from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.skills.models import SkillLifecycleEvent
from apps.skills.tasks import soft_rollback_skill


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def skill_lifecycle_events_list(request, skill_id: str):
    """返回指定 Skill 的生命周期事件（staff 用于审计/论文证据链）。"""
    if not getattr(request.user, "is_staff", False):
        return Response({"detail": "需要管理员"}, status=status.HTTP_403_FORBIDDEN)

    try:
        limit = int(request.query_params.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    limit = max(1, min(limit, 200))

    rows = (
        SkillLifecycleEvent.objects.filter(skill_id=skill_id)
        .order_by("-created_at")[:limit]
    )
    items = []
    for r in rows:
        items.append(
            {
                "id": str(r.id),
                "event_type": r.event_type,
                "from_version": r.from_version,
                "to_version": r.to_version,
                "content_hash": r.content_hash,
                "note": (r.note or "")[:2000],
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "user": getattr(getattr(r, "user", None), "username", None) if r.user_id else None,
            }
        )

    return Response({"skill_id": skill_id, "items": items})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def skill_lifecycle_rollback(request, skill_id: str):
    """管理员触发 Skill 软回滚（恢复 _pre_apply_backup）。"""
    if not getattr(request.user, "is_staff", False):
        return Response({"detail": "需要管理员"}, status=status.HTTP_403_FORBIDDEN)

    ok, reason = soft_rollback_skill(skill_id=skill_id, reviewer=request.user)
    if not ok:
        return Response({"ok": False, "reason": reason}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"ok": True, "skill_id": skill_id, "mode": "soft_rollback"})

