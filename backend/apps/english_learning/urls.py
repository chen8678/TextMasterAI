from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.profile_detail, name="english-profile"),
    path("profile/bootstrap/", views.profile_bootstrap, name="english-profile-bootstrap"),
    path("assessment/start/", views.assessment_start, name="english-assessment-start"),
    path(
        "assessment/<uuid:assessment_id>/submit/",
        views.assessment_submit,
        name="english-assessment-submit",
    ),
    path("roadmap/draft/", views.roadmap_draft, name="english-roadmap-draft"),
    path("roadmap/save-draft/", views.roadmap_save_draft, name="english-roadmap-save-draft"),
    path("roadmap/revisions/", views.roadmap_revisions_list, name="english-roadmap-revisions"),
    path("roadmap/finalize/", views.roadmap_finalize, name="english-roadmap-finalize"),
    path("today/", views.today_suggestions, name="english-today"),
    path("curriculum/", views.curriculum_libraries, name="english-curriculum"),
    path("graph/status/", views.graph_status, name="english-graph-status"),
    path("graph/langgraph-poc/", views.graph_langgraph_poc_step, name="english-graph-langgraph-poc"),
    path("graph/langgraph-advance/", views.graph_langgraph_advance_step, name="english-graph-langgraph-advance"),
    path("graph/langgraph-sync/", views.graph_langgraph_sync, name="english-graph-langgraph-sync"),
    path("graph/langgraph-history/", views.graph_langgraph_history, name="english-graph-langgraph-history"),
    path("graph/langgraph-reset/", views.graph_langgraph_reset, name="english-graph-langgraph-reset"),
    path("graph/checkpoint/", views.graph_save_checkpoint, name="english-graph-checkpoint"),
    path("graph/run-node/", views.graph_run_node, name="english-graph-run-node"),
    path("graph/run-chain/", views.graph_run_chain, name="english-graph-run-chain"),
    path("graph/wizard/start/", views.graph_wizard_start, name="english-graph-wizard-start"),
    path("graph/wizard/resume/", views.graph_wizard_resume, name="english-graph-wizard-resume"),
    path(
        "graph/wizard/resume/stream/",
        views.graph_wizard_resume_stream,
        name="english-graph-wizard-resume-stream",
    ),
    path("drill-touch/", views.drill_touch, name="english-drill-touch"),
]
