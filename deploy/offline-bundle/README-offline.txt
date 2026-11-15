内网离线部署包说明（本机构建，SFTP 上传）
============================================

本目录内容
----------
1) frontend-dist/          —— 已构建的前端静态文件（本机 npm run build 产物副本）
2) python-wheels-linux/    —— 面向 Linux x86_64 + Python 3.9 的 wheel 包（与 backend/Dockerfile 一致）
3) requirements-offline-py39-linux.txt —— 与 requirements-minimal 对应，但：
   - openai 限制为 <2（2.x 需要 Python 3.10+）
   - 未包含 ifcopenshell（跨平台纯 wheel 打包易失败；不用 BIM 可忽略）

你需要额外 SFTP 的内容（不在本包内自动生成）
------------------------------------------
- 整个 backend/ 源码目录（勿覆盖服务器上的 .env）
- 若用 Docker：docker-compose.yml、docker/ 等（按你们线上方式）
- 若需 BIM：在一台「可联网的 Linux x86_64 + Python3.9」上执行：
    pip download "ifcopenshell>=0.8.0" -d ./extra-wheels \\
      --platform manylinux2014_x86_64 --python-version 39 \\
      --implementation cp --abi cp39 --only-binary=:all:
  将生成的 wheel 一并拷入内网 python-wheels-linux/

内网服务器（裸机 Python 示例）
----------------------------
  cd /path/to/app
  python3.9 -m venv .venv
  source .venv/bin/activate
  pip install --no-index --find-links=./python-wheels-linux \\
    -r requirements-offline-py39-linux.txt

  # 部署后端代码后：
  export DJANGO_SETTINGS_MODULE=ai_qa_system.settings
  python manage.py migrate --noinput
  # 重启 gunicorn/uwsgi（或 docker compose up -d）

前端静态文件
------------
  将 frontend-dist/ 内全部文件覆盖到 Nginx 的站点根目录（与线上一致）。

云机并行部署（第二套 3010 / 8010）
--------------------------------
详见仓库内：docs/CLOUD_PARALLEL_DEPLOY_V3010.md（端口表、SFTP 清单、命令）

注意
----
- 勿用本机 macOS 直接 pip download 不加平台参数的产物给 Linux 用（含 psycopg2-binary 等会装不上）。
- 勿覆盖服务器生产 .env、勿删除 PostgreSQL 数据目录；知识库数据在数据库中。
- 重新生成本包：在项目根执行 scripts/prepare-offline-bundle.sh（需本机可访问 PyPI）。
