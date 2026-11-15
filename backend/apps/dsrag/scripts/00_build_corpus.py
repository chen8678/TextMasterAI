#!/usr/bin/env python3
"""P01：从 raw 构建 docs.jsonl / chunks.jsonl / MANIFEST.yaml。"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# 允许直接 python scripts/00_build_corpus.py
ROOT = Path(__file__).resolve().parents[3]  # backend/
sys.path.insert(0, str(ROOT))

from apps.dsrag.corpus import (  # noqa: E402
    build_chunks,
    load_raw_dir,
    sha256_file,
    write_jsonl,
)

REPO = ROOT.parent
RAW = REPO / "SCAR" / "data" / "dsrag" / "raw"
CORPUS = REPO / "SCAR" / "data" / "dsrag" / "corpus"
CHUNKS_DIR = REPO / "SCAR" / "data" / "dsrag" / "chunks"


def main() -> None:
    docs = load_raw_dir(RAW)
    if not docs:
        raise SystemExit(f"no txt in {RAW}")
    chunks = build_chunks(docs, target_chars=600, overlap=80)

    CORPUS.mkdir(parents=True, exist_ok=True)
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    docs_path = CORPUS / "docs.jsonl"
    # 双写：契约路径 chunks/ + corpus/ 各一份一致内容
    chunks_path = CHUNKS_DIR / "chunks.jsonl"
    chunks_path_alt = CORPUS / "chunks.jsonl"

    write_jsonl(docs_path, docs)
    write_jsonl(chunks_path, chunks)
    write_jsonl(chunks_path_alt, chunks)

    docs_hash = sha256_file(docs_path)
    chunks_hash = sha256_file(chunks_path)
    assert sha256_file(chunks_path_alt) == chunks_hash

    manifest = f"""# DS-RAG corpus MANIFEST (P01)
corpus_id: campus_lab_synthetic_v0
source_type: synthetic_curated
source_url: synthetic://dsrag/campus_lab_v0
license: research_internal_synthetic
license_note: 合成制度语料，仅用于 Decision-Split RAG 可复现实验；非真实校规，禁止当作真实制度执行依据。
download_date: {date.today().isoformat()}
filter_rule: "UTF-8 txt; strip navigation noise; paragraph window chunk target_chars=600 overlap=80; chunk_id={{doc_id}}#c{{ord}}"
raw_dir: SCAR/data/dsrag/raw
docs_path: SCAR/data/dsrag/corpus/docs.jsonl
chunks_path: SCAR/data/dsrag/chunks/chunks.jsonl
docs_sha256: {docs_hash}
chunks_sha256: {chunks_hash}
n_docs: {len(docs)}
n_chunks: {len(chunks)}
encoding: UTF-8
"""
    (CORPUS / "MANIFEST.yaml").write_text(manifest, encoding="utf-8")
    print(
        {
            "n_docs": len(docs),
            "n_chunks": len(chunks),
            "docs_sha256": docs_hash,
            "chunks_sha256": chunks_hash,
            "manifest": str(CORPUS / "MANIFEST.yaml"),
        }
    )


if __name__ == "__main__":
    main()
