from django.contrib import admin

from .models import Agent, AgentEvolutionProposal


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active", "evolution_enabled", "evolution_governance", "default_model")
    list_filter = ("is_active", "evolution_enabled")
    search_fields = ("id", "name", "description")
    fieldsets = (
        ("基本", {"fields": ("id", "name", "description", "is_active")}),
        ("角色设定", {"fields": ("system_prompt",), "description": "影响所有问答路径的系统前缀；问候与闲聊也会遵守。"}),
        ("能力与模型", {"fields": ("skills", "default_model", "workflow_id", "policies")}),
        ("自进化", {"fields": ("evolution_enabled", "evolution_governance")}),
    )


@admin.register(AgentEvolutionProposal)
class AgentEvolutionProposalAdmin(admin.ModelAdmin):
    list_display = ("id", "agent", "status", "provenance", "created_at", "reviewed_at")
    list_filter = ("status",)
    raw_id_fields = ("agent", "created_by", "reviewed_by")
    readonly_fields = ("created_at",)
