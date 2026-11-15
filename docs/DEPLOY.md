# Text Master AI 部署环境检查表（P1-T30）

> 与 `backend/ai_qa_system/settings.py` 及 `docker-compose.yml` 对照使用；部署前逐项勾选。

## 1. 数据库

| 检查项 | 说明 |
|--------|------|
| PostgreSQL 可连接 | `DATABASE_URL` 或 `HOST/PORT/USER/PASSWORD/NAME` |
| 扩展 `vector` | `knowledge` 迁移含 `0000_pgvector_extension`；全新库需能执行 `CREATE EXTENSION vector` |
| 迁移 | `cd backend && python manage.py migrate` |

## 2. 异步任务（Celery）

| 检查项 | 说明 |
|--------|------|
| 测试/单机 | `CELERY_TASK_ALWAYS_EAGER=true`（默认）同步执行任务 |
| 生产 | `CELERY_BROKER_URL`（如 Redis）、独立 worker；`CELERY_TASK_ALWAYS_EAGER=false` |
| **英语学习提醒 beat** | 可选；见 **§6.3 推荐生产**（`ENGLISH_REMINDER_BEAT=true` + `docker-compose.celery.yml`） |
| **向导长耗时 async** | `async=true` 需 §6.3 同一 Celery profile 的 worker |

## 3. AI 与向量化

| 环境变量 | 用途 |
|----------|------|
| `DEEPSEEK_API_KEY` | 问答与（可选）自进化 LLM |
| `VECTORIZATION_SERVICE_URL` | 文档向量化服务（默认 `http://127.0.0.1:8001`） |
| `SKILL_EVOLUTION_USE_LLM` / `AGENT_EVOLUTION_USE_LLM` | 设为 `true` 时启用对应 LLM 路径 |

## 4. 自进化与定向策略

| 环境变量 | 说明 |
|----------|------|
| `EVOLUTION_ALLOWED_DOMAINS` | 逗号分隔领域白名单 |
| `EVOLUTION_ENFORCE_DOMAIN_GUARD` | 默认 `true` |
| `FORBID_SYSTEM_SKILL_EVOLUTION` | 默认禁止 system 级 Skill 调度自进化 |
| `PRODUCT_TIER` | `standard` \| `vip`（预留） |

## 5. 前端

```bash
cd frontend && npm ci && npm run build
```

静态资源由 Nginx 或 Django `collectstatic` 按实际架构部署。

**MEDIA（P0-01）**：`apps/` 下无 Django `models.FileField`/`ImageField`；`MEDIA_URL` 仅在 `settings.DEBUG` 时由 `urls.py` 挂载，故生产 `DEBUG=False` 后访问 `/media/` 返回 404 属预期。不要为此新增 nginx `/media/` 静态目录。

## 6. 预置数据

```bash
cd backend && python manage.py init_skills_agents
```

## 6.1 向量化微服务（本仓库内置）

镜像由 **`services/vectorization/`** 构建（`docker-compose.yml` / `docker-compose.infra.yml` 中 `vectorization.build`），**非** Docker Hub 上的 `chen-ai-vectorization`。首次运行需从 Hugging Face 拉取嵌入模型，见 `docs/LOCAL_DEV.md`。

## 6.2 英语学习 LangGraph 向导（Phase-C）

| 检查项 | 说明 |
|--------|------|
| `langgraph` 已安装 | Docker 使用 `backend/requirements-minimal.txt`（含 `langgraph` + checkpoint）；容器内：`python -c "import langgraph"` |
| 向导 API | `POST /api/v1/english-learning/graph/wizard/start/` 非 503 |
| 流式 resume | `POST .../graph/wizard/resume/stream/` 返回 `text/event-stream` |
| 端口 | 宿主机后端常为 **`BACKEND_HOST_PORT=8010`**（`.env`）；健康检查 `http://localhost:8010/api/v1/system/health/` |
| 前端向导 | `http://localhost:3009/english-learning`；开发调试加 **`?dev=1`** |
| 长耗时异步 | `resume` body 传 `async=true` + Celery profile（`docker-compose.celery.yml`）；UI 默认走 SSE 同步流 |

镜像变更后重建 backend：

```bash
docker compose up -d --build backend
```

### 6.2.1 向导 resume：SSE 为主 / async 备选（G3 决策，2026-05-29）

