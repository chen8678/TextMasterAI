#!/usr/bin/env bash
# Phase-0 门禁 smoke：逐条 PASS/FAIL（依赖已启动的 API）
# 用法: bash 重构/scripts/phase0_smoke.sh [BASE_URL]
# 可选环境: SMOKE_USER / SMOKE_PASS（已有账号）；SMOKE_BACKEND 指向 manage.py 所在目录以播种配额

set -u
BASE_URL="${1:-http://127.0.0.1:8000}"
BASE_URL="${BASE_URL%/}"
SMOKE_USER="${SMOKE_USER:-phase0_smoke_user}"
SMOKE_PASS="${SMOKE_PASS:-Phase0Smoke!Pass9}"
SMOKE_BACKEND="${SMOKE_BACKEND:-$(cd "$(dirname "$0")/../backend" && pwd)}"
PASS=0
FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

say() { printf '%s\n' "$*"; }
ok() { say "PASS  $*"; PASS=$((PASS + 1)); }
bad() { say "FAIL  $*"; FAIL=$((FAIL + 1)); }

code_of() { # $1=file
  head -n1 "$1" | tr -d '\r'
}

# --- health ---
curl -sS -o "$TMP/health.json" -w "%{http_code}" "$BASE_URL/api/v1/system/health/" >"$TMP/health.code" || true
if [[ "$(code_of "$TMP/health.code")" == "200" ]]; then
  ok "health 200"
else
  bad "health expected 200 got $(code_of "$TMP/health.code")"
fi

# --- simple API 404 ---
curl -sS -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/simple/" >"$TMP/simple.code" || true
if [[ "$(code_of "$TMP/simple.code")" == "404" ]]; then
  ok "api/v1/simple/* 404"
else
  bad "simple expected 404 got $(code_of "$TMP/simple.code")"
fi

# --- anonymous analyze_document 401 ---
curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/knowledge/analyze-document/" \
  -H "Content-Type: application/json" -d '{}' >"$TMP/analyze.code" || true
AC="$(code_of "$TMP/analyze.code")"
if [[ "$AC" == "401" || "$AC" == "403" ]]; then
  ok "anonymous analyze_document $AC (unauthenticated)"
else
  bad "analyze_document expected 401/403 got $AC"
fi

# --- ensure login user (register once if open) ---
curl -sS -o "$TMP/reg.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/auth/register/" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$SMOKE_USER\",\"email\":\"${SMOKE_USER}@example.com\",\"password\":\"$SMOKE_PASS\",\"password_confirm\":\"$SMOKE_PASS\"}" \
  >"$TMP/reg.code" || true

curl -sS -o "$TMP/login.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$SMOKE_USER\",\"password\":\"$SMOKE_PASS\"}" \
  >"$TMP/login.code" || true
LC="$(code_of "$TMP/login.code")"
if [[ "$LC" == "200" ]]; then
  ok "login 200"
else
  bad "login expected 200 got $LC body=$(head -c 200 "$TMP/login.json")"
fi

ACCESS="$(python3 -c "import json;print(json.load(open('$TMP/login.json')).get('access',''))" 2>/dev/null || true)"
REFRESH="$(python3 -c "import json;print(json.load(open('$TMP/login.json')).get('refresh',''))" 2>/dev/null || true)"

# --- refresh 换新 200 ---
if [[ -n "$REFRESH" ]]; then
  curl -sS -o "$TMP/ref1.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/auth/token/refresh/" \
    -H "Content-Type: application/json" \
    -d "{\"refresh\":\"$REFRESH\"}" >"$TMP/ref1.code" || true
  if [[ "$(code_of "$TMP/ref1.code")" == "200" ]]; then
    ok "refresh 换新 200"
    NEW_REFRESH="$(python3 -c "import json;d=json.load(open('$TMP/ref1.json'));print(d.get('refresh') or '$REFRESH')" 2>/dev/null || echo "$REFRESH")"
    OLD_REFRESH="$REFRESH"
    REFRESH="$NEW_REFRESH"
    ACCESS="$(python3 -c "import json;print(json.load(open('$TMP/ref1.json')).get('access',''))" 2>/dev/null || true)"
  else
    bad "refresh 换新 expected 200 got $(code_of "$TMP/ref1.code")"
    OLD_REFRESH="$REFRESH"
  fi
