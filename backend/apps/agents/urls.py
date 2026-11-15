from django.urls import path

from . import views_evolution

urlpatterns = [
    path(
        "evolution/proposals/overview/",
        views_evolution.agent_evolution_proposals_overview,
        name="agent-evolution-proposals-overview",
    ),
    path(
        "<slug:agent_id>/evolution/proposals/",
        views_evolution.agent_evolution_proposals,
        name="agent-evolution-proposals",
    ),
    path(
        "<slug:agent_id>/evolution/proposals/<uuid:proposal_id>/apply/",
        views_evolution.agent_evolution_proposal_apply,
        name="agent-evolution-proposal-apply",
    ),
    path(
        "<slug:agent_id>/evolution/proposals/<uuid:proposal_id>/reject/",
        views_evolution.agent_evolution_proposal_reject,
        name="agent-evolution-proposal-reject",
    ),
]
