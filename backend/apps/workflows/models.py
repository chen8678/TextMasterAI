from django.db import models
from django.conf import settings
import uuid


class WorkflowRun(models.Model):
    """工作流执行记录"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_id = models.CharField(max_length=64)
    knowledge_base_id = models.UUIDField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, default='running')  # running | success | failed
    input_params = models.JSONField(default=dict, blank=True)
    output_summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'workflow_runs'
        verbose_name = '工作流执行'
        verbose_name_plural = '工作流执行'


class GeneratedContent(models.Model):
    """工作流生成的内容（大模型驱动的内容生成）"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    knowledge_base = models.ForeignKey(
        'knowledge.KnowledgeBase',
        on_delete=models.CASCADE,
        related_name='generated_contents'
    )
    content_type = models.CharField(max_length=32)  # summary | outline | key_concepts | q_and_a
    content_data = models.JSONField(default=dict)
    ai_model = models.CharField(max_length=64, default='deepseek-chat')
    workflow_run = models.ForeignKey(
        WorkflowRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_contents'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'workflow_generated_contents'
        verbose_name = '生成内容'
        verbose_name_plural = '生成内容'


CONTENT_TYPE_DISPLAY = {
    'summary': '内容总结',
    'outline': '学习大纲',
    'key_concepts': '关键概念',
    'q_and_a': '问答集',
}
