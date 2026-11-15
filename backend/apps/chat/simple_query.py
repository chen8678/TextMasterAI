"""
简单的FastGPT式查询接口 - 支持 Agent 编排
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .services import QAService
from .agent_service import AgentOrchestrator
from apps.knowledge.models import KnowledgeBase


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def simple_query(request):
    """
    简单的知识库查询接口
    
    请求格式：
    {
        "question": "根据知识库内容，总结关键要点。",
        "knowledge_base_id": "知识库ID（可选）",
        "agent_id": "qa（可选）",
        "use_agent": true（可选，默认 true）
    }
    
    返回格式：
    {
        "answer": "专业答案...",
        "sources": ["文档1", "文档2"],
        "from_private_kb": true,
        "question": "用户问题",
        "skills_used": ["rag_answer", "cite_snippets"],
        "agent_name": "知识问答助手",
        "agent_id": "qa"
    }
    """
    question = request.data.get('question', '').strip()
    agent_id = request.data.get('agent_id', 'qa')
    use_agent = request.data.get('use_agent', True)
    
    if not question:
        return Response(
            {'error': '请提供问题'},
            status=status.HTTP_400_BAD_REQUEST
        )

    from apps.system.content_safety.guards import require_safe_user_text, apply_output_safety

    blocked = require_safe_user_text(request, question, channel="chat_simple")
    if blocked is not None:
        return blocked
    
    # 获取知识库ID（如果提供）
    knowledge_base_id = request.data.get('knowledge_base_id')
    
    # 如果没有提供知识库ID，使用用户的第一个知识库
    if not knowledge_base_id:
        user_kb = KnowledgeBase.objects.filter(owner=request.user).first()
        if not user_kb:
            return Response(
                {'error': '请先创建知识库并上传文档'},
                status=status.HTTP_400_BAD_REQUEST
            )
        knowledge_base_id = str(user_kb.id)
    else:
        knowledge_base_id = str(knowledge_base_id)
    
    try:
        payload = None
        if use_agent:
            try:
                orchestrator = AgentOrchestrator(agent_id=agent_id)
                result = orchestrator.process(
                    question,
                    knowledge_base_id,
                    request.user,
                )
                payload = {
                    'answer': result.get('answer', ''),
                    'sources': result.get('sources', []),
                    'from_private_kb': True,
                    'question': question,
                    'skills_used': result.get('skills_used', []),
                    'agent_name': result.get('agent_name', ''),
                    'agent_id': result.get('agent_id', ''),
                }
            except Exception:
                use_agent = False
        
        if payload is None:
            qa_service = QAService(model='deepseek-chat')
            result = qa_service.ask_question(
                question=question,
                knowledge_base_id=knowledge_base_id,
                user=request.user
            )
            payload = {
                'answer': result.get('answer', ''),
                'sources': result.get('sources', []),
                'from_private_kb': True,
                'question': question,
                'skills_used': result.get('skills_used', []),
                'agent_name': result.get('agent_name', ''),
                'agent_id': result.get('agent_id', ''),
            }
        payload = apply_output_safety(
            payload,
            channel="chat_simple",
            user=request.user,
            request=request,
        )
        return Response(payload)
        
    except Exception as e:
        return Response(
            {'error': f'查询失败: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

