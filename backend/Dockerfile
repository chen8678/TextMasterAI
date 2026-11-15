# 日本网络通常可用 python:3.9-slim；Docker Hub 超时时改用 docker.1ms.run/library/python:3.9-slim
FROM docker.1ms.run/library/python:3.9-slim

WORKDIR /app

RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-minimal.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple/ -r requirements-minimal.txt

COPY . .
RUN mkdir -p logs media static

ENV PYTHONPATH=/app
ENV DJANGO_SETTINGS_MODULE=ai_qa_system.settings
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["sh", "-c", "python manage.py makemigrations || true && python manage.py migrate --noinput && python manage.py init_skills_agents || true && python manage.py runserver 0.0.0.0:8000"]
