import re
from typing import List, Dict, Any, Optional
from .models import QARecord
from apps.knowledge.models import Document
from apps.knowledge.vectorization_service import HybridRetrievalService
from apps.knowledge.retrieval_service import RetrievalStrategyManager
from .ai_services import AIServiceFactory, AIModel
from . import prompts as qa_prompts
from apps.skills.prompt_builder import build_skills_prompt, merge_base_system_with_agent
import os
import logging

logger = logging.getLogger(__name__)


def _merge_additional_into_user_prompt(user_content: str, additional_context_text: str) -> str:
    """无 RAG 上下文时仍将补充材料（如个人路线摘录）并入 user 侧，避免仅靠库检索路径才能注入。"""
    extra = (additional_context_text or "").strip()
    if not extra:
        return user_content
    return f"{user_content}\n\n【以下为仅供本题参考的补充材料】\n{extra}"


class SimpleRetrievalService:
    def search_documents(self, query: str, knowledge_base_id: str, top_k: int = 5) -> List[Document]:
        """简单的关键词检索"""
        # 提取关键词
        keywords = self.extract_keywords(query)
        
        # 检索相关文档
        documents = Document.objects.filter(
            knowledge_base_id=knowledge_base_id
        )
        
        # 简单的关键词匹配
        results = []
        for doc in documents:
            score = self.calculate_similarity(query, doc.content, keywords)
            if score > 0.05:  # 降低相似度阈值，确保能检索到更多文档
                results.append((doc, score))
        
        # 排序并返回top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in results[:top_k]]
    
    def extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 提取中文词汇和英文单词
        words = re.findall(r'[\u4e00-\u9fff\w]+', text)
        
        # 过滤停用词
        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这', '什么', '怎么', '如何', '为什么', '哪个', '哪些', '？', '？', '!', '。', '，', '、'}
        
        keywords = []
        for word in words:
            word = word.strip('？!。，、')
            if word not in stop_words and len(word) > 1:
                keywords.append(word)
                # 对于长词汇，也提取其中的子词汇
                if len(word) > 3:
                    for i in range(len(word) - 2):
                        subword = word[i:i+3]
                        if subword not in stop_words and len(subword) >= 2:
                            keywords.append(subword)
        
        return keywords
    
    def calculate_similarity(self, query: str, content: str, keywords: List[str]) -> float:
        """计算相似度"""
        if not content:
            return 0.0
        
        content_lower = content.lower()
        query_lower = query.lower()
        
        # 计算关键词匹配度
        keyword_matches = sum(1 for keyword in keywords if keyword in content_lower)
        keyword_score = keyword_matches / len(keywords) if keywords else 0
        
        # 计算直接匹配度
        direct_matches = sum(1 for word in query_lower.split() if word in content_lower)
        direct_score = direct_matches / len(query_lower.split()) if query_lower.split() else 0
        
        # 综合得分
        return (keyword_score * 0.7 + direct_score * 0.3)

class RAGRetrievalService:
    """RAG检索服务 - 使用向量检索"""
    
    def __init__(self):
        self.hybrid_retrieval = HybridRetrievalService()
    
    def search_documents(self, query: str, knowledge_base_id: str, top_k: int = 5) -> List[Document]:
        """
        使用混合检索搜索文档
        
        Args:
            query: 查询文本
            knowledge_base_id: 知识库ID
            top_k: 返回文档数量
            
        Returns:
            文档列表
        """
        try:
            # 使用混合检索服务
            results = self.hybrid_retrieval.search_documents(query, knowledge_base_id, top_k)
            
            # 返回文档对象列表
            return [doc for doc, score in results]
            
        except Exception as e:
            print(f"RAG检索失败: {e}")
            # 回退到简单检索
            simple_retrieval = SimpleRetrievalService()
            return simple_retrieval.search_documents(query, knowledge_base_id, top_k)

