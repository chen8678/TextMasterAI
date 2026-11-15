from rest_framework import serializers
from .models import QARecord, ChatSession, StudioDraft, StudioDraftRevision

class QARecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = QARecord
        fields = ['id', 'question', 'answer', 'knowledge_sources', 'confidence_score', 'feedback', 'created_at', 'message_type', 'message_order']
        read_only_fields = ['id', 'created_at']

class ChatSessionSerializer(serializers.ModelSerializer):
    messages = QARecordSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'knowledge_base', 'created_at', 'last_activity', 'is_active', 'messages', 'message_count']
        read_only_fields = ['id', 'created_at', 'last_activity']
    
    def get_message_count(self, obj):
        return obj.messages.count()

class ChatSessionListSerializer(serializers.ModelSerializer):
    """简化的会话列表序列化器"""
    message_count = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    
    class Meta:
        model = ChatSession
        fields = ['id', 'title', 'created_at', 'last_activity', 'is_active', 'message_count', 'last_message']
        read_only_fields = ['id', 'created_at', 'last_activity']
    
    def get_message_count(self, obj):
        return obj.messages.count()
    
    def get_last_message(self, obj):
        last_msg = obj.messages.order_by('-created_at').first()
        if last_msg:
            return {
                'question': last_msg.question[:100] + '...' if len(last_msg.question) > 100 else last_msg.question,
                'created_at': last_msg.created_at
            }
        return None


class StudioDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioDraft
        fields = [
            "id",
            "title",
            "content",
            "mode",
            "path",
            "version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "version", "created_at", "updated_at"]


class StudioDraftRevisionListSerializer(serializers.ModelSerializer):
    """列表：带正文预览，避免移动端一次拉过大文本。"""

    content_preview = serializers.SerializerMethodField()

    class Meta:
        model = StudioDraftRevision
        fields = ["revision_index", "title", "mode", "created_at", "content_preview"]

    def get_content_preview(self, obj):
        text = (obj.content or "").strip()
        return text[:320] + ("…" if len(text) > 320 else "")


class StudioDraftRevisionDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioDraftRevision
        fields = ["revision_index", "title", "content", "mode", "created_at"]
