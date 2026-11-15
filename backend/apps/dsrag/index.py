"""DS-RAG 索引与检索（P02）。

优先调用现网向量服务；不可用时回退到确定性 char TF-IDF（写入 meta.backend）。
"""

from __future__ import annotations

import json
import pickle
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from apps.dsrag.config import load_base_config, resolve_path
from apps.dsrag.corpus import read_jsonl, sha256_file
from apps.dsrag.schema import Candidate


def build_context(candidates: list[Candidate], *, max_chars: int = 4000) -> str:
    """D3 与 Generate 共用的上下文截断（P02/P13 硬约束）。"""
    parts: list[str] = []
    used = 0
    for i, c in enumerate(candidates):
        block = f"[{c.chunk_id}] score={c.score:.4f}\n{c.text.strip()}"
        if used + len(block) + 2 > max_chars and parts:
            break
        parts.append(block)
        used += len(block) + 2
    return "\n\n".join(parts)


def _try_remote_embed(texts: list[str], base: dict[str, Any]) -> Optional[np.ndarray]:
    import os

    import requests

    url = (os.getenv("VECTORIZATION_SERVICE_URL") or "http://127.0.0.1:8001").rstrip("/")
    try:
        sess = requests.Session()
        sess.trust_env = False  # 避免系统代理把 localhost:8001 拐跑导致 502
        health = sess.get(f"{url}/health", timeout=3)
        if health.status_code != 200:
            return None
        body = health.json() if health.content else {}
        if body.get("model_loaded") is False:
            return None
        # batch embed（服务约定：POST /vectorize/batch → {vectors: [...]}）
        resp = sess.post(
            f"{url}/vectorize/batch",
            json={"texts": texts},
            timeout=(15, 180),
        )
        if resp.status_code != 200:
            # try single-text API shapes
            vecs = []
            for t in texts:
                r = sess.post(f"{url}/vectorize", json={"text": t}, timeout=(15, 60))
                if r.status_code != 200:
                    return None
                payload = r.json()
                v = payload.get("embedding") or payload.get("vector") or payload.get("embeddings")
                if isinstance(v, list) and v and isinstance(v[0], list):
                    v = v[0]
                if not v:
                    return None
                vecs.append(v)
            return np.asarray(vecs, dtype=np.float32)
        payload = resp.json()
        emb = payload.get("vectors") or payload.get("embeddings") or payload.get("embedding")
        if emb is None:
            return None
        arr = np.asarray(emb, dtype=np.float32)
        if arr.ndim == 1:
            arr = arr.reshape(1, -1)
        if arr.shape[0] != len(texts):
            return None
        return arr
    except Exception:
        return None


def build_index(
    *,
    chunks_path: Path | str | None = None,
    out_dir: Path | str | None = None,
    base: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = base or load_base_config()
    chunks_path = Path(chunks_path) if chunks_path else resolve_path(base["corpus_chunks"])
    out_dir = Path(out_dir) if out_dir else resolve_path(base["index_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(chunks_path)
    if not rows:
        raise ValueError(f"empty chunks: {chunks_path}")
    texts = [r["text"] for r in rows]
    chunk_ids = [r["chunk_id"] for r in rows]
    chunks_hash = sha256_file(chunks_path)

    remote = _try_remote_embed(texts, base)
    vectorizer = None
    if remote is not None:
        matrix = remote
        backend = "bge"
        model_name = str(base.get("embedding_model") or "BAAI/bge-large-zh-v1.5")
    else:
        vectorizer = TfidfVectorizer(analyzer="char", ngram_range=(2, 3), min_df=1)
        matrix = vectorizer.fit_transform(texts)
        # store dense for simple cosine save; sparse ok via pickle
        backend = "sklearn_tfidf_char23"
        model_name = "tfidf_char_2_3"

    # persist
    meta = {
        "embedding_model": model_name,
        "backend": backend,
        "dim": int(matrix.shape[1]) if hasattr(matrix, "shape") else None,
        "n_chunks": len(chunk_ids),
        "chunks_path": str(chunks_path),
        "chunks_sha256": chunks_hash,
        "top_k_default": int(base.get("top_k") or 5),
        "built_at": datetime.now(timezone.utc).isoformat(),
        "note": "索引重建后旧 runs 作废，须重跑 retrieve/eval",
    }
    (out_dir / "meta.yaml").write_text(_dump_meta_yaml(meta), encoding="utf-8")
    with (out_dir / "chunk_ids.json").open("w", encoding="utf-8") as f:
        json.dump(chunk_ids, f, ensure_ascii=False, indent=2)
    with (out_dir / "chunk_texts.json").open("w", encoding="utf-8") as f:
        json.dump(texts, f, ensure_ascii=False)

    payload: dict[str, Any] = {
        "backend": backend,
        "matrix": matrix,
        "vectorizer": vectorizer,
    }
    with (out_dir / "vectors.pkl").open("wb") as f:
        pickle.dump(payload, f, protocol=4)

    return meta


def _dump_meta_yaml(meta: dict[str, Any]) -> str:
    lines = ["# DS-RAG index meta (P02)", f"embedding_model: {meta['embedding_model']!s}"]
    for k in (
        "backend",
        "dim",
        "n_chunks",
        "chunks_path",
        "chunks_sha256",
        "top_k_default",
        "built_at",
        "note",
    ):
        v = meta.get(k)
        if isinstance(v, str):
            lines.append(f"{k}: \"{v}\"")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines) + "\n"


def _load_index(index_dir: Path) -> dict[str, Any]:
    with (index_dir / "vectors.pkl").open("rb") as f:
        payload = pickle.load(f)
    chunk_ids = json.loads((index_dir / "chunk_ids.json").read_text(encoding="utf-8"))
    texts = json.loads((index_dir / "chunk_texts.json").read_text(encoding="utf-8"))
    meta_text = (index_dir / "meta.yaml").read_text(encoding="utf-8")
    return {"payload": payload, "chunk_ids": chunk_ids, "texts": texts, "meta_text": meta_text}


def retrieve(
    query: str,
    k: int | None = None,
    *,
    index_dir: Path | str | None = None,
    base: dict[str, Any] | None = None,
) -> list[Candidate]:
    base = base or load_base_config()
    k = int(k if k is not None else base.get("top_k") or 5)
    index_dir = Path(index_dir) if index_dir else resolve_path(base["index_dir"])
    bundle = _load_index(index_dir)
    payload = bundle["payload"]
    chunk_ids = bundle["chunk_ids"]
    texts = bundle["texts"]
    matrix = payload["matrix"]
    backend = payload["backend"]

    if backend == "sklearn_tfidf_char23":
        vectorizer: TfidfVectorizer = payload["vectorizer"]
        qv = vectorizer.transform([query])
        sims = cosine_similarity(qv, matrix).ravel()
    else:
        # dense (bge / vectorization_service): embed query via same service
        q_emb = _try_remote_embed([query], base)
        if q_emb is None:
            raise RuntimeError("index backend is dense embeddings but vector service unavailable")
        sims = cosine_similarity(q_emb, matrix).ravel()

    # stable ranking: (-score, chunk_id)
    ranked = sorted(
        range(len(chunk_ids)),
        key=lambda i: (-float(sims[i]), chunk_ids[i]),
    )
    out: list[Candidate] = []
    for i in ranked[:k]:
        out.append(
            Candidate(
                chunk_id=chunk_ids[i],
                score=float(sims[i]),
                text=texts[i],
            )
        )
    return out
