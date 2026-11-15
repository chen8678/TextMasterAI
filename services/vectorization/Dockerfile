# 文本向量化微服务（与 backend vectorization_client 契约一致）
# 无法直连 Docker Hub 时，构建传入：--build-arg BASE_IMAGE=docker.m.daocloud.io/library/python:3.11-slim-bookworm
# 或在 compose 中设置 VECTORIZATION_BASE_IMAGE（见 docker/infra-mirror.env.example）
ARG BASE_IMAGE=python:3.11-slim-bookworm
FROM ${BASE_IMAGE}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 先装 CPU 版 PyTorch，避免 sentence-transformers 拉 CUDA 大包
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV DEFAULT_MODEL_NAME=BAAI/bge-large-zh-v1.5 \
    TRANSFORMERS_CACHE=/app/models \
    HF_HOME=/app/models \
    HF_HUB_CACHE=/app/models

EXPOSE 8001

# 首次启动会从 HuggingFace 拉取模型（需网络；国内可配 HF_ENDPOINT 镜像）
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