else
  bad "refresh 换新 skipped (no refresh token)"
  OLD_REFRESH=""
fi

# --- logout 200 ---
if [[ -n "$REFRESH" && -n "$ACCESS" ]]; then
  curl -sS -o "$TMP/logout.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/auth/logout/" \
    -H "Authorization: Bearer $ACCESS" \
    -H "Content-Type: application/json" \
    -d "{\"refresh\":\"$REFRESH\"}" >"$TMP/logout.code" || true
  if [[ "$(code_of "$TMP/logout.code")" == "200" ]]; then
    ok "logout 200"
  else
    bad "logout expected 200 got $(code_of "$TMP/logout.code")"
  fi
  # 旧 refresh（已旋转或已登出）应 401
  curl -sS -o "$TMP/ref2.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/auth/token/refresh/" \
    -H "Content-Type: application/json" \
    -d "{\"refresh\":\"${OLD_REFRESH:-$REFRESH}\"}" >"$TMP/ref2.code" || true
  RC="$(code_of "$TMP/ref2.code")"
  if [[ "$RC" == "401" ]]; then
    ok "旧 refresh 401"
  else
    bad "旧 refresh expected 401 got $RC"
  fi
else
  bad "logout / 旧 refresh skipped (missing tokens)"
fi

# --- 连续注册 429 ---
REG_HIT=0
for i in 1 2 3 4 5 6 7; do
  curl -sS -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/auth/register/" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"smoke_reg_$i_$RANDOM\",\"email\":\"smoke_reg_$i_$RANDOM@ex.com\",\"password\":\"$SMOKE_PASS\",\"password_confirm\":\"$SMOKE_PASS\"}" \
    >"$TMP/regn.code" || true
  if [[ "$(code_of "$TMP/regn.code")" == "429" ]]; then
    REG_HIT=1
    break
  fi
done
if [[ "$REG_HIT" == "1" ]]; then
  ok "连续注册 429"
else
  # 注册关闭时可能全是 403 — 记为 PARTIAL 语义：仍标 FAIL 并说明
  bad "连续注册 429 not observed (last=$(code_of "$TMP/regn.code"); registration may be closed)"
fi

# --- 触发配额 429（本地播种 UsageDaily）---
# 重新登录拿 token
curl -sS -o "$TMP/login2.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/auth/login/" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$SMOKE_USER\",\"password\":\"$SMOKE_PASS\"}" >"$TMP/login2.code" || true
ACCESS2="$(python3 -c "import json;print(json.load(open('$TMP/login2.json')).get('access',''))" 2>/dev/null || true)"
if [[ -n "$ACCESS2" && -d "$SMOKE_BACKEND" ]]; then
  (
    cd "$SMOKE_BACKEND" && python manage.py shell -c "
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from apps.chat.models import UsageDaily
u = get_user_model().objects.filter(username='${SMOKE_USER}').first()
assert u, 'smoke user missing'
limit = int(getattr(settings, 'USER_DAILY_ASK_LIMIT', 50))
UsageDaily.objects.update_or_create(
    user=u, date=timezone.localdate(),
    defaults={'ask_count': limit, 'token_count': 0},
)
print('seeded', limit)
"
  ) >"$TMP/seed.out" 2>"$TMP/seed.err" || true
  curl -sS -o "$TMP/ask.json" -w "%{http_code}" -X POST "$BASE_URL/api/v1/chat/ask/" \
    -H "Authorization: Bearer $ACCESS2" \
    -H "Content-Type: application/json" \
    -d '{"question":"smoke quota","knowledge_base_id":"00000000-0000-0000-0000-000000000001"}' \
    >"$TMP/ask.code" || true
  if [[ "$(code_of "$TMP/ask.code")" == "429" ]]; then
    ok "触发配额 429"
  else
    bad "触发配额 expected 429 got $(code_of "$TMP/ask.code") seed=$(head -c 120 "$TMP/seed.out" "$TMP/seed.err" 2>/dev/null | tr '\n' ' ')"
  fi
else
  bad "触发配额 429 skipped (no access or backend)"
fi

say "----"
say "SUMMARY pass=$PASS fail=$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
exit 0
