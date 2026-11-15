"""语料清洗与切片（P01）。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    # 去掉明显导航噪声行
    lines = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            lines.append("")
            continue
        if re.fullmatch(r"[-_=*]{3,}", s):
            continue
        if s.lower() in {"navigation", "目录", "返回顶部", "home"}:
            continue
        lines.append(s)
    text = "\n".join(lines)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def chunk_text(
    text: str,
    *,
    target_chars: int = 600,
    overlap: int = 80,
) -> list[str]:
    """按字符窗切片；优先在段落边界断开。"""
    text = clean_text(text)
    if not text:
        return []
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras:
        paras = [text]

    chunks: list[str] = []
    buf = ""
    for p in paras:
        if not buf:
            buf = p
            continue
        if len(buf) + 1 + len(p) <= target_chars:
            buf = f"{buf}\n\n{p}"
        else:
            chunks.append(buf)
            # overlap：取末尾 overlap 字符作下一段前缀
            if overlap > 0 and len(buf) > overlap:
                tail = buf[-overlap:]
                buf = f"{tail}\n\n{p}" if len(p) < target_chars else p
            else:
                buf = p
            # 单段过长则硬切
            while len(buf) > target_chars * 2:
                chunks.append(buf[:target_chars])
                buf = buf[target_chars - overlap :] if overlap < target_chars else buf[target_chars:]
    if buf.strip():
        chunks.append(buf.strip())

    # 合并过短尾块
    merged: list[str] = []
    for c in chunks:
        if merged and len(c) < 120:
            merged[-1] = f"{merged[-1]}\n\n{c}"
        else:
            merged.append(c)
    return merged


def load_raw_dir(raw_dir: Path) -> list[dict[str, Any]]:
    docs = []
    paths = sorted(raw_dir.glob("*.txt"))
    for i, path in enumerate(paths):
        raw = path.read_text(encoding="utf-8")
        meta_title = path.stem
        source_url = f"local://dsrag/raw/{path.name}"
        # optional first-line meta: # title: ... | source: ...
        body = raw
        if raw.startswith("#"):
            first, _, rest = raw.partition("\n")
            m_title = re.search(r"title\s*[:=]\s*(.+)", first, re.I)
            m_src = re.search(r"source\s*[:=]\s*(\S+)", first, re.I)
            if m_title:
                meta_title = m_title.group(1).strip()
            if m_src:
                source_url = m_src.group(1).strip()
            body = rest if (m_title or m_src) else raw
        doc_id = f"doc_{i:03d}_{path.stem}"
        docs.append(
            {
                "doc_id": doc_id,
                "title": meta_title,
                "text": clean_text(body),
                "source_url": source_url,
                "raw_file": path.name,
            }
        )
    return docs


def build_chunks(
    docs: Iterable[dict[str, Any]],
    *,
    target_chars: int = 600,
    overlap: int = 80,
) -> list[dict[str, Any]]:
    out = []
    for doc in docs:
        parts = chunk_text(doc["text"], target_chars=target_chars, overlap=overlap)
        for ord_i, part in enumerate(parts):
            chunk_id = f"{doc['doc_id']}#c{ord_i}"
            out.append(
                {
                    "chunk_id": chunk_id,
                    "doc_id": doc["doc_id"],
                    "text": part,
                    "ord": ord_i,
                    "title": doc.get("title") or "",
                }
            )
    return out


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows
