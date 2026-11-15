import logging
import time
import uuid
from apps.system.monitoring import record_request

logger = logging.getLogger(__name__)


class TraceIdMiddleware:
    """为每个请求注入Trace-ID并在响应头回传"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace_id = request.headers.get('X-Trace-Id') or uuid.uuid4().hex[:16]
        request.trace_id = trace_id
        response = self.get_response(request)
        response['X-Trace-Id'] = trace_id
        return response


class APILogMiddleware:
    """将 /api/ 请求统一写入 APILog（不含请求体，避免敏感数据与体积）。"""

    _SKIP_PREFIXES = (
        '/api/v1/system/health/',
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith('/api/') or request.method == 'OPTIONS':
            return self.get_response(request)
        if any(request.path.startswith(p) for p in self._SKIP_PREFIXES):
            return self.get_response(request)

        start = time.perf_counter()
        response = self.get_response(request)
        duration = time.perf_counter() - start

        try:
            self._persist(request, response, duration)
        except Exception:
            logger.exception('APILogMiddleware: 写入 api_logs 失败')
        try:
            record_request(getattr(response, "status_code", 0), duration)
        except Exception:
            logger.exception('APILogMiddleware: 聚合监控写入失败')

        return response

    def _persist(self, request, response, duration):
        from apps.system.models import APILog

        user = getattr(request, 'user', None)
        if user is not None and not getattr(user, 'is_authenticated', False):
            user = None

        status_code = getattr(response, 'status_code', None) or 0
        trace_id = getattr(request, 'trace_id', '') or ''
        err = ''
        if status_code >= 400:
            err = (getattr(response, 'reason_phrase', None) or '')[:500]

        APILog.objects.create(
            log_type='system',
            model_id='',
            user=user,
            request_data={
                'path': request.path,
                'method': request.method,
                'trace_id': trace_id,
            },
            response_data={},
            status_code=status_code,
            duration=round(duration, 4),
            tokens_used=0,
            error_message=err,
            ip_address=self._client_ip(request),
            user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:1000],
        )

    @staticmethod
    def _client_ip(request):
        from ipaddress import ip_address

        xff = request.META.get('HTTP_X_FORWARDED_FOR')
        if xff:
            raw = xff.split(',')[0].strip()
        else:
            raw = request.META.get('REMOTE_ADDR')
        if not raw or raw.startswith('unix:'):
            return None
        try:
            return str(ip_address(raw.split('%')[0]))
        except ValueError:
            return None

