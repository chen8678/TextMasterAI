from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid

class ChatSession(models.Model):
    """聊天会话模型 - 类似NotebookLM的会话概念"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    knowledge_base = models.ForeignKey('knowledge.KnowledgeBase', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)  # 会话标题
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'chat_sessions'
        verbose_name = '聊天会话'
        verbose_name_plural = '聊天会话'
        ordering = ['-last_activity']

    def __str__(self):
        return f"{self.user.username}: {self.title or 'Untitled Session'}"

class QARecord(models.Model):
    """问答记录模型 - 临时存储，定期清理"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)  # 保持向后兼容
    question = models.TextField()
    answer = models.TextField(blank=True)
    knowledge_sources = models.JSONField(default=list, blank=True)
    skills_used = models.JSONField(default=list, blank=True)
    agent_id = models.CharField(max_length=64, blank=True)
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    feedback = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # 添加消息类型和顺序
    message_type = models.CharField(max_length=20, choices=[
        ('user', '用户消息'),
        ('assistant', '助手回复'),
        ('system', '系统消息')
    ], default='user')
    message_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'qa_records'
        verbose_name = '问答记录'
        verbose_name_plural = '问答记录'
        ordering = ['session', 'message_order']

    def __str__(self):
        return f"{self.session}: {self.question[:50]}..."

    @classmethod
    def cleanup_old_records(cls, days=7):
        """清理超过指定天数的记录"""
        cutoff_date = timezone.now() - timedelta(days=days)
        old_records = cls.objects.filter(created_at__lt=cutoff_date)
        count = old_records.count()
        old_records.delete()
        return count

    @classmethod
    def cleanup_inactive_sessions(cls, days=30):
        """清理不活跃的会话"""
        cutoff_date = timezone.now() - timedelta(days=days)
        inactive_sessions = ChatSession.objects.filter(
            last_activity__lt=cutoff_date,
            is_active=True
        )
        count = inactive_sessions.count()
        inactive_sessions.update(is_active=False)
        return count


class UsageDaily(models.Model):
    """用户日问答用量（P0-08 成本熔断；跨 worker 用 DB + F() 自增）。"""

    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="usage_daily",
    )
    date = models.DateField(db_index=True)
    ask_count = models.PositiveIntegerField(default=0)
    token_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "chat_usage_daily"
        verbose_name = "日问答用量"
        verbose_name_plural = "日问答用量"
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="uniq_usage_daily_user_date"),
        ]
        indexes = [
            models.Index(fields=["date"], name="chat_usage_daily_date_idx"),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.date} asks={self.ask_count} tokens={self.token_count}"


class StudioDraft(models.Model):
    """PRO 工作室草稿（服务端持久化，类 Cursor 文件）。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="studio_drafts")
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(blank=True)
    mode = models.CharField(
        max_length=20,
        choices=[("novel", "小说"), ("paper", "论文"), ("contract", "合同")],
        default="novel",
    )
    path = models.CharField(max_length=255, blank=True, default="")
    version = models.PositiveIntegerField(default=1)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "studio_drafts"
        verbose_name = "工作室草稿"
        verbose_name_plural = "工作室草稿"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.user_id}:{self.title or self.id}"


class StudioDraftRevision(models.Model):
    """工作室草稿历史快照（每次覆盖保存前写入一条，供回滚）。P3-T01"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(
        StudioDraft,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    revision_index = models.PositiveIntegerField(
        verbose_name="版本号",
        help_text="对应保存前草稿的 version，与本条快照内容一致",
    )
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField(blank=True)
    mode = models.CharField(
        max_length=20,
        choices=[("novel", "小说"), ("paper", "论文"), ("contract", "合同")],
        default="novel",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "studio_draft_revisions"
        verbose_name = "工作室草稿历史版本"
        verbose_name_plural = "工作室草稿历史版本"
        ordering = ["-revision_index", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["draft", "revision_index"],
                name="uniq_studio_draft_revision_per_version",
            ),
        ]
        indexes = [
            models.Index(fields=["draft", "-revision_index"], name="studio_draft_rev_draft_idx"),
        ]

    def __str__(self):
        return f"{self.draft_id}:v{self.revision_index}"
