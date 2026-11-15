from django.db import models
from django.conf import settings
from pgvector.django import VectorField
import uuid


class DomainTemplate(models.Model):
    class Lifecycle(models.TextChoices):
        DRAFT = "draft", "草案"
        ACTIVE = "active", "生效"
        RETIRED = "retired", "退役"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain_key = models.CharField(max_length=64, db_index=True)
    version = models.PositiveIntegerField(default=1)
    lifecycle = models.CharField(
        max_length=16, choices=Lifecycle.choices, default=Lifecycle.DRAFT, db_index=True
    )
    # 结构规格、索引白名单、别名、单位规则等（机器可读）
    spec_json = models.JSONField(default=dict, blank=True)
    index_whitelist = models.JSONField(default=list, blank=True)
    alias_map = models.JSONField(default=dict, blank=True)
    unit_rules = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scar_domain_templates"
        unique_together = ("domain_key", "version")
        verbose_name = "SCAR 领域模板"
        verbose_name_plural = "SCAR 领域模板"

    def __str__(self):
        return f"{self.domain_key}@v{self.version}({self.lifecycle})"


class StructureUnit(models.Model):
    class Provenance(models.TextChoices):
        PARSER = "parser", "确定性解析"
        RULE = "rule", "规则"
        LLM_SUGGEST = "llm_suggest", "LLM 建议（非金标）"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        "knowledge.Document",
        on_delete=models.CASCADE,
        related_name="scar_units",
    )
    unit_id = models.CharField(max_length=255, db_index=True)
    path = models.CharField(max_length=512, db_index=True)
    unit_type = models.CharField(max_length=64, default="field")
    value_norm = models.TextField()
    unit = models.CharField(max_length=32, blank=True, default="")
    source_ref = models.CharField(max_length=512)
    provenance = models.CharField(
        max_length=32, choices=Provenance.choices, default=Provenance.PARSER
    )
    domain = models.CharField(max_length=64, default="construction", db_index=True)
    template_version = models.PositiveIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scar_structure_units"
        unique_together = ("document", "unit_id")
        verbose_name = "SCAR 结构单元"
        verbose_name_plural = "SCAR 结构单元"
        indexes = [
            models.Index(fields=["document", "path"]),
            models.Index(fields=["domain", "path"]),
        ]

    def __str__(self):
        return f"{self.path}={self.value_norm}"


class IndexEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        "knowledge.Document",
        on_delete=models.CASCADE,
        related_name="scar_index_entries",
    )
    unit = models.ForeignKey(
        StructureUnit,
        on_delete=models.CASCADE,
        related_name="index_entries",
    )
    embed_text = models.TextField()
    vector_embedding = VectorField(dimensions=1024, null=True, blank=True)
    domain = models.CharField(max_length=64, default="construction", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "scar_index_entries"
        verbose_name = "SCAR 定向索引项"
        verbose_name_plural = "SCAR 定向索引项"

    def __str__(self):
        return self.embed_text[:80]
