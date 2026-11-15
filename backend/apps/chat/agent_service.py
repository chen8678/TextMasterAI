"""
AgentOrchestrator：根据 agent_id 选择 Agent，编排 Skill 调用，返回 answer + skills_used
支持关键词触发：当问题含「生成总结」「生成摘要」「生成问答集」等时，触发大模型内容生成工作流
"""
from typing import Dict, Any, List, Optional
from uuid import UUID
from apps.agents.models import Agent
from apps.chat.services import QAService
from apps.skills.registry import SkillRegistry, log_skill_execution
from apps.skills.eligibility import should_include_skill
from apps.skills.models import Skill

# 与 rag_answer 等价走检索的「场景」Skill（builtin 内多委托 rag_answer.execute）
RAG_LIKE_SKILLS = frozenset(
    {
        "rag_answer",
        "text_law_assist",
        "text_paper_assist",
        "text_format_assist",
        "text_novel_assist",
    }
)
PRO_ONLY_AGENT_IDS = frozenset({"studio_pro"})
PRO_ONLY_SKILL_IDS = frozenset({"novel_continuer", "paper_section_generator", "contract_filler"})


def get_orchestrator_by_tier(user, requested_agent_id: str = "qa") -> "AgentOrchestrator":
    """按用户档位选择可用 orchestrator（P2-T40）。"""
    is_pro = bool(user and getattr(user, "is_authenticated", False) and getattr(user, "is_pro", False))
    agent_id = requested_agent_id or "qa"
    if (not is_pro) and agent_id in PRO_ONLY_AGENT_IDS:
        agent_id = "qa"
    return AgentOrchestrator(agent_id=agent_id)


class AgentOrchestrator:
    def __init__(self, agent_id: str = "qa"):
        try:
            self.agent = Agent.objects.get(id=agent_id, is_active=True)
        except Agent.DoesNotExist:
            self.agent = Agent.objects.filter(is_active=True).first()
            if not self.agent:
                raise ValueError("无可用 Agent，请先执行初始化脚本")
        self.qa_service = QAService(model=self.agent.default_model)

    def process(
        self,
        question: str,
        knowledge_base_id: str,
        user,
        retrieval_params: Optional[Dict[str, Any]] = None,
        auxiliary_knowledge_base_ids: Optional[List[str]] = None,
        session_id: Optional[UUID] = None,
        scene: Optional[str] = None,
        english_learning: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        skills_used: List[str] = []
        context_docs = []
        supplemental_analysis_parts: List[str] = []
        retrieval_params = retrieval_params or {}
        strategy = retrieval_params.get("strategy", "hybrid")
        top_k = retrieval_params.get("top_k", 5)
        score_threshold = retrieval_params.get("score_threshold", 0.15)
        alpha = retrieval_params.get("alpha", 0.5)

        # 构建经 eligibility 过滤的 skill 列表
        raw_skill_ids = [sid for sid in (self.agent.skills or []) if sid in SkillRegistry.list_ids()]
        try:
            skills_in_db = {s.id: s for s in Skill.objects.filter(id__in=raw_skill_ids)}
            eligible_skill_ids = [
                sid for sid in raw_skill_ids
                if skills_in_db.get(sid) is None or should_include_skill(skills_in_db[sid])
            ]
        except Exception:
            eligible_skill_ids = raw_skill_ids
        if not getattr(user, "is_pro", False):
            eligible_skill_ids = [sid for sid in eligible_skill_ids if sid not in PRO_ONLY_SKILL_IDS]

        el_ctx = english_learning or {}
        deny = el_ctx.get("skill_denylist") or set()
        if deny:
            eligible_skill_ids = [sid for sid in eligible_skill_ids if sid not in deny]
        excerpt = (el_ctx.get("roadmap_excerpt") or "").strip()
        if excerpt:
            supplemental_analysis_parts.append(
                "## 当前生效的个人学习路线（摘录；回答时请与该路线对齐）\n" + excerpt[:8000]
            )

        # 0. 关键词触发：大模型内容生成工作流（参考 Keyword-Triggered Skills）
        if "skill_creator" in eligible_skill_ids:
            result, err = SkillRegistry.execute_safe(
                "skill_creator",
                session_id=session_id,
                user=user,
                question=question,
            )
            if not err and result and result.get("triggered"):
                log_skill_execution(
                    "skill_creator", "success",
                    f"query={question[:80]}", f"skill_id={result.get('skill_id', '')}",
                    session_id=session_id,
                    user=user,
                )
                trial = result.get("trial_run") or {}
                trial_text = ""
                if isinstance(trial, dict) and trial:
                    if trial.get("ok"):
                        trial_text = "\n\n试运行结果：成功（新 Skill 已可执行）。"
                    else:
                        trial_text = f"\n\n试运行结果：失败（{trial.get('error') or '未知错误'}）。"
                return {
                    "answer": (result.get("message", "Skill 创建完成。") + trial_text).strip(),
                    "sources": [result.get("file_path", "")] if result.get("file_path") else [],
                    "skills_used": ["skill_creator"] + ([result.get("skill_id")] if result.get("skill_id") else []),
                    "agent_name": self.agent.name,
                    "agent_id": self.agent.id,
                    "answer_source": "skill_creator",
                    "context_docs": [],
                }

        if "content_generation" in eligible_skill_ids:
            result, err = SkillRegistry.execute_safe(
                "content_generation",
                session_id=session_id,
                user=user,
                question=question,
                knowledge_base_id=knowledge_base_id,
                ai_model=retrieval_params.get("ai_model", "deepseek"),
                config=retrieval_params.get("config", {}),
            )
            if not err and result and result.get("triggered"):
                log_skill_execution(
                    "content_generation", "success",
                    f"query={question[:80]}", f"types={result.get('content_types', [])}",
                    session_id=session_id,
                    user=user,
                )
                return {
                    "answer": result.get("answer", "内容生成完成。"),
                    "sources": [],
                    "skills_used": ["content_generation"],
                    "agent_name": self.agent.name,
                    "agent_id": self.agent.id,
                    "answer_source": "content_generation",
                    "context_docs": [],
                }

        # DS-RAG 旁路：默认关；显式 dsrag_mode=true 时走 apps.dsrag（不改 SCAR 主链）
        from django.conf import settings as dj_settings

        if "dsrag_mode" in retrieval_params:
            dsrag_mode = bool(retrieval_params.get("dsrag_mode"))
        else:
            dsrag_mode = bool(getattr(dj_settings, "DSRAG_ENABLED", False))
        if dsrag_mode:
            try:
                from apps.dsrag.config import load_merged
                from apps.dsrag.pipeline import RUNNERS

                cfg = str(
                    retrieval_params.get("dsrag_config")
                    or getattr(dj_settings, "DSRAG_DEFAULT_CONFIG", "R3")
                    or "R3"
                ).strip()
                runner = RUNNERS.get(cfg) or RUNNERS["R3"]
                merged = load_merged()
                case = {"id": f"online-{session_id or 'anon'}", "question": question}
                trace = runner(case, merged=merged)
                if trace.status == "refuse_scope":
                    answer_text = (
                        "【拒答·超纲】该问题不在当前知识域范围内，无法基于资料回答。"
                    )
                elif trace.status == "refuse_evidence":
                    answer_text = (
                        "【拒答·证据不足】检索到的资料不足以可靠回答该问题，暂不生成答案。"
                    )
                else:
                    answer_text = (trace.answer_text or "").strip() or "（空回答）"
                sources = list(trace.retrieve_ids or [])
                return {
                    "answer": answer_text,
                    "sources": sources,
                    "skills_used": [f"dsrag_{trace.config_id}"],
                    "agent_name": self.agent.name,
                    "agent_id": self.agent.id,
                    "answer_source": "dsrag",
                    "context_docs": [],
                    "dsrag_status": trace.status,
                    "dsrag_config": trace.config_id,
                    "dsrag_generated": bool(trace.generated),
                    "dsrag_policy_hash": trace.policy_hash,
                    "abstained": trace.status != "answer",
                }
            except Exception as e:
                # 旁路失败不污染默认路径：回落后续 RAG/SCAR
                log_skill_execution(
                    "dsrag",
                    "error",
                    f"query={question[:80]}",
                    f"err={e}",
                    session_id=session_id,
                    user=user,
                )

        # SCAR 路径：请求显式 scar_mode 优先；否则跟随 SCAR_ENABLED
        if "scar_mode" in retrieval_params:
            scar_mode = bool(retrieval_params.get("scar_mode"))
        else:
            scar_mode = bool(getattr(dj_settings, "SCAR_ENABLED", False))
        if scar_mode:
            try:
                from apps.knowledge.models import Document

                has_compiled = Document.objects.filter(
                    knowledge_base_id=knowledge_base_id, compile_status="ok"
                ).exists()
            except Exception:
                has_compiled = False
            if has_compiled:
                ablation = (
                    retrieval_params.get("scar_ablation")
                    or getattr(dj_settings, "SCAR_ABLATION", "")
                    or ""
                )
                domain = (
                    retrieval_params.get("scar_domain")
                    or getattr(dj_settings, "SCAR_DEFAULT_DOMAIN", "construction")
                )
                ret, err = SkillRegistry.execute_safe(
                    "scar_retrieve",
                    session_id=session_id,
                    user=user,
                    query=question,
                    knowledge_base_id=knowledge_base_id,
                    top_k=top_k,
                    domain=domain,
                    ablation=ablation,
                )
                if not err and ret:
                    gen, gerr = SkillRegistry.execute_safe(
                        "scar_generate",
                        session_id=session_id,
                        user=user,
                        query=question,
                        evidence_pack=ret.get("evidence_pack") or {},
                    )
                    if not gerr and gen:
                        cites = gen.get("citations") or []
                        # 补文档标题，便于前端展示 file + path
                        title_by_id = {}
                        try:
                            from apps.knowledge.models import Document as DocModel

                            ids = [c.get("file_id") for c in cites if c.get("file_id")]
                            if ids:
                                title_by_id = {
                                    str(d.id): d.title
                                    for d in DocModel.objects.filter(id__in=ids).only("id", "title")
                                }
                        except Exception:
                            title_by_id = {}
                        citations = []
                        for c in cites:
                            fid = c.get("file_id")
                            citations.append(
                                {
                                    "file_id": fid,
                                    "file": title_by_id.get(str(fid) if fid else "", "") or str(fid or ""),
                                    "unit_id": c.get("unit_id"),
                                    "path": c.get("path"),
                                }
                            )
                        return {
                            "answer": gen.get("answer", ""),
                            "sources": [c.get("path") for c in citations if c.get("path")],
                            "citations": citations,
                            "skills_used": ["scar_retrieve", "scar_generate"],
                            "agent_name": self.agent.name,
                            "agent_id": self.agent.id,
                            "answer_source": "scar",
                            "context_docs": [],
                            "evidence_pack": ret.get("evidence_pack"),
                            "abstained": bool(gen.get("abstained")),
                        }

        # 1. 按 Agent 配置的 skills 依次执行（经 eligibility 过滤）
        for skill_id in eligible_skill_ids:
            if skill_id in RAG_LIKE_SKILLS:
                context_docs, _ = self.qa_service._retrieve_with_strategy(
                    question,
                    knowledge_base_id,
                    strategy=strategy,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    alpha=alpha,
                )
                log_skill_execution(
                    skill_id,
                    "success",
                    f"query={question[:100]}",
                    f"docs={len(context_docs)}",
                    session_id=session_id,
                    user=user,
                )
                skills_used.append(skill_id)
            elif skill_id == "cite_snippets":
                if context_docs:
                    result, err = SkillRegistry.execute_safe(
                        "cite_snippets",
                        session_id=session_id,
                        user=user,
                        documents=context_docs,
                        query=question,
                    )
                    if not err:
                        skills_used.append("cite_snippets")
            elif skill_id == "summarize" and context_docs:
                combined = "\n\n".join(getattr(d, "content", "")[:2000] for d in context_docs)
                result, err = SkillRegistry.execute_safe(
                    "summarize", session_id=session_id, user=user, text=combined
                )
                if not err and result.get("summary"):
                    supplemental_analysis_parts.append(
                        "检索内容摘要（供模型内部参考，不作为来源标题输出）：\n"
                        f"{result['summary']}"
                    )
                    skills_used.append("summarize")
            elif skill_id == "read_local_file":
                file_paths = retrieval_params.get("file_paths") or []
                for fp in file_paths:
                    if not fp:
                        continue
                    result, err = SkillRegistry.execute_safe(
                        "read_local_file", session_id=session_id, user=user, file_path=str(fp)
                    )
                    if not err and result.get("content"):
                        from types import SimpleNamespace
                        doc = SimpleNamespace(
                            title=f"[本地文件] {result.get('path', fp)}",
                            content=result["content"],
                            id=None,
                        )
                        context_docs.append(doc)
                        log_skill_execution(
                            "read_local_file", "success", f"path={fp[:80]}",
                            f"len={len(result.get('content', ''))}",
                            session_id=session_id, user=user,
                        )
                        skills_used.append("read_local_file")
                        break
            elif skill_id == "compare_docs" and len(context_docs) >= 2:
                result, err = SkillRegistry.execute_safe(
                    "compare_docs",
                    session_id=session_id,
                    user=user,
                    documents=context_docs[:5],
                    query=question,
                )
                if not err and result.get("comparison"):
                    supplemental_analysis_parts.append(
                        "文档对比要点（供模型内部参考，不作为来源标题输出）：\n"
                        f"{result['comparison']}"
                    )
                    skills_used.append("compare_docs")
            elif skill_id in PRO_ONLY_SKILL_IDS:
                result, err = SkillRegistry.execute_safe(
                    skill_id,
                    session_id=session_id,
                    user=user,
                    question=question,
                    knowledge_base_id=knowledge_base_id,
                )
                if not err and result and result.get("answer"):
                    skills_used.append(skill_id)
                    return {
                        "answer": result.get("answer"),
                        "sources": [],
                        "skills_used": skills_used,
                        "agent_name": self.agent.name,
                        "agent_id": self.agent.id,
                        "answer_source": skill_id,
                        "context_docs": [],
                    }

        # 2. 若仍无文档且尚未执行过任一检索类 Skill，则按配置补一次检索（避免与循环内重复）
        if not context_docs and not any(s in skills_used for s in RAG_LIKE_SKILLS):
            _rag_fallback = next(
                (s for s in eligible_skill_ids if s in RAG_LIKE_SKILLS),
                None,
            )
            if _rag_fallback:
                context_docs, _ = self.qa_service._retrieve_with_strategy(
                    question,
                    knowledge_base_id,
                    strategy=strategy,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    alpha=alpha,
                )
                if context_docs:
                    log_skill_execution(
                        _rag_fallback,
                        "success",
                        f"query={question[:100]}",
                        f"docs={len(context_docs)}",
                        session_id=session_id,
                        user=user,
                    )
                    skills_used.append(_rag_fallback)

        # 3. 生成答案（注入 Agent 可用 Skill 描述到 system prompt）
        use_general = not context_docs
        answer_question = question if not scene else f"[{scene}] {question}"
        answer = self.qa_service.generate_answer(
            answer_question,
            context_docs,
            use_general_knowledge=use_general,
            agent=self.agent,
            additional_context_text="\n\n".join(supplemental_analysis_parts),
        )

        sources = [d.title for d in context_docs]

        # 序列化 context_docs 为可 JSON 序列化的 dict 列表（避免 TypeError）
        def _doc_to_dict(d):
            return {
                "id": str(getattr(d, "id", "")) or None,
                "title": getattr(d, "title", ""),
                "content": (getattr(d, "content", "") or "")[:500],
            }

        return {
            "answer": answer,
            "sources": sources,
            "skills_used": skills_used,
            "agent_name": self.agent.name,
            "agent_id": self.agent.id,
            "answer_source": "general" if use_general else "rag",
            "context_docs": [_doc_to_dict(d) for d in context_docs],
        }
