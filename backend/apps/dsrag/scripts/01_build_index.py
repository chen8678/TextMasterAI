#!/usr/bin/env python3
"""P02：构建 DS-RAG 索引。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from apps.dsrag.index import build_index  # noqa: E402


def main() -> None:
    meta = build_index()
    print(meta)


if __name__ == "__main__":
    main()
