#!/usr/bin/env bash
# 生成分发型离线包：frontend-dist + Linux/py39 wheels
# 依赖：本机可联网、Python3、Node/npm；路径含空格时请仍从项目根执行

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/deploy/offline-bundle"
REQ_OFFLINE="$OUT/requirements-offline-py39-linux.txt"

cd "$ROOT"

echo "==> 前端 npm run build"
( cd frontend && npm run build )

echo "==> 同步 frontend/dist -> deploy/offline-bundle/frontend-dist"
mkdir -p "$OUT/frontend-dist"
rsync -a --delete "$ROOT/frontend/dist/" "$OUT/frontend-dist/"

echo "==> 下载 Linux x86_64 / CPython 3.9 wheels（不含 ifcopenshell）"
rm -rf "$OUT/python-wheels-linux"
mkdir -p "$OUT/python-wheels-linux"
python3 -m pip download -r "$REQ_OFFLINE" -d "$OUT/python-wheels-linux" \
  --platform manylinux2014_x86_64 \
  --python-version 39 \
  --implementation cp \
  --abi cp39 \
  --only-binary=:all:

echo "==> 完成：$OUT"
echo "    请阅读 deploy/offline-bundle/README-offline.txt，并用 SFTP 上传 frontend-dist、python-wheels-linux、requirements-offline-py39-linux.txt 及整个 backend/"
