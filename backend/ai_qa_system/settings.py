# -*- coding: utf-8 -*-
# 测试包最小配置：登录 + 知识库 + AI 问答
import logging
import os
from celery.schedules import crontab
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
# override=False：Compose / 进程已注入的变量（如 DATABASE_URL）优先生效，避免 backend/.env 里本机 127.0.0.1:5433 覆盖容器内应使用的 postgres 主机名。
# 若需在容器内用 .env 补全未设置的项，保持 False；仅本机且希望 .env 强制覆盖 shell 时，可临时 export 清空后再启动。
load_dotenv(BASE_DIR / ".env", override=False)

def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# P0-01：DEBUG 从环境读取，缺省 False；本地开发在 backend/.env 设 DEBUG=True
DEBUG = _env_bool("DEBUG", False)

_secret = (os.getenv("SECRET_KEY") or "").strip()
if (not DEBUG) and (
    not _secret
    or _secret.startswith("django-insecure")
    or len(_secret) < 40
):
    raise ImproperlyConfigured(
        "SECRET_KEY must be set to a strong value when DEBUG=False "
        "(non-empty, length>=40, must not start with 'django-insecure')."
    )
# DEBUG 下占位；禁止使用 insecure 官方前缀作默认值（见上方 fail-fast）
SECRET_KEY = _secret or "dev-only-placeholder-set-SECRET_KEY-in-backend-dotenv"

_allowed_default = "localhost,127.0.0.1,0.0.0.0"
ALLOWED_HOSTS_ENV = os.getenv("ALLOWED_HOSTS", _allowed_default if DEBUG else "")
ALLOWED_HOSTS = [h.strip() for h in ALLOWED_HOSTS_ENV.split(",") if h.strip()]
if DEBUG and "host.docker.internal" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("host.docker.internal")
if not DEBUG and not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS must be explicitly set when DEBUG=False."
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "apps.auth.apps.AuthConfig",
    "apps.simple_api.apps.SimpleApiConfig",
    "apps.knowledge.apps.KnowledgeConfig",
    "apps.chat.apps.ChatConfig",
    "apps.skills.apps.SkillsConfig",
    "apps.agents.apps.AgentsConfig",
    "apps.system.apps.SystemConfig",
    "apps.cet.apps.CETConfig",
    "apps.workflows.apps.WorkflowsConfig",
    "apps.english_learning.apps.EnglishLearningConfig",
    "apps.scar.apps.ScarConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "ai_qa_system.middleware.TraceIdMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "ai_qa_system.middleware.APILogMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "ai_qa_system.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "ai_qa_system.wsgi.application"

# Database
from urllib.parse import urlparse
database_url = os.getenv("DATABASE_URL")
if database_url:
    p = urlparse(database_url)
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": p.path[1:],
        "USER": p.username,
        "PASSWORD": p.password,
        "HOST": p.hostname,
        "PORT": p.port or "5432",
    }}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "ai_qa_system",
        "USER": "postgres",
        "PASSWORD": "password",
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "custom_auth.User"

_cors_default = (
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3009,http://127.0.0.1:3009"
    if DEBUG
    else ""
)
CORS_ALLOWED_ORIGINS_ENV = os.getenv("CORS_ALLOWED_ORIGINS", _cors_default)
CORS_ALLOWED_ORIGINS = [x.strip() for x in CORS_ALLOWED_ORIGINS_ENV.split(",") if x.strip()]
# P0-09：App WebView 壳 Origin（Bearer JWT，不依赖 Cookie）
_app_shell_default = "capacitor://localhost,http://localhost,http://localhost:3009"
APP_SHELL_ORIGINS = [
    x.strip()
    for x in os.getenv("APP_SHELL_ORIGINS", _app_shell_default).split(",")
    if x.strip()
]
for _origin in APP_SHELL_ORIGINS:
    if _origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(_origin)
CSRF_TRUSTED_ORIGINS_ENV = os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    os.getenv("CORS_ALLOWED_ORIGINS", _cors_default),
)
CSRF_TRUSTED_ORIGINS = [x.strip() for x in CSRF_TRUSTED_ORIGINS_ENV.split(",") if x.strip()]
if not DEBUG and not CORS_ALLOWED_ORIGINS:
    logging.getLogger(__name__).warning(
        "CORS_ALLOWED_ORIGINS is empty while DEBUG=False; browser cross-origin requests will be denied."
    )
# P0-09：全站 Authorization Bearer，不需要跨域 Cookie
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_HEADERS = list(
    {
        "accept",
        "authorization",
        "content-type",
        "user-agent",
        "x-csrftoken",
        "x-requested-with",
    }
)

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_RATES": {
        # P3-T21：登录按 IP 限流（暴力破解防护）
        "login": os.getenv("THROTTLE_LOGIN", "20/min"),
        # P0-04：自助注册限流
        "register": os.getenv("THROTTLE_REGISTER", "5/hour"),
        # 问答按用户限流（默认每分钟 60 次）
        "ask_question": os.getenv("THROTTLE_ASK_QUESTION", "60/min"),
        # 沙盒触发按用户限流（默认每分钟 6 次）
        "sandbox_trigger": os.getenv("THROTTLE_SANDBOX_TRIGGER", "6/min"),
    },
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# P0-01：安全头（无条件）与可选 HTTPS 强化
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_HTTPS = _env_bool("SECURE_HTTPS", False)
if SECURE_HTTPS:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# 缓存：测试包用内存缓存，不依赖 Redis
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# P0-02：匿名业务面开关（生产默认关闭）
ENABLE_SIMPLE_API = _env_bool("ENABLE_SIMPLE_API", False)
ENABLE_ANONYMOUS_DOC_ANALYZE = _env_bool("ENABLE_ANONYMOUS_DOC_ANALYZE", False)

# P0-04：公网自助注册；未显式配置时跟随 DEBUG（生产默认关闭）
_allow_reg = os.getenv("ALLOW_PUBLIC_REGISTRATION")
if _allow_reg is None:
    ALLOW_PUBLIC_REGISTRATION = DEBUG
else:
    ALLOW_PUBLIC_REGISTRATION = _allow_reg.strip().lower() in ("1", "true", "yes", "on")

# P0-05：PRO 沙盒触发；未显式配置时跟随 DEBUG（生产默认关闭，本地开发保持可用）
_enable_sandbox = os.getenv("ENABLE_PRO_SANDBOX")
if _enable_sandbox is None:
    ENABLE_PRO_SANDBOX = DEBUG
else:
    ENABLE_PRO_SANDBOX = _enable_sandbox.strip().lower() in ("1", "true", "yes", "on")

# P0-06（修正）：公网 API 挂载开关。CET/知识库/问答默认开；其余默认关。
# english_learning 与 CET 无 import 依赖，默认关闭 HTTP 入口（app 仍在 INSTALLED_APPS，供 chat 可选引用）。
ENABLE_CET_API = _env_bool("ENABLE_CET_API", True)
ENABLE_ENGLISH_LEARNING_API = _env_bool("ENABLE_ENGLISH_LEARNING_API", False)
ENABLE_WORKFLOWS_API = _env_bool("ENABLE_WORKFLOWS_API", False)
ENABLE_AGENTS_API = _env_bool("ENABLE_AGENTS_API", False)
ENABLE_SKILLS_API = _env_bool("ENABLE_SKILLS_API", False)
ENABLE_SCAR_API = _env_bool("ENABLE_SCAR_API", False)

# P0-08：免费日配额与全局 token 预算（UsageDaily）
USER_DAILY_ASK_LIMIT = int(os.getenv("USER_DAILY_ASK_LIMIT", "50"))
_global_tok = os.getenv("GLOBAL_DAILY_TOKEN_BUDGET", "").strip()
GLOBAL_DAILY_TOKEN_BUDGET = int(_global_tok) if _global_tok else None

# AI 问答
AI_ENGINE_CONFIG = {
    "deepseek": {
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "base_url": "https://api.deepseek.com/v1/chat/completions",
        "model_name": "deepseek-chat",
        "max_tokens": 4000,
        "temperature": 0.7,
    },
    "qwen": {
        "api_key": os.getenv("QWEN_API_KEY", ""),
        "base_url": "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
        "model_name": "qwen-turbo",
        "max_tokens": 2000,
        "temperature": 0.7,
    },
    "glm": {
        "api_key": os.getenv("GLM_API_KEY", ""),
        "base_url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "model_name": "glm-4",
        "max_tokens": 2000,
        "temperature": 0.7,
    },
}
VECTORIZATION_SERVICE_URL = os.getenv("VECTORIZATION_SERVICE_URL", "http://127.0.0.1:8001")

# 知识库「单文件 / 分片合并后」文档大小上限（字节）。默认 100MB；可用 KNOWLEDGE_UPLOAD_MAX_BYTES 调整。
try:
    KNOWLEDGE_UPLOAD_MAX_BYTES = int(
        os.getenv("KNOWLEDGE_UPLOAD_MAX_BYTES", str(100 * 1024 * 1024)) or str(100 * 1024 * 1024)
    )
except (TypeError, ValueError):
    KNOWLEDGE_UPLOAD_MAX_BYTES = 100 * 1024 * 1024

# 分片上传时「单次请求」正文上限（字节）。每片须小于等于该值，便于网关与内存控制；默认 8MB。
try:
    KNOWLEDGE_CHUNK_MAX_BYTES = int(
        os.getenv("KNOWLEDGE_CHUNK_MAX_BYTES", str(8 * 1024 * 1024)) or str(8 * 1024 * 1024)
    )
except (TypeError, ValueError):
    KNOWLEDGE_CHUNK_MAX_BYTES = 8 * 1024 * 1024

# Skill 白名单：read_local_file 仅允许读取以下目录（绝对路径）
SKILL_FILE_WHITELIST_ENV = os.getenv("SKILL_FILE_WHITELIST", "")
SKILL_FILE_WHITELIST = [p.strip() for p in SKILL_FILE_WHITELIST_ENV.split(",") if p.strip()]

# Skill 自进化 JSON 履历目录（默认：BASE_DIR/data/skill_evolutions）
SKILL_EVOLUTION_DATA_DIR = os.getenv("SKILL_EVOLUTION_DATA_DIR", "")

# Agent 进化提案：同一 Agent 两次分析最小间隔（秒），避免每轮对话都写库
try:
    AGENT_EVOLUTION_MIN_INTERVAL_SECONDS = int(os.getenv("AGENT_EVOLUTION_MIN_INTERVAL_SECONDS", "300") or "300")
except (TypeError, ValueError):
    AGENT_EVOLUTION_MIN_INTERVAL_SECONDS = 300

# Skill：permission_level=system 时是否禁止参与自进化调度（默认禁止）
FORBID_SYSTEM_SKILL_EVOLUTION = os.getenv("FORBID_SYSTEM_SKILL_EVOLUTION", "true").lower() in (
    "1",
    "true",
    "yes",
)

# 内容安全：敏感词 / 有害内容 / 越狱提示（学校合规检测）
CONTENT_SAFETY_ENABLED = os.getenv("CONTENT_SAFETY_ENABLED", "true").lower() in ("1", "true", "yes")
CONTENT_SAFETY_CHECK_OUTPUT = os.getenv("CONTENT_SAFETY_CHECK_OUTPUT", "true").lower() in ("1", "true", "yes")
CONTENT_SAFETY_AUDIT_ENABLED = os.getenv("CONTENT_SAFETY_AUDIT_ENABLED", "true").lower() in ("1", "true", "yes")
CONTENT_SAFETY_KEYWORDS_PATH = os.getenv("CONTENT_SAFETY_KEYWORDS_PATH", "").strip() or None
CONTENT_SAFETY_MAX_TEXT_LEN = int(os.getenv("CONTENT_SAFETY_MAX_TEXT_LEN", "32000") or "32000")
# 可选：{"category": ["词1", "词2"]} 追加词表（覆盖 settings 模块内 dict 时需代码注入；推荐改 keywords.json）
CONTENT_SAFETY_EXTRA_KEYWORDS = None

