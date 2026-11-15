from rest_framework import serializers
from .models import KnowledgeBase, Document
import hashlib

class DocumentSerializer(serializers.ModelSerializer):
    scar_compile_error = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            'id',
            'title',
            'content',
            'content_type',
            'file_path',
            'file_size',
            'metadata',
            'scar_domain',
            'compile_status',
            'template_version',
            'scar_compile_error',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'scar_domain',
            'compile_status',
            'template_version',
            'scar_compile_error',
            'created_at',
            'updated_at',
        ]

    def get_scar_compile_error(self, obj):
        md = obj.metadata if isinstance(obj.metadata, dict) else {}
        return md.get('scar_compile_error') or ''

class KnowledgeBaseSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True)
    document_count = serializers.SerializerMethodField()
    
    class Meta:
        model = KnowledgeBase
        fields = ['id', 'title', 'description', 'category', 'settings', 'status', 'document_count', 'documents', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_document_count(self, obj):
        return obj.documents.count()

class KnowledgeBaseListSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()
    is_system_curriculum = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    access_role = serializers.SerializerMethodField()

    class Meta:
        model = KnowledgeBase
        fields = [
            'id', 'title', 'description', 'category', 'status', 'document_count',
            'is_system_curriculum', 'is_owner', 'access_role',
            'created_at', 'updated_at',
        ]

    def get_document_count(self, obj):
        return obj.documents.count()

    def get_is_system_curriculum(self, obj):
        st = obj.settings if isinstance(obj.settings, dict) else {}
        return bool(st.get('is_system_curriculum'))

    def get_is_owner(self, obj):
        user = self.context.get('request')
        if user and hasattr(user, 'user'):
            user = user.user
        if not user or not getattr(user, 'id', None):
            return False
        return obj.owner_id == user.id

    def get_access_role(self, obj):
        if self.get_is_owner(obj):
            return 'owner'
        return 'viewer'

class DocumentCreateSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)
    title = serializers.CharField(required=False, write_only=True)
    content = serializers.CharField(required=False, write_only=True)
    content_type = serializers.CharField(required=False, write_only=True)
    file_path = serializers.CharField(required=False, write_only=True)
    metadata = serializers.JSONField(required=False, write_only=True)
    
    class Meta:
        model = Document
        fields = ['file', 'title', 'content', 'content_type', 'file_path', 'metadata']
    
    def create(self, validated_data):
        knowledge_base_id = self.context['knowledge_base_id']
        file = validated_data.pop('file')
        
        # 处理文件上传
        validated_data['title'] = file.name
        validated_data['file_path'] = file.name
        validated_data['content_type'] = file.content_type or 'text/plain'
        
        # 读取文件内容
        file.seek(0)  # 重置文件指针
        try:
            # 尝试读取文本内容
            content = file.read().decode('utf-8')
            validated_data['content'] = content
        except UnicodeDecodeError:
            # 如果不是文本文件，保存基本信息
            validated_data['content'] = f"文件: {file.name}"
        
        # 获取知识库对象
        from .models import KnowledgeBase
        knowledge_base = KnowledgeBase.objects.get(id=knowledge_base_id)
        validated_data['knowledge_base'] = knowledge_base
        validated_data['content_hash'] = hashlib.sha256((validated_data.get('content') or '').strip().encode('utf-8')).hexdigest()

        duplicated = Document.objects.filter(
            knowledge_base=knowledge_base,
            content_hash=validated_data['content_hash'],
        ).exists()
        if duplicated:
            raise serializers.ValidationError('检测到重复文档：该内容已存在于知识库中')
        
        return super().create(validated_data)
