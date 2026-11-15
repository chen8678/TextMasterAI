# Text Master AI

私有知识库文字工作台（前后端代码与 Docker 部署配置）。

## 目录

- `backend/` — Django + DRF
- `frontend/` — Vue 3
- `services/vectorization/` — 向量化微服务
- `docker-compose.yml` — 一体化部署
- `docs/` — 部署与本地开发说明

## 快速启动

```bash
cp .env.example .env
# 填写 DEEPSEEK_API_KEY、SECRET_KEY、数据库密码等
docker compose up -d --build
```

- 前端默认：http://localhost:3009
- 后端默认：http://localhost:8000

详见 `docs/DEPLOY.md`、`docs/LOCAL_DEV.md`。