# SCAR：结构编译 Agentic RAG（默认关闭，不破坏现网 hybrid 路径）
SCAR_ENABLED = os.getenv("SCAR_ENABLED", "false").lower() in ("1", "true", "yes")
# DS-RAG 旁路（默认关；请求 dsrag_mode=true 或本开关开启时走 apps.dsrag）
DSRAG_ENABLED = os.getenv("DSRAG_ENABLED", "false").lower() in ("1", "true", "yes")
DSRAG_DEFAULT_CONFIG = os.getenv("DSRAG_DEFAULT_CONFIG", "R3").strip() or "R3"
SCAR_DEFAULT_DOMAIN = os.getenv("SCAR_DEFAULT_DOMAIN", "construction").strip() or "construction"
SCAR_RETRIEVE_MAX_STEPS = int(os.getenv("SCAR_RETRIEVE_MAX_STEPS", "6") or "6")
SCAR_EVAL_FREEZE = os.getenv("SCAR_EVAL_FREEZE", "true").lower() in ("1", "true", "yes")
# 消融：scar_no_structure / scar_no_open（评测用，产品默认空）
SCAR_ABLATION = os.getenv("SCAR_ABLATION", "").strip().lower()

# 定向自进化：领域白名单（私有知识库 + 纯文字处理；见《自进化 Skill 与 Agent 的定向控制方案》）
_ev_domains_raw = os.getenv(
    "EVOLUTION_ALLOWED_DOMAINS",
    "qa_enhancement,summary,citation,format_extraction,law,paper_writing,novel_writing,education,scar_retrieval",
)
EVOLUTION_ALLOWED_DOMAINS = frozenset(
    x.strip().lower() for x in _ev_domains_raw.split(",") if x.strip()
)
EVOLUTION_ENFORCE_DOMAIN_GUARD = os.getenv("EVOLUTION_ENFORCE_DOMAIN_GUARD", "true").lower() in (
    "1",
    "true",
    "yes",
)
# 可选：追加禁区关键词（元组/列表，不设则用 guard 模块默认）
EVOLUTION_FORBIDDEN_MARKERS = None

# 产品档位（预留）：当前默认普通用户版；后续 VIP 增值能力可在此开关下扩展，未实现前与 standard 行为一致
_tier = os.getenv("PRODUCT_TIER", "standard").strip().lower()
PRODUCT_TIER = _tier if _tier in ("standard", "vip") else "standard"
PRO_UPGRADE_URL = os.getenv("PRO_UPGRADE_URL", "").strip()
PRO_UPGRADE_CALLBACK_URL = os.getenv("PRO_UPGRADE_CALLBACK_URL", "").strip()

# P3-T31：埋点与 A/B 开关
ANALYTICS_ENABLED = os.getenv("ANALYTICS_ENABLED", "true").lower() in ("1", "true", "yes")

# skill_creator：是否仅管理员可触发。当前默认 false（普通用户可用）；生产若需收紧可设 true 或后续结合 PRODUCT_TIER
SKILL_CREATOR_REQUIRE_STAFF = os.getenv("SKILL_CREATOR_REQUIRE_STAFF", "false").lower() in (
    "1",
    "true",
    "yes",
)

# Skill 执行超时（秒），0 表示不限制
try:
    _t = int(os.getenv("SKILL_EXECUTION_TIMEOUT", "60") or "0")
    SKILL_EXECUTION_TIMEOUT = _t if _t > 0 else None