class QAService:
    def __init__(self, model: str = 'deepseek-chat'):
        self.retrieval = RAGRetrievalService()  # 回退用
        self.model = model
        self.ai_service = None
        self._init_ai_service()
    
    def _retrieve_with_strategy(
        self,
        question: str,
        knowledge_base_id: str,
        strategy: str = 'hybrid',
        top_k: int = 5,
        score_threshold: float = 0.15,
        alpha: float = 0.5,
    ) -> tuple:
        """使用高级检索策略获取文档列表及最高分。返回 (documents, max_score)，失败时回退到 RAGRetrievalService 并返回 (docs, 0.5)。"""
        try:
            manager = RetrievalStrategyManager()
            result = manager.execute_strategy(
                strategy_name=strategy,
                query=question,
                knowledge_base_id=knowledge_base_id,
                custom_params={
                    'top_k': top_k,
                    'score_threshold': score_threshold,
                    'alpha': alpha,
                    'enable_deduplication': True,
                },
            )
            evidence = result.get('evidence') or []
            if not evidence:
                fallback = self.retrieval.search_documents(question, knowledge_base_id, top_k)
                return (fallback, 0.0)
            max_score = max((e.get('score', 0) for e in evidence), default=0.0)
            doc_ids = []
            for e in evidence:
                sid = (e.get('source') or {}).get('document_id')
                if sid:
                    doc_ids.append(sid)
            if not doc_ids:
                fallback = self.retrieval.search_documents(question, knowledge_base_id, top_k)
                return (fallback, 0.0)
            docs = list(Document.objects.filter(id__in=doc_ids))
            doc_by_id = {str(d.id): d for d in docs}
            ordered = [doc_by_id[did] for did in doc_ids if did in doc_by_id]
            return (ordered, max_score)
        except Exception as e:
            logger.warning("高级检索失败，回退到混合检索: %s", e)
            fallback = self.retrieval.search_documents(question, knowledge_base_id, top_k)
            return (fallback, 0.0)
    
    def _init_ai_service(self):
        """初始化 AI 服务：优先使用后端配置（环境变量 / settings），其次使用管理员在界面保存的配置。"""
        provider_key = self._get_provider_key(self.model)
        api_key = None
        
        # 1）后端内置：Django 设置（来自 settings 的 AI_ENGINE_CONFIG，一般由 .env 填充）
        from django.conf import settings
        ai_config = getattr(settings, 'AI_ENGINE_CONFIG', {})
        api_key = (ai_config.get(provider_key) or {}).get('api_key')
        
        # 2）环境变量
        if not api_key or not str(api_key).strip():
            api_key = os.getenv(f'{provider_key.upper()}_API_KEY')
        
        # 3）管理员在「AI配置」页保存的配置（数据库）
        if not api_key or not str(api_key).strip():
            try:
                from apps.system.models import APIKeyConfig
                cfg = APIKeyConfig.objects.filter(provider=provider_key, is_active=True).first()
                if cfg and getattr(cfg, 'api_key', None):
                    api_key = cfg.api_key
            except Exception:
                pass
        
        if api_key and str(api_key).strip():
            self.ai_service = AIServiceFactory.create_service(self.model, api_key.strip())
        else:
            logger.warning("未找到 AI API 密钥：请在 backend/.env 中配置 %s_API_KEY，或由管理员在「AI配置」页保存", provider_key.upper())
    
    def _get_provider_key(self, model: str) -> str:
        """根据模型名称获取提供商Key"""
        if model.startswith('deepseek'):
            return 'deepseek'
        elif model.startswith('qwen'):
            return 'qwen'
        elif model.startswith('glm') or model.startswith('cogview'):
            return 'glm'
        else:
            return 'deepseek'  # 默认

    def _sanitize_answer_text(self, answer: str) -> str:
        """兜底清洗：移除后端中间态来源字样，避免前端出现伪来源。"""
        if not answer:
            return answer
        sanitized = answer
        forbidden_aliases = [
            "《检索摘要》",
            "[检索摘要]",
            "【检索摘要】",
            "《文档对比分析》",
            "[文档对比分析]",
            "【文档对比分析】",
        ]
        for marker in forbidden_aliases:
            sanitized = sanitized.replace(marker, "相关文档")
        return sanitized
    
    def ask_question(
        self,
        question: str,
        knowledge_base_id: str,
        user,
        retrieval_params: Optional[Dict[str, Any]] = None,
        auxiliary_knowledge_base_ids: Optional[List[str]] = None,
        scene: Optional[str] = None,
    ) -> Dict[str, Any]:
        """处理问答请求。scene 可选：用于区分通用问答、CET 等不同场景。"""
        strategy = 'hybrid'
        top_k = 5
        score_threshold = 0.15
        alpha = 0.5
        if retrieval_params:
            strategy = retrieval_params.get('strategy', strategy)
            top_k = retrieval_params.get('top_k', top_k)
            score_threshold = retrieval_params.get('score_threshold', score_threshold)
            alpha = retrieval_params.get('alpha', alpha)
        
        if auxiliary_knowledge_base_ids:
            context_docs, max_score = self._retrieve_multi_kb(
                question,
                knowledge_base_id,
                auxiliary_knowledge_base_ids,
                user,
                strategy=strategy,
                top_k=top_k,
                score_threshold=score_threshold,
                alpha=alpha,
            )
        else:
            context_docs, max_score = self._retrieve_with_strategy(
                question,
                knowledge_base_id,
                strategy=strategy,
                top_k=top_k,
                score_threshold=score_threshold,
                alpha=alpha,
            )
        
        # 只在完全没有检索到文档时，才视为常规问题（用 AI 通用知识兜底）；
        # 只要有文档，就一律按知识库回答（不再因为分数低而走纯 AI 回答）。
        use_general = not context_docs

        # 预留按场景定制回答的扩展点（当前实现仍调用通用 generate_answer）
        # 后续可根据 scene == "cet" 时，增加对四级/六级题目、解析、学习建议的专用 Prompt。
        answer_question = question if not scene else f"[{scene}] {question}"
        answer = self.generate_answer(
            answer_question,
            context_docs,
            use_general_knowledge=use_general,
        )
        
        qa_record = QARecord.objects.create(
            user=user,
            question=question,
            answer=answer,
            knowledge_sources=[str(doc.id) for doc in context_docs],
            confidence_score=0.8
        )
        
        return {
            'answer': answer,
            'sources': [doc.title for doc in context_docs],
            'qa_id': str(qa_record.id),
            'model': self.model,
            'answer_source': 'general' if use_general else 'rag',
            'max_score': round(max_score, 4) if context_docs else None,
        }
    
    def _retrieve_multi_kb(
        self,
        question: str,
        main_kb_id: str,
        auxiliary_kb_ids: List[str],
        user,
        strategy: str = 'hybrid',
        top_k: int = 5,
        score_threshold: float = 0.15,
        alpha: float = 0.5,
    ) -> List[Document]:
        """多知识库检索：主库 + 辅助库分别检索后按分数合并、去重，返回有序 Document 列表。"""
        from apps.knowledge.models import KnowledgeBase
        all_evidence = []
        main_per_k = max(3, top_k - len(auxiliary_kb_ids) * 2)
        aux_per_k = 2
        # 主库
        try:
            manager = RetrievalStrategyManager()
            res = manager.execute_strategy(
                strategy_name=strategy,
                query=question,
                knowledge_base_id=main_kb_id,
                custom_params={
                    'top_k': main_per_k,
                    'score_threshold': score_threshold,
                    'alpha': alpha,
                    'enable_deduplication': True,
                },
            )
            for e in (res.get('evidence') or []):
                e['_kb_id'] = main_kb_id
                all_evidence.append(e)
        except Exception as e:
            logger.warning("主知识库检索失败: %s", e)
        # 辅助库（仅检索用户有权限的）
        try:
            allowed = set(
                KnowledgeBase.objects.filter(owner=user, id__in=auxiliary_kb_ids).values_list('id', flat=True)
            )
            for kb_id in auxiliary_kb_ids:
                if str(kb_id) not in allowed:
                    continue
                res = manager.execute_strategy(
                    strategy_name=strategy,
                    query=question,
                    knowledge_base_id=str(kb_id),
                    custom_params={
                        'top_k': aux_per_k,
                        'score_threshold': score_threshold,
                        'alpha': alpha,
                        'enable_deduplication': True,
                    },
                )
                for e in (res.get('evidence') or []):
                    e['_kb_id'] = str(kb_id)
                    all_evidence.append(e)
        except Exception as e:
            logger.warning("辅助知识库检索失败: %s", e)
        if not all_evidence:
            fallback = self.retrieval.search_documents(question, main_kb_id, top_k)
            return (fallback, 0.0)
        all_evidence.sort(key=lambda x: x.get('score', 0), reverse=True)
        max_score = all_evidence[0].get('score', 0.0) if all_evidence else 0.0
        seen = set()
        doc_ids = []
        for e in all_evidence:
            sid = (e.get('source') or {}).get('document_id')
            if sid and sid not in seen:
                seen.add(sid)
                doc_ids.append(sid)
            if len(doc_ids) >= top_k:
                break
        if not doc_ids:
            fallback = self.retrieval.search_documents(question, main_kb_id, top_k)
            return (fallback, 0.0)
        docs = list(Document.objects.filter(id__in=doc_ids))
        doc_by_id = {str(d.id): d for d in docs}
        ordered = [doc_by_id[did] for did in doc_ids if did in doc_by_id]
        return (ordered, max_score)
    
    def generate_answer(
        self,
        question: str,
        context_docs: List[Document],
        use_general_knowledge: bool = False,
        agent=None,
        additional_context_text: str = "",
    ) -> str:
        """生成答案。use_general_knowledge=True 时视为常规问题，用 AI 自身知识回答（不依赖本地库）。
        agent 可选：传入时将可用 Skill 描述注入 system prompt。"""
        # 检查是否是问候语或非技术性问题
        greeting_patterns = ['你好', 'hello', 'hi', '您好', '早上好', '下午好', '晚上好', '谢谢', '再见', '拜拜']
        is_greeting = any(pattern in question.lower() for pattern in greeting_patterns)
        
        if is_greeting:
            if self.ai_service:
                system_prompt, user_content = qa_prompts.get_greeting_prompts(question)
                system_prompt = merge_base_system_with_agent(system_prompt, agent)
                if agent:
                    system_prompt = system_prompt + build_skills_prompt(agent)
                messages = self.ai_service.format_messages(system_prompt, user_content)
                return self._sanitize_answer_text(self.ai_service.generate_response(messages))
            else:
                return """你好！我是智能知识库问答助手。

我可以基于你上传的文档进行问答。请上传相关文档到知识库，我就能基于知识库内容给出更精准的答案。有什么想了解的吗？"""
        
        if not context_docs:
            if use_general_knowledge and self.ai_service:
                system_prompt, user_content = qa_prompts.get_general_knowledge_prompts(question)
                user_content = _merge_additional_into_user_prompt(user_content, additional_context_text)
                system_prompt = merge_base_system_with_agent(system_prompt, agent)
                if agent:
                    system_prompt = system_prompt + build_skills_prompt(agent)
                messages = self.ai_service.format_messages(system_prompt, user_content)
                return self._sanitize_answer_text(self.ai_service.generate_response(messages))
            if self.ai_service:
                system_prompt, user_content = qa_prompts.get_no_context_prompts(question)
                user_content = _merge_additional_into_user_prompt(user_content, additional_context_text)
                system_prompt = merge_base_system_with_agent(system_prompt, agent)
                if agent:
                    system_prompt = system_prompt + build_skills_prompt(agent)
                messages = self.ai_service.format_messages(system_prompt, user_content)
                return self._sanitize_answer_text(self.ai_service.generate_response(messages))
            else:
                return self._sanitize_answer_text(f"""抱歉，当前知识库中未找到与「{question}」相关的文档。

建议：1）检查是否已上传相关文档；2）用更具体的关键词提问。"""
)
        
        # 库内无强相关索引（由调用方判定）→ 用 AI 自身知识回答，不使用检索到的弱相关内容
        if use_general_knowledge and self.ai_service:
            system_prompt, user_content = qa_prompts.get_general_knowledge_prompts(question)
            user_content = _merge_additional_into_user_prompt(user_content, additional_context_text)
            system_prompt = merge_base_system_with_agent(system_prompt, agent)
            if agent:
                system_prompt = system_prompt + build_skills_prompt(agent)
            messages = self.ai_service.format_messages(system_prompt, user_content)
            return self._sanitize_answer_text(self.ai_service.generate_response(messages))
        if use_general_knowledge:
            # 常规问题但未配置 AI：API 密钥由平台统一配置，客户无需操作
            return "AI 服务暂时不可用，请稍后再试或联系管理员。"
        
        # 以下为 RAG 路径：有强相关检索结果且走知识库回答
        def _context_block(doc: Document) -> str:
            content = (doc.content or "").strip()
            cap = 500
            if len(content) <= cap:
                return f"文档：{doc.title}\n内容：{content}"
            return f"文档：{doc.title}\n内容：{content[:cap]}..."
        context = "\n\n".join(_context_block(doc) for doc in context_docs)
        if additional_context_text and additional_context_text.strip():
            context = f"{context}\n\n辅助分析：\n{additional_context_text.strip()}"
        
        if self.ai_service:
            q_lower = (question or "").lower()
            is_summary_intent = any(
                k in q_lower for k in ["生成总结", "总结", "摘要", "总览"]
            )
            if is_summary_intent:
                system_prompt, user_content = qa_prompts.get_rag_summary_prompts(question, context)
            else:
                system_prompt, user_content = qa_prompts.get_rag_prompts(question, context)
            system_prompt = merge_base_system_with_agent(system_prompt, agent)
            if agent:
                system_prompt = system_prompt + build_skills_prompt(agent)
            messages = self.ai_service.format_messages(system_prompt, user_content)
            return self._sanitize_answer_text(self.ai_service.generate_response(messages))
        else:
            # 回退到简单答案生成
            return self._sanitize_answer_text(f"""基于知识库中的信息，我为您找到以下相关内容：

{context}

根据以上信息，您可以参考相关文档来回答您的问题："{question}"

如果您需要更详细的回答，建议您查看完整的文档内容。"""
)
