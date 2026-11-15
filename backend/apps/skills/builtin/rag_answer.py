from typing import List, Any
from apps.knowledge.models import Document
from apps.knowledge.vectorization_service import HybridRetrievalService


def execute(
    query: str,
    knowledge_base_id: str,
    top_k: int = 5,
    strategy: str = "hybrid",
    **kwargs) -> dict:
    """
    知识库检索 Skill：使用混合检索返回相关文档
    """
    retrieval = HybridRetrievalService()
    results = retrieval.search_documents(query, knowledge_base_id, top_k)
    docs: List[Document] = [doc for doc, _ in results]
    return {
        "documents": docs,
        "count": len(docs),
        "titles": [d.title for d in docs],
    }
