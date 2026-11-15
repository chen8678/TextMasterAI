#!/usr/bin/env bash
# 校验「重构」可复现布局：实现代码、关键文档与根兼容链接是否齐全。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PKG="$ROOT/重构"
fail=0

ok()  { printf 'OK   %s\n' "$1"; }
bad() { printf 'FAIL %s\n' "$1"; fail=1; }

need_file() {
  local p="$1"
  if [[ -f "$p" || -L "$p" ]]; then
    # 若是链接，最终目标须存在
    if [[ -e "$p" ]]; then ok "$p"; else bad "$p (broken link)"; fi
  else
    bad "$p"
  fi
}

need_dir() {
  local p="$1"
  if [[ -d "$p" ]]; then ok "$p"; else bad "$p"; fi
}

echo "== 重构包本体 =="
need_dir "$PKG/backend"
need_dir "$PKG/frontend"
need_dir "$PKG/services/vectorization"
need_dir "$PKG/docker"
need_dir "$PKG/docs/guides"
need_dir "$PKG/docs/blueprints"
need_dir "$PKG/docs/execution"
need_dir "$PKG/research"
need_file "$PKG/README.md"
need_file "$PKG/INDEX.md"
need_file "$PKG/REPRODUCE.md"
need_file "$PKG/MANIFEST.md"
need_file "$PKG/backend/manage.py"
need_file "$PKG/frontend/package.json"
need_file "$PKG/docs/guides/DEPLOY.md"
need_file "$PKG/docs/guides/LOCAL_DEV.md"
need_file "$PKG/docs/guides/TENANT_BOUNDARY_AND_REPRO_PROTOCOL.md"
need_file "$PKG/docs/blueprints/Text Master AI 分阶段实现蓝图（2026-04-11）.markdown"
need_file "$PKG/docs/execution/Text Master AI 执行 Todo 清单（2026-04-11）.markdown"
need_file "$PKG/research/PLAN-TODO.markdown"
need_file "$PKG/research/ANSY-SNAPSHOT.markdown"

echo "== 仓库根兼容链接 / compose =="
for name in frontend backend services docker deploy scripts docs research finetune; do
  if [[ -L "$ROOT/$name" ]]; then
    target="$(readlink "$ROOT/$name")"
    if [[ -e "$ROOT/$name" ]]; then ok "$ROOT/$name -> $target"; else bad "$ROOT/$name -> $target (broken)"; fi
  elif [[ -d "$ROOT/$name" ]]; then
    ok "$ROOT/$name (directory)"
  else
    bad "$ROOT/$name (missing)"
  fi
done

need_file "$ROOT/docker-compose.yml"
need_file "$ROOT/.env.example"
need_file "$ROOT/README.md"

# 历史扁平路径
need_file "$PKG/docs/DEPLOY.md"
need_file "$ROOT/docs/DEPLOY.md"

echo "== 摘要 =="
if [[ "$fail" -eq 0 ]]; then
  echo "布局校验通过。下一步见 重构/REPRODUCE.md"
  exit 0
fi
echo "布局校验失败：请按 MANIFEST.md 修复缺失项。"
exit 1
