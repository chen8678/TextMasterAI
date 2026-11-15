"""
KB 问答采集工作流：模拟用户提问 → 走 KB 编排链路 → 导出训练 JSON。

供 management command、工作流 API、外部脚本（n8n / cron）调用。
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone as django_timezone

from apps.knowledge.models import KnowledgeBase
from apps.chat.agent_service import AgentOrchestrator

from .content_generation_workflow import _call_ai, _gather_kb_text, _strip_json_block
from .kb_collector_personas import (
    DEFAULT_INSTRUCTION,
    CollectorPersona,
    build_question_generation_prompt,
    build_workflow_config_from_persona,
    get_persona_by_id,
    resolve_persona_for_kb,
)
from .models import WorkflowRun

DEFAULT_OUTPUT_DIR = Path(settings.BASE_DIR) / "data" / "training_datasets"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_output_path(knowledge_base_id: str, run_id: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return DEFAULT_OUTPUT_DIR / f"kb_qa_{knowledge_base_id[:8]}_{ts}_{run_id[:8]}.json"


def _build_context_input(question: str, context_docs: List[Dict[str, Any]]) -> str:
    if not context_docs:
        return question
    chunks = []
    for doc in context_docs[:5]:
        title = (doc.get("title") or "未命名文档").strip()
        content = (doc.get("content") or "").strip()
        if content:
            chunks.append(f"【{title}】\n{content}")
    if not chunks:
        return question
    return (
        f"{question}\n\n"
        "-----\n"
        "检索上下文：\n"
        + "\n\n".join(chunks)
    )


def format_sft_record(
    question: str,
    answer: str,
    context_docs: Optional[List[Dict[str, Any]]] = None,
    instruction: str = DEFAULT_INSTRUCTION,
) -> Dict[str, str]:
    return {
        "instruction": instruction,
        "input": _build_context_input(question, context_docs or []),
        "output": answer,
    }


def format_training_record(
    *,
    question: str,
    result: Dict[str, Any],
    knowledge_base_id: str,
    agent_id: str,
    retrieval_params: Dict[str, Any],
    instruction: str = DEFAULT_INSTRUCTION,
    question_source: str = "provided",
    persona: Optional[CollectorPersona] = None,
) -> Dict[str, Any]:
    context_docs = result.get("context_docs") or []
    answer = (result.get("answer") or "").strip()
    record = {
        "id": str(uuid.uuid4()),
        "question": question,
        "answer": answer,
        "sources": result.get("sources") or [],
        "context_docs": context_docs,
        "skills_used": result.get("skills_used") or [],
        "agent_id": result.get("agent_id") or agent_id,
        "agent_name": result.get("agent_name") or "",
        "answer_source": result.get("answer_source") or "",
        "knowledge_base_id": knowledge_base_id,
        "retrieval_params": retrieval_params,
        "question_source": question_source,
        "collected_at": _utc_now_iso(),
        "sft": format_sft_record(question, answer, context_docs, instruction),
    }
    if persona:
        record["persona_id"] = persona.id
        record["role_name"] = persona.role_name
    return record


def _normalize_questions(raw: Any) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        q = raw.strip()
        return [q] if q else []
    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                q = str(item.get("question") or item.get("q") or "").strip()
                if q:
                    out.append(q)
        return out
    return []


def _resolve_seed_path(seed_path: str) -> str:
    if not seed_path:
        return ""
    path = Path(seed_path)
    if path.is_file():
        return str(path)
    alt = Path(settings.BASE_DIR) / seed_path
    if alt.is_file():
        return str(alt)
    alt2 = Path(settings.BASE_DIR).parent / seed_path
    if alt2.is_file():
        return str(alt2)
    return seed_path


def _load_questions_from_seed(seed_path: str) -> List[str]:
    resolved = _resolve_seed_path(seed_path)
    path = Path(resolved)
    if not path.is_file():
        raise FileNotFoundError(f"种子问题文件不存在: {seed_path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return _normalize_questions(data)
    if isinstance(data, dict):
        if "questions" in data:
            return _normalize_questions(data["questions"])
        if "cases" in data:
            return _normalize_questions(data["cases"])
    raise ValueError("种子文件格式无效，需为字符串数组或含 questions/cases 字段的对象")


def generate_questions_from_kb(
    knowledge_base_id: str,
    *,
    count: int = 10,
    ai_model: str = "deepseek",
    config: Optional[Dict[str, Any]] = None,
    persona: Optional[CollectorPersona] = None,
) -> List[str]:
    """基于知识库文档，用 LLM 按提问角色生成模拟用户问题。"""
    config = config or {}
    text = _gather_kb_text(str(knowledge_base_id))
    if not text.strip():
        return []
    count = max(1, min(int(count), 50))
    if persona:
        prompt, system = build_question_generation_prompt(persona, text, count)
    else:
        prompt = f"""你是知识库问答数据标注员。请根据以下知识库内容，生成 {count} 个真实用户可能会问的问题。

