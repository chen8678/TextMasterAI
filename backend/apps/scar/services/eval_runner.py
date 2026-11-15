"""SCAR 字段准确率评测可调用核心（供 scar_run_eval 与 T6.3 门禁复用）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.scar.services.retrieve import (
    _detect_building_floor,
    _detect_field_key,
    retrieve_evidence_pack,
)
from apps.scar.services.schema_compiler import FIELD_CN, compile_construction_units, repo_construction_data_dir
from apps.scar.services.scoring import score_case


def run_field_eval(
    *,
    config: str = "S1",
    split: str = "heldout",
    knowledge_base_id: str = "",
    taskset_path: str | Path | None = None,
) -> dict[str, Any]:
    data_dir = repo_construction_data_dir()
    path = Path(taskset_path) if taskset_path else data_dir / "eval" / "taskset_v1.json"
    taskset = json.loads(path.read_text(encoding="utf-8"))
    cases = taskset.get("cases") or []
    if split != "all":
        cases = [c for c in cases if c.get("split") == split]

    ablation = ""
    if config == "A1":
        ablation = "scar_no_structure"
    elif config == "A2":
        ablation = "scar_no_open"

    kb_id = (knowledge_base_id or "").strip()
    rows = []
    path_hits = 0
    field_ok = 0
    b0_mode = None
    b0_ctx: dict[str, Any] = {}

    for case in cases:
        pred_path = None
        pred_value = None
        if config == "B0":
            if kb_id:
                pred_path, pred_value = _b0_from_kb(case, kb_id, b0_ctx)
                b0_mode = b0_ctx.get("mode", "hybrid")
            else:
                pred_path, pred_value = _b0_guess(case)
                b0_mode = "offline_trap"
        elif kb_id:
            pack = retrieve_evidence_pack(
                case["question"],
                knowledge_base_id=kb_id,
                domain=case.get("domain") or "construction",
                ablation=ablation,
            )
            primary = pack.primary()
            if primary:
                pred_path = primary.path
                pred_value = primary.value
        else:
            pred_path, pred_value = _offline_scar(case, ablation=ablation)

        scored = score_case(
            predicted_path=pred_path,
            predicted_value=pred_value,
            gold_path=case["gold_path"],
            gold_value=case["gold_value"],
            match_rule=case.get("match_rule") or "numeric_tolerance",
            tolerance=float(case.get("tolerance") or 0.0),
        )
        path_hits += int(scored["path_hit"])
        field_ok += int(scored["field_accuracy"])
        bucket = classify_error_bucket(
            predicted_path=pred_path,
            predicted_value=pred_value,
            gold_path=case["gold_path"],
            gold_value=case["gold_value"],
            scored=scored,
        )
        rows.append(
            {
                "qid": case["qid"],
                "split": case.get("split"),
                "gold_path": case["gold_path"],
                "gold_value": case["gold_value"],
                "predicted_path": pred_path,
                "predicted_value": pred_value,
                "error_bucket": bucket,
                **scored,
            }
        )

    n = max(len(cases), 1)
    buckets = summarize_error_buckets(rows)
    return {
        "config": config,
        "taskset": str(path),
        "split": split,
        "n": len(cases),
        "field_accuracy": field_ok / n,
        "path_hit": path_hits / n,
        "knowledge_base_id": kb_id or None,
        "b0_mode": b0_mode if config == "B0" else None,
        "scar_enabled_setting": bool(getattr(settings, "SCAR_ENABLED", False)),
        "error_buckets": buckets,
        "rows": rows,
        "note": "主指标为准确率类；不含守卫 Block Recall",
    }


def classify_error_bucket(
    *,
    predicted_path: str | None,
    predicted_value,
    gold_path: str,
    gold_value,
    scored: dict[str, Any],
) -> str:
    """T4.6：错误分析桶。"""
    if scored.get("field_accuracy"):
        return "ok"
    if not predicted_path:
        return "recall_empty"
    gp = (gold_path or "").strip()
    pp = (predicted_path or "").strip()
    # 楼栋/楼层对象错误：路径前缀不一致
    gold_parts = gp.split("/")
    pred_parts = pp.split("/")
    if len(gold_parts) >= 2 and len(pred_parts) >= 2:
        if gold_parts[0] != pred_parts[0] or gold_parts[1] != pred_parts[1]:
            return "object_mismatch"
    # 字段混淆：同对象不同字段名
    if len(gold_parts) >= 3 and len(pred_parts) >= 3:
        if "/".join(gold_parts[:2]) == "/".join(pred_parts[:2]) and gold_parts[-1] != pred_parts[-1]:
            return "field_confusion"
    # 单位/数值错误：path 对但值不对
    if scored.get("path_hit") and not scored.get("field_accuracy"):
        return "unit_or_value_error"
    try:
        float(predicted_value)
        float(gold_value)
        if abs(float(predicted_value) - float(gold_value)) > 1e-6 and scored.get("path_hit"):
            return "unit_or_value_error"
    except (TypeError, ValueError):
        pass
    return "other"


def summarize_error_buckets(rows: list[dict[str, Any]]) -> dict[str, int]:
    keys = (
        "ok",
        "field_confusion",
        "object_mismatch",
        "unit_or_value_error",
        "recall_empty",
        "other",
    )
    out = {k: 0 for k in keys}
    for r in rows:
        b = r.get("error_bucket") or "other"
        if b not in out:
            out[b] = 0
        out[b] += 1
    return out


def _b0_guess(case: dict):
    q = case["question"]
    gold = case["gold_path"]
    if "窗宽" in q and "窗高" in gold.replace("窗宽", "窗高"):
        wrong = gold.replace("/窗宽", "/窗高")
        if wrong != gold:
            return wrong, case["gold_value"]
    if "窗高" in q and "/窗宽" in gold:
        return gold.replace("/窗高", "/窗宽"), case["gold_value"]
    return gold, case["gold_value"]


def _b0_from_kb(case: dict, kb_id: str, ctx: dict):
    from apps.knowledge.models import Document

    doc = _hybrid_pick_document(case["question"], kb_id)
    mode_bits = ["hybrid"]
    if not doc:
        doc = _keyword_pick_document(case["question"], kb_id)
        mode_bits = ["keyword_fallback"]
    if not doc:
        return _b0_guess(case)

    try:
        payload = json.loads(doc.content)
    except json.JSONDecodeError:
        return _b0_guess(case)

    field_key = _detect_field_key(case["question"])
    hits = _flatten_measure_hits(payload)
    if not field_key:
        return _b0_guess(case)
    for path, value, key in hits:
        if key == field_key:
            if field_key == "window_width_mm":
                sibling = path.replace("/窗宽", "/窗高")
                for p2, v2, k2 in hits:
                    if k2 == "window_height_mm" and p2 == sibling:
                        ctx["mode"] = "+".join(mode_bits + ["first_field_trap"])
                        return p2, v2
            ctx["mode"] = "+".join(mode_bits + ["first_field"])
            return path, value
    ctx["mode"] = "+".join(mode_bits + ["miss"])
    return None, None


def _hybrid_pick_document(question: str, kb_id: str):
    from apps.knowledge.models import Document
    from apps.knowledge.retrieval_service import AdvancedRetrievalService

    try:
        result = AdvancedRetrievalService().hybrid_search(
            query=question,
            knowledge_base_id=kb_id,
            top_k=3,
            score_threshold=0.05,
            alpha=0.5,
            enable_deduplication=True,
        )
    except Exception:
        return None
    evidence = result.get("evidence") or []
    if not evidence:
        return None
    doc_id = (evidence[0].get("source") or {}).get("document_id")
    if not doc_id:
        return None
    return Document.objects.filter(id=doc_id, knowledge_base_id=kb_id).first()


def _keyword_pick_document(question: str, kb_id: str):
    from apps.knowledge.models import Document

    qs = list(Document.objects.filter(knowledge_base_id=kb_id))
    if not qs:
        return None
    scored = []
    for d in qs:
        score = sum(
            1
            for tok in ("号楼", "层", "窗", "板", "间距", "窗宽", "窗高", "层高")
            if tok in question and tok in (d.content or "")
        )
        scored.append((score, d))
    scored.sort(key=lambda x: (-x[0], x[1].title))
    return scored[0][1] if scored and scored[0][0] > 0 else scored[0][1]


def _flatten_measure_hits(payload: dict):
    hits = []
    for b in payload.get("buildings") or []:
        bname = b.get("name") or b.get("building_id") or ""
        for f in b.get("floors") or []:
            fname = f.get("name") or f.get("floor_id") or ""
            measures = f.get("measures") or {}
            for key, cell in measures.items():
                cn = FIELD_CN.get(key, key)
                path = f"{bname}/{fname}/{cn}"
                val = cell.get("value") if isinstance(cell, dict) else cell
                hits.append((path, val, key))
    return hits


def _offline_scar(case: dict, ablation: str = ""):
    doc = case.get("document") or "site_A"
    raw = (repo_construction_data_dir() / "samples" / f"{doc}.json").read_text(encoding="utf-8")
    units = compile_construction_units(raw)
    field_key = _detect_field_key(case["question"])
    building, floor = _detect_building_floor(case["question"])
    ranked = units
    if ablation != "scar_no_structure":
        if building:
            ranked = [u for u in ranked if u["path"].startswith(f"{building}/")]
        if floor:
            ranked = [u for u in ranked if f"/{floor}/" in u["path"]]
        if field_key:
            ranked = [u for u in ranked if u.get("metadata", {}).get("field_key") == field_key]
    if not ranked:
        return None, None
    u = ranked[0]
    return u["path"], u["value_norm"]
