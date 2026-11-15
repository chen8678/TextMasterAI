from django.db import models
from django.conf import settings
import uuid


class Agent(models.Model):
    """Agent 配置模型"""
    id = models.SlugField(primary_key=True, max_length=64)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    system_prompt = models.TextField(blank=True)
    skills = models.JSONField(default=list)  # ["rag_answer", "cite_snippets"]
    default_model = models.CharField(max_length=64, default='deepseek-chat')
    workflow_id = models.CharField(max_length=64, blank=True)
    policies = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    evolution_enabled = models.BooleanField(default=False, db_index=True, verbose_name='启用 Agent 配置自进化分析')
    evolution_governance = models.CharField(
        max_length=16,
        default='supervised',
        choices=[
            ('supervised', '人工审批'),
            ('auto', '低风险自动'),
            ('gated', '仅超管'),
        ],
        verbose_name='进化治理模式',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'agents'
        verbose_name = '智能体'
        verbose_name_plural = '智能体'

    def __str__(self):
        return f"{self.id}: {self.name}"


class AgentEvolutionProposal(models.Model):
    """Agent 配置进化提案（由会话摘要 + 启发/LLM 生成，默认需人工合并）"""

    class Status(models.TextChoices):
        PENDING = 'pending', '待处理'
        APPLIED = 'applied', '已应用'
        REJECTED = 'rejected', '已拒绝'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name='evolution_proposals')
    session_id = models.UUIDField(null=True, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    provenance = models.CharField(max_length=64, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='agent_evolution_proposals_created',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='agent_evolution_proposals_reviewed',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'agent_evolution_proposals'
        verbose_name = 'Agent 进化提案'
        verbose_name_plural = 'Agent 进化提案'
        ordering = ['-created_at']
