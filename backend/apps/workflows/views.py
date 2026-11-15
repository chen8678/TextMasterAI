"""
工作流 API - 供系统调用
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import GeneratedContent, CONTENT_TYPE_DISPLAY
from .content_generation_workflow import run_content_generation_workflow
from .kb_qa_collector_workflow import run_kb_qa_collector_workflow, DEFAULT_INSTRUCTION
from .kb_collector_personas import list_personas


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def run_content_generation(request):
    """
    执行大模型驱动的内容生成工作流（系统可调用）
    
    请求体：
    {
        "knowledge_base_id": "uuid",
        "content_types": ["summary", "outline", "key_concepts", "q_and_a"],
        "ai_model": "deepseek",
        "config": {"max_tokens": 2000, "temperature": 0.7}
    }
    """
    kb_id = request.data.get('knowledge_base_id')
    content_types = request.data.get('content_types', [])
    ai_model = request.data.get('ai_model', 'deepseek')
    config = request.data.get('config', {})

    if not kb_id:
        return Response({'error': '缺少 knowledge_base_id'}, status=status.HTTP_400_BAD_REQUEST)
    if not content_types:
        return Response({'error': '请选择至少一种内容类型'}, status=status.HTTP_400_BAD_REQUEST)

    from apps.knowledge.models import KnowledgeBase
    kb = KnowledgeBase.objects.filter(id=kb_id, owner=request.user).first()
    if not kb:
        return Response({'error': '知识库不存在或无权访问'}, status=status.HTTP_404_NOT_FOUND)

    result = run_content_generation_workflow(
        knowledge_base_id=str(kb_id),
        content_types=content_types,
        ai_model=ai_model,
        config=config,
        user=request.user,
    )

    if result['success']:
        return Response({
            'message': '内容生成完成',
            'total_generated': result['total_generated'],
            'generated_contents': result['generated_contents'],
        }, status=status.HTTP_201_CREATED)
    return Response({
        'error': result.get('error', '生成失败'),
        'total_generated': result.get('total_generated', 0),
        'generated_contents': result.get('generated_contents', []),
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_generated_content(request, knowledge_base_id):
    """获取某知识库的已生成内容"""
    from apps.knowledge.models import KnowledgeBase
    kb = get_object_or_404(KnowledgeBase, id=knowledge_base_id, owner=request.user)
    items = GeneratedContent.objects.filter(knowledge_base=kb).order_by('-created_at')
    contents = []
    seen = set()
    for item in items:
        if item.content_type in seen:
            continue
        seen.add(item.content_type)
        contents.append({
            'id': str(item.id),
            'content_type': item.content_type,
            'content_type_display': CONTENT_TYPE_DISPLAY.get(item.content_type, item.content_type),
            'content_data': item.content_data,
            'created_at': item.created_at.isoformat(),
        })
    return Response({'contents': contents})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_models(request):
    """获取可用于内容生成的 AI 模型列表（兼容前端）"""
    from ai_qa_system.ai_config import AIConfig
    result = {}
    for p in AIConfig.get_providers():
        pkey = p.get('key', '')
        for m in AIConfig.get_provider_models(pkey):
            key = m.get('key', '')
            result[key] = {
                'id': key,
                'name': m.get('name', ''),
                'description': m.get('version', ''),
                'max_tokens': 2000,
                'supported_types': ['summary', 'outline', 'key_concepts', 'q_and_a'],
                'available': p.get('available', True),
            }
        if pkey and pkey not in result:
            result[pkey] = {
                'id': pkey,
                'name': p.get('name', pkey),
                'description': '',
                'max_tokens': 2000,
                'supported_types': ['summary', 'outline', 'key_concepts', 'q_and_a'],
                'available': p.get('available', True),
            }
    if not result:
        for item in [
            {'id': 'deepseek', 'name': 'DeepSeek', 'description': '深度求索'},
            {'id': 'qwen', 'name': '通义千问', 'description': '阿里云'},
            {'id': 'glm', 'name': '智谱AI', 'description': '清华智谱'},
        ]:
            result[item['id']] = {**item, 'max_tokens': 2000, 'supported_types': [], 'available': True}
    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def run_kb_qa_collector(request):
    """
    执行 KB 问答采集工作流：模拟用户提问 → 走 KB 编排 → 导出训练 JSON。

    请求体示例：
    {
        "knowledge_base_id": "uuid",
        "questions": ["问题1", "问题2"],
        "question_source": "inline",
        "seed_path": "",
        "llm_question_count": 0,
        "agent_id": "qa",
        "ai_model": "deepseek",
        "config": {"max_tokens": 2000},
        "retrieval_params": {"strategy": "hybrid", "top_k": 5},
        "instruction": "可选 SFT instruction",
        "delay_seconds": 0.5,
        "max_questions": 50,
        "output_path": "",
        "dry_run": false
    }

    question_source 可选：inline | seed_file | llm_from_kb
    """
    kb_id = request.data.get('knowledge_base_id')
    if not kb_id:
        return Response({'error': '缺少 knowledge_base_id'}, status=status.HTTP_400_BAD_REQUEST)

    from apps.knowledge.models import KnowledgeBase
    from apps.knowledge.views import _has_kb_access

    kb = KnowledgeBase.objects.filter(id=kb_id).first()
    if not kb or not _has_kb_access(request.user, kb, min_role='viewer'):
        return Response({'error': '知识库不存在或无权访问'}, status=status.HTTP_404_NOT_FOUND)

    result = run_kb_qa_collector_workflow(
        knowledge_base_id=str(kb_id),
        user=request.user,
        questions=request.data.get('questions'),
        question_source=request.data.get('question_source', 'inline'),
        seed_path=request.data.get('seed_path', ''),
        llm_question_count=int(request.data.get('llm_question_count') or 0),
        agent_id=request.data.get('agent_id', 'qa'),
        ai_model=request.data.get('ai_model', 'deepseek'),
        config=request.data.get('config') or {},
        retrieval_params=request.data.get('retrieval_params'),
        instruction=request.data.get('instruction') or DEFAULT_INSTRUCTION,
        delay_seconds=float(request.data.get('delay_seconds', 0.5)),
        max_questions=int(request.data.get('max_questions', 50)),
        output_path=request.data.get('output_path', ''),
        dry_run=bool(request.data.get('dry_run', False)),
        persona_id=request.data.get('persona_id', ''),
        auto_use_persona=not bool(request.data.get('no_persona', False)),
    )

    if result.get('success'):
        return Response({
            'message': '问答采集完成',
            'run_id': result.get('run_id'),
            'persona_id': result.get('persona_id'),
            'role_name': result.get('role_name'),
            'total_questions': result.get('total_questions'),
            'total_collected': result.get('total_collected'),
            'total_errors': result.get('total_errors'),
            'question_source': result.get('question_source'),
            'output_path': result.get('output_path'),
            'jsonl_path': result.get('jsonl_path'),
            'errors': result.get('errors', []),
        }, status=status.HTTP_201_CREATED)

    return Response({
        'error': result.get('error', '采集失败'),
        'run_id': result.get('run_id'),
        'total_collected': result.get('total_collected', 0),
        'errors': result.get('errors', []),
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kb_qa_collector_personas(request):
    """列出 KB 问答采集器已注册的提问角色。"""
    return Response({'personas': list_personas()})
