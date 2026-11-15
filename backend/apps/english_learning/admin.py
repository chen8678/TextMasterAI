from django.contrib import admin

from .models import (
    AssessmentSession,
    EnglishLearningGraphCheckpoint,
    EnglishLearningProfile,
    RoadmapRevision,
)


@admin.register(EnglishLearningProfile)
class EnglishLearningProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "default_kb_id", "updated_at")
    raw_id_fields = ("user", "default_kb", "active_roadmap_document")


@admin.register(AssessmentSession)
class AssessmentSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "kind", "status", "level_target", "created_at")
    list_filter = ("status", "kind")
    raw_id_fields = ("profile",)


@admin.register(RoadmapRevision)
class RoadmapRevisionAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "version", "document_id", "source_skill_run_id", "created_at")
    raw_id_fields = ("profile", "document")


@admin.register(EnglishLearningGraphCheckpoint)
class EnglishLearningGraphCheckpointAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "thread_id", "node_cursor", "updated_at")
    raw_id_fields = ("profile",)
