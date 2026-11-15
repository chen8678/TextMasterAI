"""
向量化微服务：与 backend/apps/knowledge/vectorization_client.py 约定一致。
默认模型 BAAI/bge-large-zh-v1.5（1024 维），与 Django 侧向量维度一致。

启动时在后台线程加载模型，避免 lifespan 阻塞导致端口迟迟不监听、curl 得到空响应。
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading

# Compose 若传入 HF_ENDPOINT= 空串，huggingface_hub 会把下载 URL 拼成 "/BAAI/..." 而报 MissingSchema
_hfe = os.environ.get("HF_ENDPOINT", "").strip()
if not _hfe:
    os.environ.pop("HF_ENDPOINT", None)
elif not _hfe.startswith(("http://", "https://")):
    os.environ["HF_ENDPOINT"] = "https://" + _hfe.lstrip("/")

# 下载超时（秒），弱网或镜像站可拉长
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn.error")

DEFAULT_MODEL = os.getenv("DEFAULT_MODEL_NAME", "BAAI/bge-large-zh-v1.5")
EMBED_DIM = 1024
MODEL_LOAD_WAIT_SEC = float(os.getenv("MODEL_LOAD_WAIT_SEC", "600"))


class FallbackEmbedder:
    """无法从 Hub 拉模型时使用：同文本得到稳定向量，语义质量差，仅保证接口可用。"""

    def encode(self, sentences, normalize_embeddings=True, **kwargs):
        if isinstance(sentences, str):
            sentences = [sentences]
        out: List[np.ndarray] = []
        for s in sentences:
            seed = int(hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16], 16)
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(EMBED_DIM).astype(np.float64)
            if normalize_embeddings:
                v = v / (np.linalg.norm(v) + 1e-12)
            out.append(v)
        arr = np.stack(out, axis=0)
        if len(out) == 1:
            return arr[0]
        return arr


_model = None
_backend: str = "none"  # "st" | "fallback"
_current_model_name: str = DEFAULT_MODEL
_load_error: Optional[str] = None

_load_finished = threading.Event()
_loader_thread: Optional[threading.Thread] = None


def _load_sentence_transformer_or_fallback() -> None:
    global _model, _backend, _load_error
    _load_error = None
    try:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(_current_model_name)
        _backend = "st"
        logger.info("SentenceTransformer loaded: %s", _current_model_name)
    except Exception as e:
        _load_error = str(e)
        logger.warning(
            "SentenceTransformer 加载失败（常见原因：无法访问 huggingface.co / 未配置 HF 镜像），"
            "启用本地确定性降级向量（仅保证联调，检索语义不可用）: %s",
            e,
        )
        _model = FallbackEmbedder()
        _backend = "fallback"


def _background_load() -> None:
    try:
        _load_sentence_transformer_or_fallback()
    finally:
        _load_finished.set()


def _get_model():
    """等待后台加载完成（/vectorize 等调用）。"""
    global _model
    if _model is not None:
        return _model
    if not _load_finished.wait(timeout=MODEL_LOAD_WAIT_SEC):
        raise HTTPException(
            status_code=503,
            detail="嵌入模型仍在加载或超时，请稍后重试（见 MODEL_LOAD_WAIT_SEC）",
        )
    if _model is None:
        raise HTTPException(status_code=503, detail="嵌入模型未就绪")
    return _model


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loader_thread
    _load_finished.clear()
    _loader_thread = threading.Thread(target=_background_load, daemon=True, name="embedding-loader")
    _loader_thread.start()
    yield


app = FastAPI(title="Text Master Vectorization", version="1.0.0", lifespan=lifespan)


class VectorizeBody(BaseModel):
    text: str = ""
    model_name: Optional[str] = None


class VectorizeBatchBody(BaseModel):
    texts: List[str] = Field(default_factory=list)
    model_name: Optional[str] = None


class SearchBody(BaseModel):
    query: str = ""
    vectors: List[List[float]] = Field(default_factory=list)
    top_k: int = 5
    model_name: Optional[str] = None


@app.get("/health")
def health() -> Dict[str, Any]:
    """加载完成前返回 starting，便于 curl / 探活立即有 JSON。"""
    if not _load_finished.is_set():
        return {
            "status": "starting",
            "model_loaded": False,
            "model_name": _current_model_name,
            "embedding_backend": "none",
            "message": "嵌入模型加载中（首次可能需数分钟下载），此间端口已监听",
        }
    m = _model
    out: Dict[str, Any] = {
        "status": "healthy",
        "model_loaded": m is not None,
        "model_name": _current_model_name,
        "embedding_backend": _backend,
    }
    if _backend == "fallback":
        out["warning"] = (
            "使用降级嵌入（未加载 BGE）；请配置 HF_ENDPOINT 镜像或改善网络后重启容器"
        )
    if _load_error and _backend == "st":
        out["load_error"] = _load_error
    return out


@app.get("/models")
def list_models() -> Dict[str, Any]:
    return {"models": [_current_model_name], "current": _current_model_name}


@app.post("/models/switch")
def switch_model(model_name: str = Query(..., description="HuggingFace model id or local path")) -> Dict[str, Any]:
    global _model, _current_model_name, _backend
    _model = None
    _backend = "none"
    _current_model_name = model_name
    _load_sentence_transformer_or_fallback()
    return {"ok": True, "model_name": _current_model_name, "embedding_backend": _backend}


@app.get("/stats")
def stats() -> Dict[str, Any]:
    return {
        "model_name": _current_model_name,
        "model_loaded": _model is not None,
        "embedding_backend": _backend,
        "load_done": _load_finished.is_set(),
    }


@app.post("/vectorize")
def vectorize(body: VectorizeBody) -> Dict[str, Any]:
    model = _get_model()
    text = body.text or ""
    emb = model.encode(text, normalize_embeddings=True)
    vec = np.asarray(emb).flatten()
    return {"vector": vec.tolist()}


@app.post("/vectorize/batch")
def vectorize_batch(body: VectorizeBatchBody) -> Dict[str, Any]:
    model = _get_model()
    texts = body.texts or [""]
    embs = model.encode(texts, normalize_embeddings=True)
    arr = np.asarray(embs)
    if arr.ndim == 1:
        vectors = [arr.tolist()]
    else:
        vectors = [row.tolist() for row in arr]
    return {"vectors": vectors}


@app.post("/search")
def search(body: SearchBody) -> Dict[str, Any]:
    """对候选向量与查询文本 embedding 做余弦相似度排序（兼容客户端契约）。"""
    model = _get_model()
    q = model.encode(body.query or "", normalize_embeddings=True)
    qv = np.asarray(q, dtype=np.float64).flatten()
    qn = np.linalg.norm(qv) + 1e-12
    vectors = body.vectors or []
    scored: List[tuple] = []
    for idx, v in enumerate(vectors):
        dv = np.asarray(v, dtype=np.float64).flatten()
        dn = np.linalg.norm(dv) + 1e-12
        sim = float(np.dot(qv, dv) / (qn * dn))
        scored.append((idx, sim))
    scored.sort(key=lambda x: -x[1])
    top_k = max(1, min(body.top_k, len(scored) if scored else 1))
    results = [{"index": i, "score": s} for i, s in scored[:top_k]]
    return {"results": results}
