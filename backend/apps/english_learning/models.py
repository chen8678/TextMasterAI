import uuid

from django.conf import settings
from django.db import models


class EnglishLearningProfile(models.Model):
    """用户英语学习档案：标签、向导状态、默认私库与当前路线文档。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="english_learning_profile",
    )
    default_kb = models.ForeignKey(
        "knowledge.KnowledgeBase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="english_learning_profiles",
    )
    level_tags = models.JSONField(default=list, blank=True)
    session_state = models.JSONField(default=dict, blank=True)
    active_roadmap_document = models.ForeignKey(
        "knowledge.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="english_learning_active_roadmaps",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "english_learning_profiles"
        verbose_name = "英语学习档案"
        verbose_name_plural = "英语学习档案"

    def __str__(self):
        return f"EnglishProfile<{self.user_id}>"


class AssessmentSession(models.Model):
    """一次测评会话（出题、作答、评分）。"""

    class Kind(models.TextChoices):
        PLACEMENT = "placement", "快速定级"
        LEVEL_TEST = "level_test", "级别测评"

    class Status(models.TextChoices):
        DRAFT = "draft", "草稿"
        SUBMITTED = "submitted", "已提交"
        SCORED = "scored", "已评分"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        EnglishLearningProfile,
        on_delete=models.CASCADE,
        related_name="assessments",
    )
    kind = models.CharField(max_length=32, choices=Kind.choices, default=Kind.LEVEL_TEST)
    level_target = models.CharField(max_length=64, blank=True, default="")
    schema_version = models.PositiveSmallIntegerField(default=1)
    items_json = models.JSONField(default=list, blank=True)
    responses_json = models.JSONField(default=list, blank=True)
    scores_json = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "english_learning_assessments"
        ordering = ["-created_at"]
        verbose_name = "英语测评会话"
        verbose_name_plural = "英语测评会话"

    def __str__(self):
        return f"Assessment<{self.id}>"


class RoadmapRevision(models.Model):
    """学习路线修订记录（审计 / 版本）。"""

    profile = models.ForeignKey(
        EnglishLearningProfile,
        on_delete=models.CASCADE,
        related_name="roadmap_revisions",
    )
    version = models.PositiveIntegerField(default=1)
    markdown = models.TextField()
    source_skill_run_id = models.CharField(max_length=128, blank=True, default="")
    document = models.ForeignKey(
        "knowledge.Document",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="english_learning_roadmap_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "english_learning_roadmap_revisions"
        ordering = ["-version", "-created_at"]
        verbose_name = "英语学习路线修订"
        verbose_name_plural = "英语学习路线修订"

    def __str__(self):
        return f"RoadmapRevision<{self.profile_id} v{self.version}>"


class EnglishLearningGraphCheckpoint(models.Model):
    """Phase-C G2：向导 / LangGraph 的 checkpoint 持久化（与 `session_state` 可并行同步）。"""

    profile = models.ForeignKey(
        EnglishLearningProfile,
        on_delete=models.CASCADE,
        related_name="graph_checkpoints",
    )
    thread_id = models.CharField(max_length=128, db_index=True)
    graph_state = models.JSONField(default=dict, blank=True)
    node_cursor = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "english_learning_graph_checkpoints"
        constraints = [
            models.UniqueConstraint(
                fields=("profile", "thread_id"),
                name="uniq_el_graph_checkpoint_profile_thread",
            )
        ]
        verbose_name = "英语学习图 checkpoint"
        verbose_name_plural = "英语学习图 checkpoints"

    def __str__(self):
        return f"ELGraphCheckpoint<{self.profile_id} {self.thread_id}>"
