"""SCAR 召回 Skill → EvidencePack。"""

from typing import Any

from apps.scar.services.retrieve import retrieve_evidence_pack


def execute(
    query: str,
    knowledge_base_id: str,
    top_k: int = 8,
    domain: str = "construction",
    ablation: str = "",
    **kwargs: Any,
) -> dict:
    pack = retrieve_evidence_pack(
        query,
        knowledge_base_id=str(knowledge_base_id),
        domain=domain,
        top_k=top_k,
        ablation=ablation or None,
    )
    primary = pack.primary()
    return {
        "evidence_pack": pack.to_dict(),
        "count": len(pack.items),
        "coverage": pack.coverage,
        "primary_path": primary.path if primary else None,
        "primary_value": primary.value if primary else None,
        "titles": [i.path for i in pack.items],
    }
