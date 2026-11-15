# 本地开发：基础设施用 Docker，前后端本机运行

适用于：**不封装应用 Docker 镜像**，仅在 Docker 中跑 **PostgreSQL（pgvector）** 与 **向量化服务**，Django 与 Vite 在宿主机启动。

## 1. Phase 1 实现状态（简要）

- **代码与文档**：执行清单中 **P1-T01～T31、T40～T42** 已落地；**P1-T32** 为你在本环境的**走查验收**（见 `docs/PHASE1_E2E_CHECKLIST.md`）。
- **本指南**：帮你先把「库 + 向量服务 + 本机 API + 前端」跑通，再走 P1-T32。

## 2. 先起 Docker 基础设施（Postgres + 向量化）

向量化服务已内置在仓库 **`services/vectorization/`**（FastAPI + sentence-transformers，默认 **BAAI/bge-large-zh-v1.5**），由 Compose **本地构建** 为 `text-master-vectorization:local`。

### 2.1 能访问 Docker Hub 时

```bash
docker compose -f docker-compose.infra.yml build
docker compose -f docker-compose.infra.yml up -d
```

### 2.2 `registry-1.docker.io` 超时（Head manifest DeadlineExceeded）

这是 **拉不到 Docker Hub**（网络或墙），与业务代码无关。任选其一：

**方式 A：Docker Desktop 配置镜像加速（推荐，一劳永逸）**  
设置 → Docker Engine → 在 JSON 里增加 `registry-mirrors`（如阿里云、DaoCloud 控制台给你的专属加速地址），应用并重启 Docker。

**方式 B：用仓库提供的 Hub 代理前缀（先试 DaoCloud 公共前缀）**

```bash
cp docker/infra-mirror.env.example docker/infra-mirror.env
# 若需微调镜像名，编辑 infra-mirror.env
docker compose --env-file docker/infra-mirror.env -f docker-compose.infra.yml build
docker compose --env-file docker/infra-mirror.env -f docker-compose.infra.yml up -d
```

该文件会设置 `VECTORIZATION_BASE_IMAGE`、`POSTGRES_IMAGE` 为 **`docker.m.daocloud.io/...`** 前缀，避免直连 Hub。若仍失败，请换你环境可用的镜像站或 **方式 A**。

**方式 C：仅覆盖向量化基础镜像**

```bash
export VECTORIZATION_BASE_IMAGE=docker.m.daocloud.io/library/python:3.11-slim-bookworm
docker compose -f docker-compose.infra.yml build vectorization
```

检查：

```bash
docker compose -f docker-compose.infra.yml ps
docker compose -f docker-compose.infra.yml logs -f vectorization
curl -s http://127.0.0.1:8001/health
```

说明：

- **PostgreSQL**：镜像 **`pgvector/pgvector:pg15`**（从 Docker Hub 拉取），宿主机端口 **`5433`** → 容器 `5432`。
- **向量化**：默认 **`HF_ENDPOINT=https://hf-mirror.com`**（在 `docker-compose.infra.yml` 中），减轻国内直连 `huggingface.co` 超时。若仍失败，服务会启用 **1024 维确定性降级嵌入**（`embedding_backend: "fallback"`），保证 `/health` 与接口可用，但语义检索质量差；网络/镜像正常后重启容器以加载真实 BGE 模型。  
  **注意**：勿传 **`HF_ENDPOINT=` 空串**。
- 若仅想先验证数据库、暂时不取向量化：可临时在 override 里去掉 `vectorization` 服务；后端会走**降级向量**，检索质量会下降。

实现细节见：`services/vectorization/Dockerfile`、`services/vectorization/app.py`。

## 3. 后端（Django）

在 **`backend/`** 下配置 **`.env`**（可复制仓库根目录 `.env.example` 并改名/合并到 `backend/.env`）：

```env
SECRET_KEY=本地开发可任意长随机串
DEBUG=True
DATABASE_URL=postgresql://postgres:password@127.0.0.1:5433/ai_qa_system
VECTORIZATION_SERVICE_URL=http://127.0.0.1:8001
DEEPSEEK_API_KEY=你的_key
CORS_ALLOWED_ORIGINS=http://localhost:3009,http://127.0.0.1:3009
```

密码需与 `docker-compose.infra.yml` 中 `POSTGRES_PASSWORD` 一致（默认 `password`）。

执行：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py init_skills_agents
python manage.py runserver 0.0.0.0:8000
```

自检：

```bash
python manage.py check
curl -s http://127.0.0.1:8000/api/v1/system/health/
```

## 4. 前端（Vite）

```bash
cd frontend
npm ci
npm run dev
```

默认 **`http://localhost:3009`**，`vite.config.ts` 已将 `/api` 代理到 `http://127.0.0.1:8000`。

## 5. 建议测试步骤（对齐 P1-T32）

1. 浏览器打开 `http://localhost:3009/`，标题含 **Text Master AI**。
2. **注册 / 登录**，侧栏可见「智能问答」「知识库」等。
3. **知识库**：新建知识库 → 上传纯文本或支持格式的文档 → 执行向量化（若 8001 正常，应无持续报错）。
4. **智能问答**：选知识库 + Agent → 多轮提问，答案合理。
5. （可选）Staff 用户：**Django Admin** 或 `/admin/self-evolution` 与自进化流程。

详细勾选表：`docs/PHASE1_E2E_CHECKLIST.md`。

## 6. 常见问题

| 现象 | 处理 |
|------|------|
| `connection to server ... refused` | 确认 Postgres 容器健康、`DATABASE_URL` 端口为 **5433**。 |
| 向量化失败 / 8001 不通 | 检查 `vectorization` 容器日志；确认镜像存在且 `VECTORIZATION_SERVICE_URL` 正确。 |
| 迁移报 pgvector | 使用 `pgvector/pgvector` 镜像；已存在旧数据卷时，可在库内执行 `CREATE EXTENSION vector;`。 |

---

*与 `docs/DEPLOY.md` 互补：全文部署见 DEPLOY；本文件专注「库与向量 Docker + 本机前后端」。*
