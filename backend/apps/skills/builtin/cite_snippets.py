from typing import List, Any


def execute(
    documents: List[Any],
    query: str = "",
    max_snippets: int = 5,
    **kwargs) -> dict:
    """
    引用生成 Skill：从文档中提取可引用片段
    输入：documents 列表（来自 rag_answer 或类似）
    输出：带出处的引用片段列表
    """
    snippets = []
    for doc in (documents or [])[:max_snippets]:
        content = getattr(doc, "content", "") or ""
        title = getattr(doc, "title", "未知文档")
        doc_id = str(getattr(doc, "id", ""))
        if content:
            head = content[:300].strip()
            if len(content) > 300:
                head += "..."
            snippets.append({
                "title": title,
                "document_id": doc_id,
                "snippet": head,
            })
    return {
        "snippets": snippets,
        "count": len(snippets),
    }
