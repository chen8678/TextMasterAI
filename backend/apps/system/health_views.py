from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
from django.core.cache import cache
from django.conf import settings

@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """系统健康检查端点"""
    health_status = {
        'status': 'healthy',
        'services': {}
    }
    
    # 检查数据库连接
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        health_status['services']['database'] = 'healthy'
    except Exception as e:
        health_status['services']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # 检查Redis连接
    try:
        # 使用Django的缓存系统检查Redis连接
        cache.set('health_check', 'test', 1)
        result = cache.get('health_check')
        if result == 'test':
            health_status['services']['redis'] = 'healthy'
        else:
            health_status['services']['redis'] = 'unhealthy: cache test failed'
            health_status['status'] = 'unhealthy'
    except Exception as e:
        health_status['services']['redis'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'unhealthy'
    
    # 检查向量化服务（使用 settings.VECTORIZATION_SERVICE_URL，空则跳过）
    vectorization_url = (getattr(settings, 'VECTORIZATION_SERVICE_URL', None) or '').strip()
    if vectorization_url:
        try:
            import requests
            base = vectorization_url.rstrip('/')
            health_url = f'{base}/health' if base else 'http://127.0.0.1:8001/health'
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                health_status['services']['vectorization'] = 'healthy'
            else:
                health_status['services']['vectorization'] = 'unhealthy'
        except Exception as e:
            health_status['services']['vectorization'] = f'unreachable: {str(e)}'
    else:
        health_status['services']['vectorization'] = 'not_configured (using TF-IDF fallback)'
    
    # 返回状态码
    if health_status['status'] == 'healthy':
        return Response(health_status, status=status.HTTP_200_OK)
    else:
        return Response(health_status, status=status.HTTP_503_SERVICE_UNAVAILABLE)