except (TypeError, ValueError):
    SKILL_EXECUTION_TIMEOUT = 60

# Celery：测试包 / Docker 默认无独立 worker，用「同步执行任务」使 import-json 等可用。
# 生产若部署 Redis + celery worker，可设 CELERY_TASK_ALWAYS_EAGER=false 与 CELERY_BROKER_URL。
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "memory://")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = os.getenv(
    "CELERY_TASK_ALWAYS_EAGER", "true"
).lower() in ("1", "true", "yes")
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_TRACK_STARTED = True
CELERY_PRO_SANDBOX_QUEUE = os.getenv("CELERY_PRO_SANDBOX_QUEUE", "pro_sandbox")
CELERY_TASK_ROUTES = {
    # P3-T22：可选把沙盒任务单独放到 pro_sandbox 队列，由独立 worker 消费。
    "apps.skills.tasks.pro_sandbox_simulation": {"queue": CELERY_PRO_SANDBOX_QUEUE},
    "apps.skills.tasks.run_pro_sandbox_daily": {"queue": CELERY_PRO_SANDBOX_QUEUE},
}
CELERY_BEAT_SCHEDULE = {}
# P0-05：仅当 ENABLE_PRO_SANDBOX 开启时注册沙盒日更 beat（生产默认关）
if ENABLE_PRO_SANDBOX:
    CELERY_BEAT_SCHEDULE["pro-sandbox-daily"] = {
        "task": "apps.skills.tasks.run_pro_sandbox_daily",
        "schedule": crontab(
            hour=int(os.getenv("PRO_SANDBOX_DAILY_HOUR", "3")),
            minute=int(os.getenv("PRO_SANDBOX_DAILY_MINUTE", "0")),
        ),
        "kwargs": {
            "limit_per_user": int(os.getenv("PRO_SANDBOX_LIMIT_PER_USER", "8")),
            "max_users": int(os.getenv("PRO_SANDBOX_MAX_USERS", "20")),
        },
    }
# F4：英语学习主动提示占位 beat（需 worker+beat；默认关闭避免多一条周期任务）
if os.getenv("ENGLISH_REMINDER_BEAT", "").lower() in ("1", "true", "yes"):
    CELERY_BEAT_SCHEDULE["english-learning-reminder-tick"] = {
        "task": "apps.english_learning.tasks.english_reminder_tick",
        "schedule": crontab(
            hour=int(os.getenv("ENGLISH_REMINDER_HOUR", "9")),
            minute=int(os.getenv("ENGLISH_REMINDER_MINUTE", "0")),
        ),
    }

# Phase-C G1：LangGraph POC checkpointer（auto=Postgres 主库若可用，否则 Sqlite，再否则内存）
ENGLISH_LEARNING_LANGGRAPH_CHECKPOINTER = os.getenv(
    "ENGLISH_LEARNING_LANGGRAPH_CHECKPOINTER",
    "auto",
).strip().lower()
ENGLISH_LEARNING_LANGGRAPH_POSTGRES_USE_MAIN_DB = os.getenv(
    "ENGLISH_LEARNING_LANGGRAPH_POSTGRES_USE_MAIN_DB",
    "true",
).lower() in ("1", "true", "yes", "on")
# phase 变更时自动单步推进 LangGraph POC 直至与 phase 推断游标对齐（失败不阻断 merge）
ENGLISH_LEARNING_LANGGRAPH_AUTO_SYNC = os.getenv(
    "ENGLISH_LEARNING_LANGGRAPH_AUTO_SYNC",
    "true",
).lower() in ("1", "true", "yes", "on")
ENGLISH_LEARNING_LANGGRAPH_SQLITE_PATH = os.getenv(
    "ENGLISH_LEARNING_LANGGRAPH_SQLITE_PATH",
    str(BASE_DIR / "var" / "english_learning_langgraph.sqlite"),
)
