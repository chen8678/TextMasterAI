from django.contrib import admin

from .models import Skill, SkillEvolutionStaging, SkillExecutionLog


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "evolution_domain_display",
        "use_case_display",
        "is_active",
        "evolution_enabled",
        "evolution_auto_apply",
    )
    list_filter = ("is_active", "evolution_enabled")
    search_fields = ("id", "name")

    @admin.display(description="evolution_domain")
    def evolution_domain_display(self, obj):
        m = obj.metadata or {}
        return (m.get("evolution_domain") or "—") if isinstance(m, dict) else "—"

    @admin.display(description="适用场景")
    def use_case_display(self, obj):
        m = obj.metadata or {}
        return (m.get("use_case") or "—")[:80] if isinstance(m, dict) else "—"


@admin.register(SkillExecutionLog)
class SkillExecutionLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "skill_id",
        "status",
        "trigger_source",
        "retrieval_refs_short",
        "session_id",
        "user",
        "created_at",
    )
    list_filter = ("status", "skill_id", "trigger_source")
    raw_id_fields = ("user",)

    @admin.display(description="refs")
    def retrieval_refs_short(self, obj):
        r = obj.retrieval_refs
        if not r:
            return "—"
        if isinstance(r, dict):
            keys = ",".join(sorted(r.keys())[:6])
            return keys or "—"
        return str(type(r).__name__)


@admin.register(SkillEvolutionStaging)
class SkillEvolutionStagingAdmin(admin.ModelAdmin):
    list_display = ("id", "skill", "status", "provenance", "created_at", "reviewed_at")
    list_filter = ("status",)
    raw_id_fields = ("skill", "source_log", "user")
    readonly_fields = ("created_at",)

    actions = ["approve_and_merge"]

    @admin.action(description="批准并合并到 Skill.metadata（evolution_merged_markdown）")
    def approve_and_merge(self, request, queryset):
        from apps.skills.tasks import apply_staging_to_skill

        n = 0
        for st in queryset.filter(status=SkillEvolutionStaging.Status.PENDING):
            if apply_staging_to_skill(st.id):
                n += 1
        self.message_user(request, f"已合并 {n} 条草案。")
