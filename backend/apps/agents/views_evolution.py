"""Agent 进化提案 API（管理员）。"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.agents.models import Agent, AgentEvolutionProposal


def _staff(request):
    return getattr(request.user, "is_staff", False) or getattr(request.user, "is_superuser", False)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agent_evolution_proposals(request, agent_id: str):
    if not _staff(request):
        return Response({"detail": "需要管理员权限"}, status=status.HTTP_403_FORBIDDEN)
    rows = AgentEvolutionProposal.objects.filter(agent_id=agent_id).order_by("-created_at")[:80]
    data = [
        {
            "id": str(r.id),
            "status": r.status,
            "payload": r.payload,
            "provenance": r.provenance,
            "session_id": str(r.session_id) if r.session_id else None,
            "created_by": getattr(getattr(r, "created_by", None), "username", None),
            "reviewed_by": getattr(getattr(r, "reviewed_by", None), "username", None),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        }
        for r in rows
    ]
    return Response({"agent_id": agent_id, "items": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def agent_evolution_proposals_overview(request):
    """P3-T11：审批总览（Agent 提案）。"""
    if not _staff(request):
        return Response({"detail": "需要管理员权限"}, status=status.HTTP_403_FORBIDDEN)
    try:
        limit = int(request.query_params.get("limit", 120))
    except (TypeError, ValueError):
        limit = 120
    limit = max(20, min(limit, 500))
    status_filter = str(request.query_params.get("status", "")).strip()
    qs = AgentEvolutionProposal.objects.select_related("agent", "created_by", "reviewed_by").order_by("-created_at")
    if status_filter:
        qs = qs.filter(status=status_filter)
    rows = qs[:limit]
    items = []
    for r in rows:
        items.append(
            {
                "id": str(r.id),
                "agent_id": str(r.agent_id),
                "agent_name": str(getattr(r.agent, "name", r.agent_id)),
                "status": r.status,
                "provenance": r.provenance,
                "created_by": getattr(getattr(r, "created_by", None), "username", None),
                "reviewed_by": getattr(getattr(r, "reviewed_by", None), "username", None),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
            }
        )
    return Response({"items": items})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def agent_evolution_proposal_apply(request, agent_id: str, proposal_id: str):
    if not _staff(request):
        return Response({"detail": "需要管理员权限"}, status=status.HTTP_403_FORBIDDEN)
    prop = AgentEvolutionProposal.objects.filter(id=proposal_id, agent_id=agent_id).first()
    if not prop:
        return Response({"error": "提案不存在"}, status=status.HTTP_404_NOT_FOUND)
    try:
        agent = Agent.objects.get(id=agent_id)
    except Agent.DoesNotExist:
        return Response({"error": "Agent 不存在"}, status=status.HTTP_404_NOT_FOUND)
    if getattr(agent, "evolution_governance", "") == "gated" and not getattr(
        request.user, "is_superuser", False
    ):
        return Response({"detail": "gated 模式仅超级管理员可应用提案"}, status=status.HTTP_403_FORBIDDEN)
    from apps.agents.tasks import apply_agent_proposal

    ok = apply_agent_proposal(prop.id, request.user, force=False)
    if not ok:
        return Response({"error": "无法应用"}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def agent_evolution_proposal_reject(request, agent_id: str, proposal_id: str):
    if not _staff(request):
        return Response({"detail": "需要管理员权限"}, status=status.HTTP_403_FORBIDDEN)
    from django.utils import timezone

    prop = AgentEvolutionProposal.objects.filter(id=proposal_id, agent_id=agent_id).first()
    if not prop:
        return Response({"error": "提案不存在"}, status=status.HTTP_404_NOT_FOUND)
    if prop.status != AgentEvolutionProposal.Status.PENDING:
        return Response({"error": "状态不可拒绝"}, status=status.HTTP_400_BAD_REQUEST)
    prop.status = AgentEvolutionProposal.Status.REJECTED
    prop.reviewed_by = request.user
    prop.reviewed_at = timezone.now()
    prop.save(update_fields=["status", "reviewed_by", "reviewed_at"])
    return Response({"ok": True})
