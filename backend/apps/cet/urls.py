from django.urls import path

from . import views

urlpatterns = [
    path("questions/", views.question_list, name="cet-question-list"),
    path("practice/", views.generate_practice, name="cet-generate-practice"),
    path("practice/submit/", views.submit_practice, name="cet-submit-practice"),
    path("weak-points/", views.weak_points, name="cet-weak-points"),
    path(
        "vocabulary/notebooks/",
        views.create_vocabulary_notebook,
        name="cet-create-vocabulary-notebook",
    ),
    path(
        "vocabulary/notebooks/import-core/",
        views.import_core_vocabulary_notebook,
        name="cet-import-core-vocabulary",
    ),
    path(
        "vocabulary/notebooks/list/",
        views.vocabulary_notebook_list,
        name="cet-vocabulary-notebook-list",
    ),
    path(
        "vocabulary/notebooks/<int:notebook_id>/review-plan/",
        views.vocabulary_review_plan,
        name="cet-vocabulary-review-plan",
    ),
    path(
        "vocabulary/review/",
        views.record_vocabulary_review,
        name="cet-vocabulary-review",
    ),
    path("analysis/ability-radar/", views.ability_radar, name="cet-ability-radar"),
    path(
        "analysis/learner-snapshot/",
        views.learner_snapshot,
        name="cet-learner-snapshot",
    ),
    path("tutor/ask/", views.tutor_ask, name="cet-tutor-ask"),
    path("writing/grade/", views.grade_writing, name="cet-writing-grade"),
    path(
        "listening/process/",
        views.process_listening_transcript,
        name="cet-listening-process",
    ),
    path("exam/create-mock/", views.create_mock_exam, name="cet-create-mock-exam"),
    path(
        "exam/<int:mock_exam_id>/submit/",
        views.submit_mock_exam,
        name="cet-submit-mock-exam",
    ),
]

