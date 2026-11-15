from django.db import models
from django.conf import settings
import uuid


class Skill(models.Model):
    """Skill 元数据模型"""
    id = models.SlugField(primary_key=True, max_length=64)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    input_schema = models.JSONField(default=dict, blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    permission_level = models.CharField(max_length=32, default='rag')
    execute_module = models.CharField(max_length=255, blank=True)
    execute_func = models.CharField(max_length=64, default='execute')
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    evolution_enabled = models.BooleanField(default=False, db_index=True, verbose_name='启用自进化')
    evolution_auto_apply = models.BooleanField(default=False, verbose_name='自动合并进化（高风险，默认关）')
    # 以下字段见 migrations 0004_skill_lifecycle_foundation（须与 DB 一致，否则 INSERT 会漏列导致 NOT NULL 失败）
    content_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
    lifecycle_status = models.CharField(
        max_length=16,
        choices=[
            ('draft', '草案'),
            ('active', '已生效'),
            ('disabled', '已禁用'),
            ('rolled_back', '已回滚'),
        ],
        default='active',
        db_index=True,
    )
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'skills'
        verbose_name = '技能'
        verbose_name_plural = '技能'

    def __str__(self):
        return f"{self.id}: {self.name}"


class SkillExecutionLog(models.Model):
    """Skill 执行日志（可选）"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    skill_id = models.CharField(max_length=64)
    session_id = models.UUIDField(null=True, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='skill_execution_logs',
    )
    input_summary = models.TextField(blank=True)
    output_summary = models.TextField(blank=True)
    status = models.CharField(max_length=20)  # success | failed | denied
    created_at = models.DateTimeField(auto_now_add=True)
    # 0004_skill_lifecycle_foundation：与数据库列一致，避免 INSERT 缺列导致 NOT NULL 失败
    refusal_reason = models.CharField(max_length=128, blank=True, default='')
    retrieval_refs = models.JSONField(default=list, blank=True)
    skill_content_hash = models.CharField(max_length=64, blank=True, default='')
    skill_version = models.PositiveIntegerField(default=1)
    trigger_source = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        db_table = 'skill_execution_logs'
        verbose_name = '技能执行日志'
        verbose_name_plural = '技能执行日志'


class SkillEvolutionStaging(models.Model):
    """自进化草案（Supervised：pending → 人工批准后合并至 Skill.metadata）"""

    class Status(models.TextChoices):
        PENDING = 'pending', '待审核'
        APPROVED = 'approved', '已批准'
        REJECTED = 'rejected', '已拒绝'
        APPLIED = 'applied', '已合并'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='evolution_stagings')
    source_log = models.ForeignKey(
        SkillExecutionLog,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='evolution_stagings',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='skill_evolution_stagings_reviewed',
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    draft_markdown = models.TextField()
    provenance = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'skill_evolution_staging'
        verbose_name = 'Skill 进化草案'
        verbose_name_plural = 'Skill 进化草案'
        ordering = ['-created_at']


class SkillLifecycleEvent(models.Model):
    """Skill 生命周期审计事件（A2：可导出时间序证据链）。"""

    class EventType(models.TextChoices):
        CREATED = "created", "创建"
        PROPOSE = "propose", "生成草案"
        GUARD_BLOCKED = "guard_blocked", "守卫拦截"
        STAGED = "staged", "进入草案"
        REJECTED = "rejected", "拒绝草案"
        APPLIED = "applied", "合并草案"
        ROLLED_BACK = "rolled_back", "回滚"
        DISABLED = "disabled", "禁用"
        TRIAL_SUCCEEDED = "trial_succeeded", "试跑成功"
        TRIAL_FAILED = "trial_failed", "试跑失败"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="lifecycle_events")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    from_version = models.PositiveIntegerField(default=0)
    to_version = models.PositiveIntegerField(default=0)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "skill_lifecycle_events"
        verbose_name = "Skill 生命周期事件"
        verbose_name_plural = "Skill 生命周期事件"
        ordering = ["-created_at"]
