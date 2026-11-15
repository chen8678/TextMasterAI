"""文档级 SCAR 编译落库。"""

from __future__ import annotations

import logging
from typing import Any, Optional

from django.db import transaction

from apps.scar.models import DomainTemplate, StructureUnit
from apps.scar.services.directed_index import rebuild_index_for_document
from apps.scar.services.schema_compiler import (
    CompileError,
    compile_construction_units,
    default_construction_template_spec,
)

logger = logging.getLogger(__name__)


def get_active_template(domain_key: str) -> Optional[DomainTemplate]:
    return (
        DomainTemplate.objects.filter(
            domain_key=domain_key, lifecycle=DomainTemplate.Lifecycle.ACTIVE
        )
        .order_by("-version")
        .first()
    )


def ensure_construction_template() -> DomainTemplate:
    tpl = get_active_template("construction")
    if tpl:
        return tpl
    spec = default_construction_template_spec()
    return DomainTemplate.objects.create(
        domain_key="construction",
        version=1,
        lifecycle=DomainTemplate.Lifecycle.ACTIVE,
        spec_json=spec,
        index_whitelist=list(spec.get("index_whitelist_keys") or []),
        alias_map=dict(spec.get("alias_to_key") or {}),
        unit_rules={"base": "mm"},
        notes="seeded construction v1",
    )


@transaction.atomic
def compile_document(
    document,
    *,
    domain: str = "construction",
    raw_text: Optional[str] = None,
    vectorize: bool = True,
) -> dict[str, Any]:
    """
    对 Document 做结构编译。原文 content 不改写。
    raw_text 默认取 document.content（应为 JSON 文本）。
    """
    domain = (domain or "construction").strip() or "construction"
    tpl = ensure_construction_template() if domain == "construction" else get_active_template(domain)
    if not tpl:
        document.scar_domain = domain
        document.compile_status = "failed"
        document.save(update_fields=["scar_domain", "compile_status", "updated_at"])
        return {"ok": False, "error": f"无 active 模板: {domain}"}

    text = raw_text if raw_text is not None else document.content
    try:
        if domain != "construction":
            raise CompileError(f"本期仅支持 construction，收到 {domain}")
        unit_dicts = compile_construction_units(text, template_version=tpl.version)
    except CompileError as e:
        document.scar_domain = domain
        document.compile_status = "failed"
        document.template_version = tpl.version
        md = document.metadata or {}
        md["scar_compile_error"] = str(e)
        document.metadata = md
        document.save(
            update_fields=["scar_domain", "compile_status", "template_version", "metadata", "updated_at"]
        )
        return {"ok": False, "error": str(e)}

    StructureUnit.objects.filter(document=document).delete()
    units = [
        StructureUnit(
            document=document,
            unit_id=u["unit_id"],
            path=u["path"],
            unit_type=u.get("unit_type") or "field",
            value_norm=u["value_norm"],
            unit=u.get("unit") or "",
            source_ref=u["source_ref"],
            provenance=u.get("provenance") or StructureUnit.Provenance.PARSER,
            domain=domain,
            template_version=tpl.version,
            metadata=u.get("metadata") or {},
        )
        for u in unit_dicts
    ]
    StructureUnit.objects.bulk_create(units)
    saved = list(StructureUnit.objects.filter(document=document))
    index_count = rebuild_index_for_document(document, saved, vectorize=vectorize)

    document.scar_domain = domain
    document.compile_status = "ok"
    document.template_version = tpl.version
    md = document.metadata or {}
    md.pop("scar_compile_error", None)
    md["scar_unit_count"] = len(saved)
    md["scar_index_count"] = index_count
    document.metadata = md
    document.save(
        update_fields=["scar_domain", "compile_status", "template_version", "metadata", "updated_at"]
    )
    return {"ok": True, "unit_count": len(saved), "index_count": index_count, "template_version": tpl.version}
