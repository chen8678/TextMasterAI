"""
向量化服务客户端 - 与向量化微服务通信（同步 httpx，连接复用，避免 Django 内 asyncio 与短连接断连）
"""
import httpx
import logging
from typing import List, Dict, Any, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# 进程内复用连接，降低「Server disconnected」概率
_http_client: Optional[httpx.Client] = None


def _get_http_client() -> httpx.Client:
    global _http_client
    if _http_client is None:
        _http_client = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=16, max_connections=32),
            trust_env=False,
        )
    return _http_client


class SyncVectorizationClient:
    """同步向量化客户端（供 VectorizationService 使用）"""

    def __init__(self, base_url: str = None):
        raw = base_url or getattr(settings, "VECTORIZATION_SERVICE_URL", "http://127.0.0.1:8001")
        self.base_url = (raw or "").rstrip("/")
        self.max_retries = 2

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        client = _get_http_client()
        last_error: Optional[BaseException] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = client.request(method, url, **kwargs)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("向量化服务返回格式异常")
                return payload
            except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as e:
                last_error = e
                if attempt < self.max_retries:
                    logger.warning(
                        "向量化服务请求重试 %s/%s: %s",
                        attempt + 1,
                        self.max_retries + 1,
                        e,
                    )
                    continue
                logger.error("向量化服务请求超时/断连: %s error=%s", url, e)
                raise Exception("向量化服务请求超时或断连") from e
            except httpx.HTTPStatusError as e:
                logger.error(
                    "向量化服务HTTP错误: %s - %s",
                    e.response.status_code,
                    e.response.text,
                )
                raise Exception(f"向量化服务错误: {e.response.status_code}") from e
            except Exception as e:
                last_error = e
                logger.error("向量化服务请求失败: %s", e)
                if attempt >= self.max_retries:
                    raise Exception(f"向量化服务请求失败: {str(e)}") from e
        raise Exception(f"向量化服务请求失败: {last_error}")

    def health_check(self) -> Dict[str, Any]:
        return self._make_request("GET", "/health")

    def vectorize_text(self, text: str, model_name: str = "BAAI/bge-large-zh-v1.5") -> List[float]:
        response = self._make_request(
            "POST",
            "/vectorize",
            json={"text": text, "model_name": model_name},
        )
        return response["vector"]

    def vectorize_batch(self, texts: List[str], model_name: str = "BAAI/bge-large-zh-v1.5") -> List[List[float]]:
        response = self._make_request(
            "POST",
            "/vectorize/batch",
            json={"texts": texts, "model_name": model_name},
        )
        return response["vectors"]

    def search_similar(
        self,
        query: str,
        vectors: List[List[float]],
        top_k: int = 5,
        model_name: str = "BAAI/bge-large-zh-v1.5",
    ) -> List[Dict[str, Any]]:
        response = self._make_request(
            "POST",
            "/search",
            json={
                "query": query,
                "vectors": vectors,
                "top_k": top_k,
                "model_name": model_name,
            },
        )
        return response["results"]
