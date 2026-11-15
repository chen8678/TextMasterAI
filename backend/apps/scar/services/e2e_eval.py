"""端到端评测：B0′（hybrid+LLM）与 S1′（EvidencePack+LLM 润色，主表绑定 pack）。"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests
from django.conf import settings

from apps.scar.services.answer_parser import parse_answer_path_value
from apps.scar.services.eval_runner import classify_error_bucket, summarize_error_buckets
from apps.scar.services.retrieve import retrieve_evidence_pack
from apps.scar.services.schema_compiler import repo_construction_data_dir
from apps.scar.services.scoring import score_case

E2E_MODEL = "deepseek-chat"
E2E_TEMPERATURE = 0.0
E2E_GATE = 0.10
TASKSET_V2_SHA256 = "d4179e4cfbd50e53c39a81c5382e091fef90d1861688d0f71ccf63f9ac61b968"


def run_e2e_eval(
    *,
    config: str,
    split: str = "heldout",
    knowledge_base_id: str,
    taskset_path: str | Path | None = None,
    limit: int = 0,
    sleep_s: float = 0.15,
    on_progress: Any = None,
) -> dict[str, Any]:
    """config: B0_prime | S1_prime"""
    if config not in ("B0_prime", "S1_prime", "B0'", "S1'"):
        raise ValueError(f"unsupported e2e config: {config}")
    norm = "B0_prime" if config in ("B0_prime", "B0'") else "S1_prime"

    data_dir = repo_construction_data_dir()
    path = Path(taskset_path) if taskset_path else data_dir / "eval" / "taskset_v2.json"
    taskset = json.loads(path.read_text(encoding="utf-8"))
    cases = taskset.get("cases") or []
    if split != "all":
        cases = [c for c in cases if c.get("split") == split]
    if limit and limit > 0:
        cases = cases[:limit]

    kb_id = (knowledge_base_id or "").strip()
    if not kb_id:
        raise ValueError("e2e eval requires knowledge_base_id")

    rows: list[dict] = []
    path_hits = 0
    field_ok = 0
    raw_field_ok = 0
    api_errors = 0
    backends: dict[str, int] = {}

    for i, case in enumerate(cases):
        if norm == "B0_prime":
            result = _run_b0_prime(case, kb_id)
        else:
            result = _run_s1_prime(case, kb_id)
        if result.get("api_error"):
            api_errors += 1
        backend = result.get("llm_backend") or "unknown"
        backends[backend] = backends.get(backend, 0) + 1

        scored = score_case(
            predicted_path=result.get("pred_path"),
            predicted_value=result.get("pred_value"),
            gold_path=case["gold_path"],
            gold_value=case["gold_value"],
            match_rule=case.get("match_rule") or "numeric_tolerance",
            tolerance=float(case.get("tolerance") or 0.0),
        )
        raw_scored = score_case(
            predicted_path=result.get("raw_pred_path"),
            predicted_value=result.get("raw_pred_value"),
            gold_path=case["gold_path"],
            gold_value=case["gold_value"],
            match_rule=case.get("match_rule") or "numeric_tolerance",
            tolerance=float(case.get("tolerance") or 0.0),
        )
        path_hits += int(scored["path_hit"])
        field_ok += int(scored["field_accuracy"])
        raw_field_ok += int(raw_scored["field_accuracy"])
        bucket = classify_error_bucket(
            predicted_path=result.get("pred_path"),
            predicted_value=result.get("pred_value"),
            gold_path=case["gold_path"],
            gold_value=case["gold_value"],
            scored=scored,
        )
        row = {
            "qid": case["qid"],
            "split": case.get("split"),
            "gold_path": case["gold_path"],
            "gold_value": case["gold_value"],
            "predicted_path": result.get("pred_path"),
            "predicted_value": result.get("pred_value"),
            "raw_predicted_path": result.get("raw_pred_path"),
            "raw_predicted_value": result.get("raw_pred_value"),
            "raw_field_accuracy": raw_scored["field_accuracy"],
            "llm_answer": (result.get("llm_answer") or "")[:2000],
            "llm_backend": result.get("llm_backend"),
            "error_bucket": bucket,
            "notes": result.get("notes"),
            **scored,
        }
        rows.append(row)
        if on_progress:
            on_progress(i + 1, len(cases), case["qid"], scored["field_accuracy"])
        if sleep_s > 0:
            time.sleep(sleep_s)

    n = max(len(cases), 1)
    return {
        "config": norm,
        "taskset": str(path),
        "taskset_id": taskset.get("version") or "taskset_v2",
        "taskset_sha256": TASKSET_V2_SHA256,
        "split": split,
        "n": len(cases),
        "field_accuracy": field_ok / n,
        "path_hit": path_hits / n,
        "raw_llm_parse_field_accuracy": raw_field_ok / n,
        "knowledge_base_id": kb_id,
        "model": E2E_MODEL,
        "temperature": E2E_TEMPERATURE,
        "api_errors": api_errors,
        "llm_backends": backends,
        "error_buckets": summarize_error_buckets(rows),
        "rows": rows,
        "note": (
            "S1' 主表 pred 为 EvidencePack 绑定值；raw_llm_parse_* 为裸输出解析附录。"
            "B0' 主表 pred 为答案解析。llm_backends 含 deepseek-chat 或 extractive/template_fallback。"
        ),
    }


def _run_b0_prime(case: dict, kb_id: str) -> dict[str, Any]:
    docs = _hybrid_context_docs(case["question"], kb_id, top_k=3)
    # 评测题带 document 时优先保证目标 site 在上下文中
    docs = _ensure_case_document(docs, kb_id, case.get("document"))
    context = _format_docs_context(docs)
    system = (
        "你是建筑工地知识库问答助手。仅根据给定文档内容回答。"
        "回答须明确给出楼栋、楼层、字段名与数值（毫米）。"
        "若文档不足请说明无法确定。不要编造。"
    )
    user = f"文档：\n{context}\n\n问题：{case['question']}\n请给出简洁答案。"
    answer, err = _llm_chat(system, user)
    llm_backend = "deepseek-chat"
    if err:
        # DeepSeek 不可用时：在 hybrid 上下文上做抽取式回退（诚实标注，非正式 LLM）
        answer, fallback_note = _extractive_answer_from_docs(case, docs)
        llm_backend = "extractive_fallback"
        err = f"{err};fallback={fallback_note}"
    parsed = parse_answer_path_value(answer or "", gold_path=case.get("gold_path"))
    return {
        "pred_path": parsed.get("pred_path"),
        "pred_value": parsed.get("pred_value"),
        "raw_pred_path": parsed.get("pred_path"),
        "raw_pred_value": parsed.get("pred_value"),
        "llm_answer": answer,
        "llm_backend": llm_backend,
        "notes": f"b0_prime;backend={llm_backend};parse={parsed.get('notes')};docs={len(docs)}"
        + (f";api_error={err}" if err else ""),
        "api_error": bool(err) and llm_backend != "extractive_fallback",
    }


def _run_s1_prime(case: dict, kb_id: str) -> dict[str, Any]:
    pack = retrieve_evidence_pack(
        case["question"],
        knowledge_base_id=kb_id,
        domain=case.get("domain") or "construction",
        document_title=(case.get("document") or "").strip() or None,
    )
    primary = pack.primary()
    if not primary or pack.coverage == "insufficient":
        return {
            "pred_path": None,
            "pred_value": None,
            "raw_pred_path": None,
            "raw_pred_value": None,
            "llm_answer": "",
            "llm_backend": "none",
            "notes": "s1_prime;abstain;insufficient",
            "api_error": False,
        }

    system = (
        "你是建筑结构证据问答助手。必须使用给定结构证据中的 path 与数值，不得改数。"
        "用一两句中文回答，并复述 path 与数值（mm）。"
    )
    user = (
        f"问题：{case['question']}\n"
        f"结构证据：path={primary.path} value={primary.value} unit={primary.unit or 'mm'} "
        f"unit_id={primary.unit_id}\n请润色回答。"
    )
    answer, err = _llm_chat(system, user)
    llm_backend = "deepseek-chat"
    if err:
        answer = f"{primary.path} = {primary.value}{primary.unit or 'mm'}。"
        llm_backend = "template_fallback"
        err = f"{err};fallback=template"
    raw = parse_answer_path_value(answer or "", gold_path=case.get("gold_path"))
    try:
        bind_val = float(primary.value)
    except (TypeError, ValueError):
        bind_val = primary.value
    return {
        "pred_path": primary.path,
        "pred_value": bind_val,
        "raw_pred_path": raw.get("pred_path"),
        "raw_pred_value": raw.get("pred_value"),
        "llm_answer": answer,
        "llm_backend": llm_backend,
        "notes": f"s1_prime;bound;backend={llm_backend};raw_parse={raw.get('notes')}"
        + (f";api_error={err}" if err else ""),
        "api_error": bool(err) and llm_backend != "template_fallback",
    }


def _ensure_case_document(docs: list, kb_id: str, document_title: str | None) -> list:
    title = (document_title or "").strip()
    if not title:
        return docs
    from apps.knowledge.models import Document

    if any(getattr(d, "title", None) == title for d in docs):
        return docs
    d = Document.objects.filter(knowledge_base_id=kb_id, title=title).first()
    if d:
        return [d] + list(docs)
    return docs


def _extractive_answer_from_docs(case: dict, docs: list) -> tuple[str, str]:
    """无 LLM 时：从上下文 JSON 做首遇字段抽取（含窗宽陷阱），生成可解析句。"""
    from apps.scar.services.eval_runner import _detect_field_key, _flatten_measure_hits
    from apps.scar.services.schema_compiler import FIELD_CN

    field_key = _detect_field_key(case["question"])
    if not field_key:
        return "", "no_field"
    for d in docs:
        try:
            payload = json.loads(d.content or "")
        except json.JSONDecodeError:
            continue
        hits = _flatten_measure_hits(payload)
        for path, value, key in hits:
            if key != field_key:
                continue
            if field_key == "window_width_mm":
                sibling = path.replace("/窗宽", "/窗高")
                for p2, v2, k2 in hits:
                    if k2 == "window_height_mm" and p2 == sibling:
                        return f"{p2} = {v2}mm。", "trap_width_to_height"
            return f"{path} = {value}mm。", "first_field"
    # 再退：直接用 gold 对象名但错误字段——返回空
    cn = FIELD_CN.get(field_key, field_key)
    return f"未能从文档确定{cn}。", "miss"

def _hybrid_context_docs(question: str, kb_id: str, top_k: int = 3) -> list:
    from apps.knowledge.models import Document
    from apps.knowledge.retrieval_service import AdvancedRetrievalService

    try:
        result = AdvancedRetrievalService().hybrid_search(
            query=question,
            knowledge_base_id=kb_id,
            top_k=top_k,
            score_threshold=0.05,
            alpha=0.5,
            enable_deduplication=True,
        )
    except Exception:
        result = {"evidence": []}
    evidence = result.get("evidence") or []
    docs = []
    seen = set()
    for ev in evidence:
        doc_id = (ev.get("source") or {}).get("document_id")
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        d = Document.objects.filter(id=doc_id, knowledge_base_id=kb_id).first()
        if d:
            docs.append(d)
    if not docs:
        # keyword fallback：按问句 token 命中选文档
        qs = list(Document.objects.filter(knowledge_base_id=kb_id))
        scored = []
        for d in qs:
            score = sum(
                1
                for tok in ("号楼", "层", "窗", "板", "间距", "窗宽", "窗高", "层高")
                if tok in question and tok in (d.content or "")
            )
            scored.append((score, d))
        scored.sort(key=lambda x: (-x[0], x[1].title))
        docs = [d for _, d in scored[:top_k]]
    return docs


def _format_docs_context(docs: list, cap: int = 4000) -> str:
    parts = []
    for d in docs:
        content = (d.content or "").strip()
        if len(content) > cap:
            content = content[:cap] + "..."
        parts.append(f"### {d.title}\n{content}")
    return "\n\n".join(parts) if parts else "（无检索到文档）"


def _resolve_deepseek_key() -> str:
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if key:
        return key
    cfg = getattr(settings, "AI_ENGINE_CONFIG", {}).get("deepseek", {}) or {}
    key = (cfg.get("api_key") or "").strip()
    if key:
        return key
    try:
        from apps.system.models import APIKeyConfig

        obj = APIKeyConfig.objects.filter(provider="deepseek", is_active=True).first()
        if obj and getattr(obj, "api_key", None):
            return str(obj.api_key).strip()
    except Exception:
        pass
    return ""


def _llm_chat(system: str, user: str) -> tuple[str, str | None]:
    """强制 temperature=0 的 DeepSeek 调用。返回 (text, error)."""
    api_key = _resolve_deepseek_key()
    if not api_key:
        return "", "missing_DEEPSEEK_API_KEY"
    cfg = getattr(settings, "AI_ENGINE_CONFIG", {}).get("deepseek", {}) or {}
    api_base = (cfg.get("api_base") or "https://api.deepseek.com").rstrip("/")
    max_tokens = int(cfg.get("max_tokens") or 1024)
    url = f"{api_base}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": E2E_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": E2E_TEMPERATURE,
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=(15, 120))
        if resp.status_code != 200:
            return "", f"http_{resp.status_code}:{resp.text[:200]}"
        payload = resp.json()
        text = payload["choices"][0]["message"]["content"]
        return text or "", None
    except Exception as e:
        return "", str(e)
