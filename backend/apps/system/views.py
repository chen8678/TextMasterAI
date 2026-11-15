"""
系统管理视图
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from .models import AIModelConfig, SystemSetting, APILog
from .models import AnalyticsEvent
from .monitoring import snapshot as monitor_snapshot
from .serializers import (
    AIModelConfigSerializer, AIModelConfigCreateSerializer,
    SystemSettingSerializer, APILogSerializer,
    AIModelTestSerializer
)
try:
    from ..learning.ai_engines.engine_factory import get_ai_engine_factory
except ImportError:
    get_ai_engine_factory = None
import logging

logger = logging.getLogger(__name__)
ALLOWED_ANALYTICS_EVENTS = {
    "chat_feedback",
    "chat_feedback_like",
    "chat_feedback_dislike",
    "ab_variant_exposed",
}


def _safe_queue_length() -> int:
    """优先读取 Redis 队列长度；不可用时退化为 pending staging 总量。"""
    broker = str(getattr(settings, "CELERY_BROKER_URL", "") or "")
    queue_name = str(getattr(settings, "CELERY_PRO_SANDBOX_QUEUE", "pro_sandbox") or "pro_sandbox")
    if broker.startswith("redis://"):
        try:
            from urllib.parse import urlparse
            import redis

            p = urlparse(broker)
            db = int((p.path or "/0").lstrip("/") or "0")
            client = redis.Redis(
                host=p.hostname or "127.0.0.1",
                port=int(p.port or 6379),
                password=p.password,
                db=db,
                socket_timeout=1.0,
            )
            return int(client.llen(queue_name))
        except Exception:
            pass
    try:
        from apps.skills.models import SkillEvolutionStaging

        return int(SkillEvolutionStaging.objects.filter(status="pending").count())
    except Exception:
        return 0


# AI模型配置管理
@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def ai_model_config_list(request):
    """获取或创建AI模型配置"""
    if request.method == 'GET':
        configs = AIModelConfig.objects.all().order_by('-created_at')
        serializer = AIModelConfigSerializer(configs, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = AIModelConfigCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAdminUser])
def ai_model_config_detail(request, pk):
    """获取、更新或删除AI模型配置"""
    config = get_object_or_404(AIModelConfig, pk=pk)
    
    if request.method == 'GET':
        serializer = AIModelConfigSerializer(config)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = AIModelConfigSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        config.delete()
        return Response({'message': 'AI模型配置已删除'}, status=status.HTTP_204_NO_CONTENT)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def test_ai_model(request, pk):
    """测试AI模型连接"""
    config = get_object_or_404(AIModelConfig, pk=pk)
    
    try:
        # 测试连接
        config.test_connection()
        
        serializer = AIModelConfigSerializer(config)
        return Response({
            'message': '测试完成',
            'config': serializer.data,
            'is_available': config.is_available,
            'error_message': config.error_message
        })
        
    except Exception as e:
        logger.error(f"测试AI模型失败: {str(e)}")
        return Response({
            'error': f'测试失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def test_ai_generation(request):
    """测试AI内容生成"""
    serializer = AIModelTestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    data = serializer.validated_data
    
    try:
        if get_ai_engine_factory is None:
            return Response({'error': '学习模块未安装，无法测试内容生成'}, status=status.HTTP_400_BAD_REQUEST)
        # 获取AI引擎
        factory = get_ai_engine_factory()
        engine = factory.get_engine(data['model_id'])
        
        if not engine:
            return Response({
                'error': f'无法获取AI模型: {data["model_id"]}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 测试生成
        import asyncio
        result = asyncio.run(engine.generate_content(
            prompt=data['test_content'],
            content_type=data['content_type'],
            config={'max_tokens': 500, 'temperature': 0.7}
        ))
        
        return Response({
            'message': '测试生成成功',
            'result': result
        })
        
    except Exception as e:
        logger.error(f"测试AI生成失败: {str(e)}")
        return Response({
            'error': f'测试生成失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 系统设置管理
@api_view(['GET', 'POST'])
@permission_classes([IsAdminUser])
def system_settings_list(request):
    """获取或创建系统设置"""
    if request.method == 'GET':
        settings = SystemSetting.objects.all().order_by('setting_type', 'key')
        serializer = SystemSettingSerializer(settings, many=True)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = SystemSettingSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAdminUser])
def system_setting_detail(request, pk):
    """获取、更新或删除系统设置"""
    setting = get_object_or_404(SystemSetting, pk=pk)
    
    if request.method == 'GET':
        serializer = SystemSettingSerializer(setting)
        return Response(serializer.data)
    
    elif request.method == 'PUT':
        serializer = SystemSettingSerializer(setting, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        setting.delete()
        return Response({'message': '系统设置已删除'}, status=status.HTTP_204_NO_CONTENT)


# API日志管理
@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_logs_list(request):
    """获取API日志列表（支持 limit，默认 100，最大 500）"""
    try:
        limit = int(request.GET.get('limit', 100))
    except (TypeError, ValueError):
        limit = 100
    limit = min(max(limit, 1), 500)
    logs = APILog.objects.all().order_by('-created_at')[:limit]
    serializer = APILogSerializer(logs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_logs_trend(request):
    """按日聚合 API 调用量与错误量，供趋势图使用"""
    try:
        days = int(request.GET.get('days', 14))
    except (TypeError, ValueError):
        days = 14
    days = min(max(days, 1), 90)

    end_time = timezone.now()
    start_time = end_time - timedelta(days=days - 1)
    start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)

    rows = (
        APILog.objects.filter(created_at__gte=start_time)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(
            total=Count('id'),
            errors=Count('id', filter=Q(status_code__gte=400)),
        )
        .order_by('day')
    )
    row_map = {}
    for r in rows:
        d = r['day']
        if hasattr(d, 'date'):
            d = d.date()
        row_map[d] = r

    labels = []
    total_calls = []
    error_calls = []
    d = start_time.date()
    end_d = end_time.date()
    while d <= end_d:
        labels.append(d.strftime('%m-%d'))
        rec = row_map.get(d)
        total_calls.append(rec['total'] if rec else 0)
        error_calls.append(rec['errors'] if rec else 0)
        d += timedelta(days=1)

    return Response({
        'days': days,
        'labels': labels,
        'total_calls': total_calls,
        'error_calls': error_calls,
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_logs_stats(request):
    """获取API日志统计"""
    # 时间范围
    end_time = timezone.now()
    start_time = end_time - timedelta(days=7)  # 最近7天
    
    # 基础统计
    total_calls = APILog.objects.filter(created_at__gte=start_time).count()
    error_calls = APILog.objects.filter(
        created_at__gte=start_time,
        status_code__gte=400
    ).count()
    
    # 计算错误率
    error_rate = (error_calls / total_calls * 100) if total_calls > 0 else 0
    
    # 平均响应时间
    avg_response_time = APILog.objects.filter(
        created_at__gte=start_time
    ).aggregate(avg_duration=Avg('duration'))['avg_duration'] or 0
    
    # 总 token（Sum，非条数）
    total_tokens = APILog.objects.filter(
        created_at__gte=start_time
    ).aggregate(total=Sum('tokens_used'))['total'] or 0

    # 最近错误
    recent_errors = APILog.objects.filter(
        created_at__gte=start_time,
        status_code__gte=400
    ).order_by('-created_at')[:10]

    recent_errors_data = []
    for log in recent_errors:
        req = log.request_data if isinstance(log.request_data, dict) else {}
        recent_errors_data.append({
            'id': str(log.id),
            'log_type': log.get_log_type_display(),
            'model_id': log.model_id,
            'path': req.get('path', ''),
            'error_message': log.error_message,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    return Response({
        'total_api_calls': total_calls,
        'error_rate': round(error_rate, 2),
        'avg_response_time': round(float(avg_response_time or 0), 2),
        'total_tokens_used': int(total_tokens),
        'recent_errors': recent_errors_data
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def monitor_overview(request):
    """P3-T30：统一监控快照（错误率、延迟、沙盒队列长度）。"""
    runtime = monitor_snapshot()
    return Response({
        "runtime": runtime,
        "pro_sandbox_queue_length": _safe_queue_length(),
        "trace_header": "X-Trace-Id",
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def api_logs_trace_lookup(request):
    """按 trace_id 快速查询日志链路。"""
    trace_id = str(request.GET.get("trace_id", "")).strip()
    if not trace_id:
        return Response({"error": "trace_id 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
    rows = (
        APILog.objects.filter(request_data__trace_id=trace_id)
        .order_by('-created_at')[:200]
    )
    serializer = APILogSerializer(rows, many=True)
    return Response({"trace_id": trace_id, "items": serializer.data})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics_config(request):
    """前端读取埋点开关。"""
    return Response({
        "enabled": bool(getattr(settings, "ANALYTICS_ENABLED", False)),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def analytics_track(request):
    """P3-T31：埋点事件写入。"""
    if not bool(getattr(settings, "ANALYTICS_ENABLED", False)):
        return Response({"ok": True, "skipped": "disabled"})

    event_name = str(request.data.get('event_name') or '').strip()
    if event_name not in ALLOWED_ANALYTICS_EVENTS:
        return Response({"error": "event_name 不在白名单"}, status=status.HTTP_400_BAD_REQUEST)
    payload = request.data.get('payload') or {}
    if not isinstance(payload, dict):
        payload = {"value": str(payload)}
    raw_sid = request.data.get('session_id')
    session_id = None
    if raw_sid:
        try:
            import uuid as _uuid
            session_id = _uuid.UUID(str(raw_sid))
        except Exception:
            session_id = None
    trace_id = str(getattr(request, "trace_id", "") or request.headers.get("X-Trace-Id") or "")[:64]

    row = AnalyticsEvent.objects.create(
        event_name=event_name,
        user=request.user if getattr(request.user, "is_authenticated", False) else None,
        session_id=session_id,
        trace_id=trace_id,
        payload=payload,
    )
    return Response({"ok": True, "event_id": str(row.id)})


@api_view(['GET'])
@permission_classes([IsAdminUser])
def analytics_stats(request):
    """埋点统计（最近 7 天）。"""
    end_time = timezone.now()
    start_time = end_time - timedelta(days=7)
    rows = (
        AnalyticsEvent.objects.filter(created_at__gte=start_time)
        .values('event_name')
        .annotate(total=Count('id'))
        .order_by('event_name')
    )
    return Response({
        "days": 7,
        "items": list(rows),
    })


# 系统统计
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def system_stats(request):
    """获取系统统计信息"""
    from apps.knowledge.models import KnowledgeBase, Document
    from apps.chat.models import QARecord
    from django.contrib.auth import get_user_model
    try:
        from apps.learning.models import Course
        total_courses = Course.objects.count()
    except ImportError:
        total_courses = 0
    
    User = get_user_model()

    # 基础统计（管理台展示）
    total_documents = Document.objects.count()
    total_questions = QARecord.objects.filter(message_type='user').count()
    total_users = User.objects.count()
    total_knowledge_bases = KnowledgeBase.objects.count()

    # Agent 调用：助手回复且记录了非空 agent_id 的次数
    agent_invocations = QARecord.objects.filter(
        message_type='assistant',
        agent_id__isnull=False,
    ).exclude(agent_id='').count()

    # Skill 调用：优先执行日志表；若无记录则从问答里 skills_used 列表长度汇总
    try:
        from apps.skills.models import SkillExecutionLog
        skill_invocations = SkillExecutionLog.objects.count()
    except ImportError:
        skill_invocations = 0
    if skill_invocations == 0:
        skill_invocations = sum(
            len(row) if isinstance(row, list) else 0
            for row in QARecord.objects.filter(message_type='assistant').values_list('skills_used', flat=True)
        )
    
    # AI模型统计
    total_ai_models = AIModelConfig.objects.count()
    active_ai_models = AIModelConfig.objects.filter(is_active=True).count()
    
    # API调用统计（最近7天）
    end_time = timezone.now()
    start_time = end_time - timedelta(days=7)
    
    total_api_calls = APILog.objects.filter(created_at__gte=start_time).count()
    total_tokens_used = sum(
        APILog.objects.filter(created_at__gte=start_time).values_list('tokens_used', flat=True)
    ) or 0
    
    error_calls = APILog.objects.filter(
        created_at__gte=start_time,
        status_code__gte=400
    ).count()
    error_rate = (error_calls / total_api_calls * 100) if total_api_calls > 0 else 0
    
    avg_response_time = APILog.objects.filter(
        created_at__gte=start_time
    ).aggregate(avg_duration=Avg('duration'))['avg_duration'] or 0
    
    stats = {
        'total_documents': total_documents,
        'total_questions': total_questions,
        'total_users': total_users,
        'total_knowledge_bases': total_knowledge_bases,
        'agent_invocations': agent_invocations,
        'skill_invocations': skill_invocations,
        'total_courses': total_courses,
        'total_ai_models': total_ai_models,
        'active_ai_models': active_ai_models,
        'total_api_calls': total_api_calls,
        'total_tokens_used': total_tokens_used,
        'error_rate': round(error_rate, 2),
        'avg_response_time': round(avg_response_time, 2)
    }
    
    return Response(stats)


# 批量操作
@api_view(['POST'])
@permission_classes([IsAdminUser])
def batch_test_ai_models(request):
    """批量测试AI模型"""
    model_ids = request.data.get('model_ids', [])
    
    if not model_ids:
        return Response({
            'error': '请提供要测试的模型ID列表'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    results = []
    for model_id in model_ids:
        try:
            config = AIModelConfig.objects.get(model_id=model_id)
            config.test_connection()
            results.append({
                'model_id': model_id,
                'model_name': config.model_name,
                'is_available': config.is_available,
                'error_message': config.error_message
            })
        except AIModelConfig.DoesNotExist:
            results.append({
                'model_id': model_id,
                'model_name': '未知',
                'is_available': False,
                'error_message': '模型配置不存在'
            })
        except Exception as e:
            results.append({
                'model_id': model_id,
                'model_name': '未知',
                'is_available': False,
                'error_message': str(e)
            })
    
    return Response({
        'message': '批量测试完成',
        'results': results
    })


@api_view(['POST'])
@permission_classes([IsAdminUser])
def refresh_ai_engine_cache(request):
    """刷新AI引擎缓存"""
    try:
        if get_ai_engine_factory is None:
            return Response({'message': '学习模块未安装，无需刷新'})
        factory = get_ai_engine_factory()
        factory.clear_cache()
        return Response({
            'message': 'AI引擎缓存已刷新'
        })
    except Exception as e:
        logger.error(f"刷新AI引擎缓存失败: {str(e)}")
        return Response({
            'error': f'刷新缓存失败: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
