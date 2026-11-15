from django.urls import path

from . import views_evolution

urlpatterns = [
    path(
        "meta/list/",
        views_evolution.skill_meta_list,
        name="skill-meta-list",
    ),
    path(
        "evolution/history/",
        views_evolution.skill_evolution_history,
        name="skill-evolution-history",
    ),
    path(
        "evolution/staging/overview/",
        views_evolution.skill_evolution_staging_overview,
        name="skill-evolution-staging-overview",
    ),
    path(
        "<slug:skill_id>/evolution/staging/",
        views_evolution.skill_evolution_staging_list,
        name="skill-evolution-staging-list",
    ),
    path(
        "<slug:skill_id>/evolution/staging/<uuid:staging_id>/apply/",
        views_evolution.skill_evolution_staging_apply,
        name="skill-evolution-staging-apply",
    ),
    path(
        "simulation/pro-sandbox/run/",
        views_evolution.pro_sandbox_run,
        name="pro-sandbox-run",
    ),
    path(
        "simulation/pro-sandbox/run-daily/",
        views_evolution.pro_sandbox_run_daily,
        name="pro-sandbox-run-daily",
    ),
]
