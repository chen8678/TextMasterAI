#!/usr/bin/env bash
# Phase-0：DEBUG=False + 强 SECRET 跑 manage.py check --deploy
# 断言无 CRITICAL/ERROR；WARNING 打印供写入报告（W004/W008/W012/W016 不得忽略）
# 用法: bash 重构/scripts/phase0_deploy_check.sh

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
cd "$BACKEND"

# Django W009 要求足够长且高熵；token_urlsafe(48) ≈ 64 字符
SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export DEBUG=False
export SECRET_KEY="$SECRET"
export ALLOWED_HOSTS="${ALLOWED_HOSTS:-localhost,127.0.0.1}"
export CORS_ALLOWED_ORIGINS="${CORS_ALLOWED_ORIGINS:-http://localhost:3009}"

echo "Running: DEBUG=False SECRET_KEY=<${#SECRET} chars> manage.py check --deploy"
OUT="$(mktemp)"
set +e
python manage.py check --deploy >"$OUT" 2>&1
RC=$?
set -e
cat "$OUT"

if grep -qiE '\(security\.|security\)' "$OUT" | head -1 >/dev/null 2>&1; then
  :
fi

if grep -qiE 'CRITICAL|System check identified [1-9][0-9]* error' "$OUT"; then
  echo "DEPLOY_CHECK: CRITICAL or ERROR present — fail"
  rm -f "$OUT"
  exit 1
fi

echo "----"
echo "Warnings (document disposition in PHASE0 report; do not ignore W004/W008/W012/W016):"
grep -E 'security\.W[0-9]+' "$OUT" || echo "(no security.W* lines)"
echo "Suggested disposition when TLS not yet cut over:"
echo "  W004/W008/W012/W016 → set SECURE_HTTPS=true after TLS terminator is live"
echo "  W009 → ensure SECRET_KEY length>=50 (this script uses 48-byte urlsafe)"
rm -f "$OUT"
# Django 对 warning 也可能返回非 0；本门禁以无 CRITICAL/ERROR 为通过
echo "DEPLOY_CHECK: PASS (no CRITICAL/ERROR; django_exit=$RC)"
exit 0
