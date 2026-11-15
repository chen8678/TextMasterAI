from rest_framework import serializers

from .models import AssessmentSession, EnglishLearningProfile, RoadmapRevision


class EnglishLearningProfileSerializer(serializers.ModelSerializer):
    session_state_version = serializers.SerializerMethodField()

    class Meta:
        model = EnglishLearningProfile
        fields = (
            "id",
            "default_kb_id",
            "level_tags",
            "session_state",
            "session_state_version",
            "active_roadmap_document_id",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "default_kb_id",
            "active_roadmap_document_id",
            "created_at",
            "updated_at",
            "session_state_version",
        )

    def get_session_state_version(self, obj):
        return int((obj.session_state or {}).get("_merge_version") or 0)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        st = data.get("session_state")
        if isinstance(st, dict) and "_merge_version" in st:
            data["session_state"] = {k: v for k, v in st.items() if k != "_merge_version"}
        return data


class AssessmentSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssessmentSession
        fields = (
            "id",
            "kind",
            "level_target",
            "schema_version",
            "items_json",
            "responses_json",
            "scores_json",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("items_json", "scores_json", "status", "created_at", "updated_at")


class RoadmapRevisionSerializer(serializers.ModelSerializer):
    """定稿修订；`knowledge_base_id` 来自入库 Document，便于前端深链到正确知识库。"""

    document_id = serializers.SerializerMethodField()
    knowledge_base_id = serializers.SerializerMethodField()

    class Meta:
        model = RoadmapRevision
        fields = (
            "id",
            "version",
            "markdown",
            "document_id",
            "knowledge_base_id",
            "source_skill_run_id",
            "created_at",
        )
        read_only_fields = fields

    def get_document_id(self, obj):
        pk = getattr(obj, "document_id", None)
        return str(pk) if pk is not None else None

    def get_knowledge_base_id(self, obj):
        doc = getattr(obj, "document", None)
        if doc is None:
            return None
        kb_id = getattr(doc, "knowledge_base_id", None)
        return str(kb_id) if kb_id is not None else None
