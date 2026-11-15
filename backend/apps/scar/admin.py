from django.contrib import admin
from .models import DomainTemplate, StructureUnit, IndexEntry


@admin.register(DomainTemplate)
class DomainTemplateAdmin(admin.ModelAdmin):
    list_display = ("domain_key", "version", "lifecycle", "updated_at")
    list_filter = ("domain_key", "lifecycle")


@admin.register(StructureUnit)
class StructureUnitAdmin(admin.ModelAdmin):
    list_display = ("path", "value_norm", "unit", "provenance", "document_id")
    list_filter = ("domain", "provenance")
    search_fields = ("path", "unit_id", "value_norm")


@admin.register(IndexEntry)
class IndexEntryAdmin(admin.ModelAdmin):
    list_display = ("domain", "unit_id", "document_id", "updated_at")
    list_filter = ("domain",)

    @admin.display(description="unit_id")
    def unit_id(self, obj):
        return obj.unit.unit_id