要求：
1. 问题应覆盖不同知识点，表述自然、口语化
2. 优先问能在材料中找到依据的事实性问题
3. 不要生成重复或过于相似的问题
4. 只输出 JSON 数组，每项为字符串，不要 markdown 代码块

知识库内容：
---
{text[:15000]}
---"""
        system = "你只输出合法 JSON 字符串数组，例如 [\"问题1\", \"问题2\"]。"
    raw = _call_ai(prompt, system, ai_model, config.get("max_tokens", 2000))
    cleaned = _strip_json_block(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return _normalize_questions(parsed)[:count]


def resolve_questions(
    *,
    knowledge_base_id: str,
    questions: Optional[List[str]] = None,
    question_source: str = "inline",
    seed_path: str = "",
    llm_question_count: int = 0,
    ai_model: str = "deepseek",
    config: Optional[Dict[str, Any]] = None,
    persona: Optional[CollectorPersona] = None,
) -> tuple[List[str], str]:
    """按来源解析待采集问题列表，返回 (questions, resolved_source)。"""
    source = (question_source or "inline").strip().lower()
    if source == "inline":
        qs = _normalize_questions(questions)
        if qs:
            return qs, "inline"
        if seed_path:
            return _load_questions_from_seed(seed_path), "seed_file"
        if llm_question_count > 0:
            return (
                generate_questions_from_kb(
                    knowledge_base_id,
                    count=llm_question_count,
                    ai_model=ai_model,
                    config=config,
                    persona=persona,
                ),
                "llm_from_kb",
            )
        return [], "inline"
    if source == "seed_file":
        if not seed_path:
            raise ValueError("question_source=seed_file 时必须提供 seed_path")
        return _load_questions_from_seed(seed_path), "seed_file"
    if source == "llm_from_kb":
        count = llm_question_count or 10
        return (
            generate_questions_from_kb(
                knowledge_base_id,
                count=count,
                ai_model=ai_model,
                config=config,
                persona=persona,
            ),
            "llm_from_kb",
        )
    raise ValueError(f"不支持的 question_source: {question_source}")


def query_kb_once(
    *,
    question: str,
    knowledge_base_id: str,
    user,
    agent_id: str = "qa",
    retrieval_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """通过 Agent 编排链路执行一次问答（与线上一致）。"""
    orchestrator = AgentOrchestrator(agent_id=agent_id)
    return orchestrator.process(
        question,
        knowledge_base_id,
        user,
        retrieval_params=retrieval_params or {},
    )


def save_collector_dataset(
    payload: Dict[str, Any],
    output_path: Optional[str] = None,
) -> Path:
    path = Path(output_path) if output_path else _default_output_path(
        payload.get("meta", {}).get("knowledge_base_id", "unknown"),
        payload.get("meta", {}).get("run_id", str(uuid.uuid4())),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    jsonl_path = path.with_suffix(".jsonl")
    with jsonl_path.open("w", encoding="utf-8") as f:
        for record in payload.get("records", []):
            f.write(json.dumps(record.get("sft") or record, ensure_ascii=False) + "\n")
    return path


def _merge_collector_params(
    *,
    persona: Optional[CollectorPersona],
    auto_use_persona: bool,
    persona_id: str,
    questions: Optional[List[str]],
    question_source: str,
    seed_path: str,
    llm_question_count: int,
    agent_id: str,
    instruction: str,
    config: Dict[str, Any],
    retrieval_params: Optional[Dict[str, Any]],
    delay_seconds: float,
    max_questions: int,
    output_path: str,
    dry_run: bool,
    ai_model: str,
) -> tuple[Dict[str, Any], Optional[CollectorPersona]]:
    """合并显式参数与角色默认配置，显式非空值优先。"""
    resolved_persona = persona
    if not resolved_persona and auto_use_persona:
        resolved_persona = get_persona_by_id(persona_id) if persona_id else None

    base: Dict[str, Any] = {}
    if resolved_persona:
        base = build_workflow_config_from_persona(resolved_persona)

    def pick(key: str, explicit: Any, default: Any = ""):
        if explicit not in (None, "", [], {}):
            return explicit
        return base.get(key, default)

    merged = {
        "questions": pick("questions", questions, []),
        "question_source": pick("question_source", question_source, "inline"),
        "seed_path": pick("seed_path", seed_path, ""),
        "llm_question_count": int(
            llm_question_count or base.get("llm_question_count") or 0
        ),
        "agent_id": pick("agent_id", agent_id, "qa"),
        "instruction": pick("instruction", instruction, DEFAULT_INSTRUCTION),
        "ai_model": pick("ai_model", ai_model, "deepseek"),
        "config": config or base.get("config") or {},
        "retrieval_params": retrieval_params or base.get("retrieval_params"),
        "delay_seconds": delay_seconds if delay_seconds != 0.5 else base.get("delay_seconds", 0.5),
        "max_questions": max_questions if max_questions != 50 else base.get("max_questions", 50),
        "output_path": pick("output_path", output_path, ""),
        "dry_run": dry_run or base.get("dry_run", False),
    }
    return merged, resolved_persona


def run_kb_qa_collector_workflow(
    *,
    knowledge_base_id: str,
    user,
    questions: Optional[List[str]] = None,
    question_source: str = "inline",
    seed_path: str = "",
    llm_question_count: int = 0,
    agent_id: str = "qa",
    ai_model: str = "deepseek",
    config: Optional[Dict[str, Any]] = None,
    retrieval_params: Optional[Dict[str, Any]] = None,
    instruction: str = "",
    delay_seconds: float = 0.5,
    max_questions: int = 50,
    output_path: str = "",
    dry_run: bool = False,
    persona_id: str = "",
    auto_use_persona: bool = True,
    persona: Optional[CollectorPersona] = None,
) -> Dict[str, Any]:
    """
    执行 KB 问答采集工作流。

    步骤：解析问题 → 逐条调用 KB 编排 → 汇总 → 写入 JSON / JSONL。
    """
    config = config or {}
    kb = KnowledgeBase.objects.filter(id=knowledge_base_id).first()
    if not kb:
        return {
            "success": False,
            "error": "知识库不存在",
            "total_collected": 0,
            "records": [],
            "output_path": None,
        }

    if not persona and auto_use_persona:
        persona = resolve_persona_for_kb(
            knowledge_base_id=str(knowledge_base_id),
            knowledge_base_title=kb.title,
            persona_id=persona_id,
        )

    params, persona = _merge_collector_params(
        persona=persona,
        auto_use_persona=auto_use_persona,
        persona_id=persona_id,
        questions=questions,
        question_source=question_source,
        seed_path=seed_path,
        llm_question_count=llm_question_count,
        agent_id=agent_id,
        instruction=instruction,
        config=config,
        retrieval_params=retrieval_params,
        delay_seconds=delay_seconds,
        max_questions=max_questions,
        output_path=output_path,
        dry_run=dry_run,
        ai_model=ai_model,
    )

    question_source = params["question_source"]
    seed_path = params["seed_path"]
    llm_question_count = params["llm_question_count"]
    agent_id = params["agent_id"]
    instruction = params["instruction"]
    ai_model = params["ai_model"]
    config = params["config"]
    retrieval_params = params["retrieval_params"] or {
        "strategy": config.get("strategy", "hybrid"),
        "top_k": config.get("top_k", 5),
        "score_threshold": config.get("score_threshold", 0.15),
        "alpha": config.get("alpha", 0.5),
    }
    delay_seconds = float(params["delay_seconds"])
    max_questions = int(params["max_questions"])
    output_path = params["output_path"]
    dry_run = bool(params["dry_run"])
    questions = params["questions"]

    run = WorkflowRun.objects.create(
        workflow_id="kb_qa_collector",
        knowledge_base_id=knowledge_base_id,
        user=user,
        status="running",
        input_params={
            "question_source": question_source,
            "seed_path": seed_path,
            "llm_question_count": llm_question_count,
            "agent_id": agent_id,
            "ai_model": ai_model,
            "config": config,
            "retrieval_params": retrieval_params,
            "max_questions": max_questions,
            "dry_run": dry_run,
            "persona_id": persona.id if persona else persona_id,
            "role_name": persona.role_name if persona else "",
        },
    )

    try:
        resolved_questions, resolved_source = resolve_questions(
            knowledge_base_id=str(knowledge_base_id),
            questions=questions,
            question_source=question_source,
            seed_path=seed_path,
            llm_question_count=llm_question_count,
            ai_model=ai_model,
            config=config,
            persona=persona,
        )
        if max_questions > 0:
            resolved_questions = resolved_questions[:max_questions]

        if not resolved_questions:
            run.status = "failed"
            run.error_message = "没有可采集的问题"
            run.finished_at = django_timezone.now()
            run.save()
            return {
                "success": False,
                "error": "没有可采集的问题",
                "run_id": str(run.id),
                "total_collected": 0,
                "records": [],
                "output_path": None,
            }

        records: List[Dict[str, Any]] = []
        errors: List[Dict[str, str]] = []

        for idx, question in enumerate(resolved_questions):
            if dry_run:
                item = {
                    "id": str(uuid.uuid4()),
                    "question": question,
                    "answer": "",
                    "dry_run": True,
                    "question_source": resolved_source,
                    "knowledge_base_id": str(knowledge_base_id),
                    "collected_at": _utc_now_iso(),
                }
                if persona:
                    item["persona_id"] = persona.id
                    item["role_name"] = persona.role_name
                records.append(item)
                continue
            try:
                result = query_kb_once(
                    question=question,
                    knowledge_base_id=str(knowledge_base_id),
                    user=user,
                    agent_id=agent_id,
                    retrieval_params=retrieval_params,
                )
                records.append(
                    format_training_record(
                        question=question,
                        result=result,
                        knowledge_base_id=str(knowledge_base_id),
                        agent_id=agent_id,
                        retrieval_params=retrieval_params,
                        instruction=instruction,
                        question_source=resolved_source,
                        persona=persona,
                    )
                )
            except Exception as exc:
                errors.append({"question": question, "error": str(exc)})
            if delay_seconds > 0 and idx < len(resolved_questions) - 1:
                time.sleep(delay_seconds)

        payload = {
            "meta": {
                "workflow": "kb_qa_collector",
                "version": "2026-07-10-v2",
                "run_id": str(run.id),
                "knowledge_base_id": str(knowledge_base_id),
                "knowledge_base_title": kb.title,
                "persona_id": persona.id if persona else None,
                "role_name": persona.role_name if persona else None,
                "question_source": resolved_source,
                "agent_id": agent_id,
                "retrieval_params": retrieval_params,
                "total_questions": len(resolved_questions),
                "total_collected": len(records),
                "total_errors": len(errors),
                "dry_run": dry_run,
                "created_at": _utc_now_iso(),
            },
            "records": records,
            "errors": errors,
        }

        saved_path = None
        if records and not dry_run:
            saved_path = save_collector_dataset(payload, output_path or None)

        run.status = "success" if not errors or records else "failed"
        run.output_summary = {
            "total_collected": len(records),
            "total_errors": len(errors),
            "output_path": str(saved_path) if saved_path else None,
            "question_source": resolved_source,
        }
        if errors and not records:
            run.error_message = errors[0]["error"]
        run.finished_at = django_timezone.now()
        run.save()

        return {
            "success": bool(records),
            "run_id": str(run.id),
            "total_questions": len(resolved_questions),
            "total_collected": len(records),
            "total_errors": len(errors),
            "question_source": resolved_source,
            "persona_id": persona.id if persona else None,
            "role_name": persona.role_name if persona else None,
            "records": records,
            "errors": errors,
            "output_path": str(saved_path) if saved_path else None,
            "jsonl_path": str(saved_path.with_suffix(".jsonl")) if saved_path else None,
        }
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = django_timezone.now()
        run.save()
        return {
            "success": False,
            "error": str(exc),
            "run_id": str(run.id),
            "total_collected": 0,
            "records": [],
            "output_path": None,
        }