| 路径 | 端点 | 生产角色 | 前端 |
|------|------|----------|------|
| **主路径（默认）** | `POST …/graph/wizard/resume/stream/` | 同步 HTTP + **SSE**；推送 `start` / `node_done` / `token` / `interrupt` / `end` | `EnglishLearningWizard.vue` → `wizardResumeViaStream`（四步全用） |
| **同步 JSON** | `POST …/graph/wizard/resume/` | 一次返回 `wizard_graph`；**无**进度事件 | 仅 `?dev=1` 或脚本；**勿与 stream 混用同一会话**（verify 曾见 `missing profile_id`） |
| **异步 Celery** | `POST …/graph/wizard/resume/` + `async=true` | **202** + `task_id`；worker 跑 `english_graph_wizard_resume_task` | **未接**；无轮询 UI；集成方自建 poll |

**结论**

- **不**将 Celery 整图 resume 设为默认；长耗时步骤的进度与 G3+ token 依赖 **SSE 单连接**。
- `async=true` 保留给：运维脚本、未来后台批处理、或超时网关后的可选集成；启用需 §6.3 Celery profile + `CELERY_TASK_ALWAYS_EAGER=false`。
- `resume/stream/` **忽略** body 中的 `async`（见 `views.graph_wizard_resume_stream`）。
- 单节点异步仍可用 `POST …/graph/run-node/` + `async=true`（`english_graph_run_node_task`），与整图 resume 无关。

**验收**：`python manage.py test apps.english_learning.tests.test_wizard_sse --keepdb`；live stream 勿在中间插入 sync `resume/`。

## 6.3 MVP-B：英语学习提醒 Celery Beat（推荐生产）

> **默认主栈**：`memory://` broker + `CELERY_TASK_ALWAYS_EAGER=true`，**不**跑独立 beat。  
> `GET /english-learning/today/` 仍按打开页面/规则返回任务；本节用于需要 **每日定时** `english_reminder_tick` 的生产/预发。

### 何时启用

| 场景 | 建议 |
|------|------|
| 本地开发 / 单测 | **不必**启 beat；任务可 eager 同步执行 |
| 预发 / 生产需每日 tick | 启用本节配置 |
| 向导 `resume` 传 `async=true` | 需 **同一** Celery worker（§6.2），与 beat 共用 `docker-compose.celery.yml` |

### `GET /today/` 与 beat tick 职责边界（联调）

| 路径 | 触发 | 粒度 | 当前行为 | 典型消费者 |
|------|------|------|----------|------------|
| **`GET /api/v1/english-learning/today/`** | 用户**打开页面**（向导 Step0、`AgentChat` 英语条） | **按当前登录用户** | 读 `session_state` → `build_today_tasks` 规则任务；可选 `english_active_recall_pack`；回显 `reminder_prefs` / 免打扰 | 前端「今日任务」卡片 |
| **`english_reminder_tick`（beat）** | Celery beat **每日 crontab**（`ENGLISH_REMINDER_BEAT=true`） | **全库聚合** | 统计 `phase=tutor` 档案数并打日志；**不**写 session、**不**推送到前端 | 运维日志 / 后续推送占位 |

**联调要点**：today 卡片**不依赖** beat 即可展示（主栈无 Redis 亦可）；beat tick **不替代** today API，二者互补——today 负责即时 UI，tick 负责定时批处理/可观测。验证 today：`python manage.py test apps.english_learning.tests.test_today_api --keepdb`；验证 tick：见下文 Smoke。

### 环境变量（项目根 `.env` 示例）

```bash
CELERY_TASK_ALWAYS_EAGER=false
CELERY_BROKER_URL=redis://redis-celery:6379/0
CELERY_RESULT_BACKEND=redis://redis-celery:6379/1
ENGLISH_REMINDER_BEAT=true
# 可选：默认每天 09:00（settings.CELERY_BEAT_SCHEDULE）
ENGLISH_REMINDER_HOUR=9
ENGLISH_REMINDER_MINUTE=0
```

| 变量 | 说明 |
|------|------|
| `ENGLISH_REMINDER_BEAT` | `true` 时注册 beat 项 `english-learning-reminder-tick` → `english_reminder_tick` |
| `ENGLISH_REMINDER_HOUR` / `MINUTE` | crontab 时刻（默认 9:00） |
| `CELERY_TASK_ALWAYS_EAGER` | 生产 **必须** `false` |

任务实现：`backend/apps/english_learning/tasks.py`（统计 `phase=tutor` 档案数并打日志，后续可接推送）。

### 启动命令

主栈 + Redis + worker + beat（项目根目录）：

```bash
docker compose -f docker-compose.yml -f docker-compose.celery.yml --profile celery up -d --build
```

服务：`redis-celery`（宿主机 **6380**）、`celery-worker`、`celery-beat`。详见 `docker-compose.celery.yml` 文件头注释。

### Smoke 自检（F2 / V2）

