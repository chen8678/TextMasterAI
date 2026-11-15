#!/usr/bin/env bash
# 下载开源英语词库到 backend/apps/english_learning/data/curriculum/raw/
# 来源见同目录 ../SOURCES.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RAW="$ROOT/backend/apps/english_learning/data/curriculum/raw"
mkdir -p "$RAW"

echo "==> KyleBing/english-vocabulary (初中/高中/CET4/CET6)"
KYLE="https://raw.githubusercontent.com/KyleBing/english-vocabulary/master/json"
for pair in \
  "1-初中-顺序.json" \
  "2-高中-顺序.json" \
  "3-CET4-顺序.json" \
  "4-CET6-顺序.json"; do
  dest="$RAW/$pair"
  if [[ -f "$dest" && -s "$dest" ]]; then
    echo "  skip (exists): $pair"
  else
    echo "  download: $pair"
    curl -fsSL "$KYLE/$pair" -o "$dest"
  fi
done

echo "==> 人教版 PEP 小学 3–6 年级 (kajweb/dict → NetEase CDN JSONL)"
PEP_ZIPS=(
  "1521164661774_PEPXiaoXue3_1.zip"
  "1521164656604_PEPXiaoXue3_2.zip"
  "1521164677447_PEPXiaoXue4_1.zip"
  "1521164663086_PEPXiaoXue4_2.zip"
  "1530101080610_PEPXiaoXue5_1.zip"
  "1530101073491_PEPXiaoXue5_2.zip"
  "1530101075331_PEPXiaoXue6_1.zip"
  "1521164632445_PEPXiaoXue6_2.zip"
)
PEP_BASE="http://ydschool-online.nos.netease.com"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
MERGED="$RAW/primary_merged.jsonl"
: > "$MERGED"
for z in "${PEP_ZIPS[@]}"; do
  echo "  fetch $z"
  curl -fsSL "$PEP_BASE/$z" -o "$TMP/$z"
  unzip -q -o "$TMP/$z" -d "$TMP"
done
for j in "$TMP"/PEPXiaoXue*.json; do
  [[ -f "$j" ]] || continue
  echo "  merge $(basename "$j")"
  cat "$j" >> "$MERGED"
done
echo "  primary lines: $(wc -l < "$MERGED" | tr -d ' ')"

echo "==> Done. Raw files in: $RAW"
ls -lh "$RAW"