```bash
# 1) 容器 healthy
docker compose -f docker-compose.yml -f docker-compose.celery.yml --profile celery ps

# 2) 手动跑一次 tick（在 worker 容器内）
docker compose -f docker-compose.yml -f docker-compose.celery.yml --profile celery exec celery-worker \
  python manage.py shell -c "from apps.english_learning.tasks import english_reminder_tick; print(english_reminder_tick())"

# 期望 stdout 含：{'ok': True, 'tutor_phase_profiles': N}
# 日志含：english_reminder_tick tutor_phase_profiles=

# 3) beat 已加载 schedule（日志中含 english-learning-reminder-tick 或 beat 启动无报错）
docker compose -f docker-compose.yml -f docker-compose.celery.yml --profile celery logs celery-beat --tail 30

# 4) 单测
cd backend && python manage.py test apps.english_learning.tests.test_celery_reminder_tick --keepdb
```

本地无 Docker 时，eager 模式可验证任务逻辑：

```bash
cd backend && CELERY_TASK_ALWAYS_EAGER=true python manage.py shell -c \
  "from apps.english_learning.tasks import english_reminder_tick; print(english_reminder_tick())"
```

**最近 smoke 记录**

| 轮次 | 日期 | 环境 | 结果摘要 |
|------|------|------|----------|
| H2 | 2026-05-31 | 本地 compose + celery profile | 7 服务 healthy；beat `english-learning-reminder-tick` 已调度；worker tick 日志；手动 tick OK |
| **R1** | 2026-05-31 | 本地预发栈复验（`/do R1`） | 7 服务 healthy；health 8010/3009；`ENGLISH_REMINDER_BEAT=true`；beat 启动无报错；手动 tick `{'ok': True, 'tutor_phase_profiles': 0}`；`test_celery_reminder_tick` 1 绿 |

> **上线前**：在**目标远程预发/生产**环境按上文 Smoke 清单再跑一轮，并追加一行到本表（本地 R1 不能替代）。

## 6.4 英语学习预置词库（小学 → 六级）

> **产品约定**：教材内容由系统预置；用户**无需上传**词库。个人 `英语学习 · {用户名}` 私库仅用于**学习路线定稿**。

### 何时执行

| 场景 | 建议 |
|------|------|
| 首次部署 / 云机上线 | **必须**：download → init → backfill |
| 升级词库 raw 文件后 | `init_english_curriculum --force`（会重建文档；生产先备份 DB） |
| 本地开发 | 可 `--skip-vectorize` 加速；联调 RAG 前需向量化 |

### 步骤

```bash
# 1) 下载开源词库（约 40MB，见 data/curriculum/SOURCES.md）
chmod +x scripts/download_english_curriculum_data.sh
./scripts/download_english_curriculum_data.sh

# 2) 导入 5 个系统 KB + 向量化（Docker 内示例）
docker compose exec backend python manage.py init_english_curriculum --backfill-users

# 开发加速（不向量化）：
# docker compose exec backend python manage.py init_english_curriculum --skip-vectorize --backfill-users
```

### Smoke

```bash
# 新用户应可见 5 预置 + 1 个人库
curl -sS -H "Authorization: Bearer $TOKEN" http://localhost:8010/api/v1/english-learning/curriculum/ \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('libraries',[])), d.get('recommended_knowledge_base_id'))"

cd backend && python manage.py test apps.english_learning.tests.test_curriculum --keepdb
```

**期望**：`libraries` 长度为 5；`recommended_knowledge_base_id` 非空；单测全绿。

**最近 smoke 记录**

| 轮次 | 日期 | 环境 | 结果摘要 |
|------|------|------|----------|
| **P0-do** | 2026-06-04 | 本地 | download 5 raw；init 196 docs（5 KB）；curriculum API smoke；`test_curriculum` 5 绿 |

## 7. 日志检索（Guard）

自进化拒绝日志含前缀 **`[evolution_guard]`**（见 `apps/skills/evolution/guard.py`）。检索示例：

```bash
# Docker 日志或应用 stdout
grep evolution_guard /path/to/app.log
```

## 8. 发布自检命令（P1-T31）

在**目标环境**按顺序执行（验证阶段将结果记入 `docs/PHASE1_E2E_CHECKLIST.md` 对应行）：

```bash
cd backend && python manage.py migrate --noinput
cd backend && python manage.py check
cd backend && python manage.py init_skills_agents
cd ../frontend && npm ci && npm run build
```

若生产由 Django 托管静态资源，按需增加：

```bash
cd backend && python manage.py collectstatic --noinput
```

**参考（开发机自检）**：`manage.py check` 应输出 `System check identified no issues`。

---

*文档随版本迭代更新。*
