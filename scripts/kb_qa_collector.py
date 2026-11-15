#!/usr/bin/env python3
"""
KB 问答采集器 — 通过 HTTP API 驱动工作流（适合 n8n / cron / 外部编排）。

用法示例：
  python scripts/kb_qa_collector.py \\
    --base-url http://localhost:8010 \\
    --username your_user --password your_pass \\
    --kb-id <uuid> \\
    --config backend/data/training_collector/sample_workflow.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import requests
except ImportError:
    print("请先安装 requests: pip install requests", file=sys.stderr)
    sys.exit(1)


def login(base_url: str, username: str, password: str) -> str:
    url = f"{base_url.rstrip('/')}/api/v1/auth/login/"
    resp = requests.post(url, json={"username": username, "password": password}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    token = data.get("access")
    if not token:
        raise RuntimeError(f"登录失败，未返回 access token: {data}")
    return token


def run_collector(
    base_url: str,
    token: str,
    kb_id: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/v1/workflows/kb-qa-collector/run/"
    headers = {"Authorization": f"Bearer {token}"}
    body = {"knowledge_base_id": kb_id, **payload}
    resp = requests.post(url, headers=headers, json=body, timeout=600)
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    if resp.status_code >= 400:
        raise RuntimeError(f"API {resp.status_code}: {data}")
    return data


def load_config(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    parser = argparse.ArgumentParser(description="KB 问答采集器（API 驱动）")
    parser.add_argument("--base-url", default="http://localhost:8010", help="后端 Base URL")
    parser.add_argument("--username", required=True, help="登录用户名")
    parser.add_argument("--password", required=True, help="登录密码")
    parser.add_argument("--kb-id", required=True, help="知识库 UUID")
    parser.add_argument(
        "--config",
        default="backend/data/training_collector/sample_workflow.json",
        help="工作流配置 JSON",
    )
    parser.add_argument("--questions", nargs="*", default=[], help="覆盖配置中的内联问题")
    parser.add_argument("--dry-run", action="store_true", help="只解析问题，不调用 KB")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.questions:
        cfg["questions"] = args.questions
    if args.dry_run:
        cfg["dry_run"] = True

    payload = {
        "questions": cfg.get("questions"),
        "question_source": cfg.get("question_source", "inline"),
        "seed_path": cfg.get("seed_path", ""),
        "llm_question_count": cfg.get("llm_question_count", 0),
        "agent_id": cfg.get("agent_id", "qa"),
        "ai_model": cfg.get("ai_model", "deepseek"),
        "config": cfg.get("config") or {},
        "retrieval_params": cfg.get("retrieval_params"),
        "instruction": cfg.get("instruction", ""),
        "delay_seconds": cfg.get("delay_seconds", 0.5),
        "max_questions": cfg.get("max_questions", 50),
        "output_path": cfg.get("output_path", ""),
        "dry_run": bool(cfg.get("dry_run", False)),
    }

    token = login(args.base_url, args.username, args.password)
    result = run_collector(args.base_url, token, args.kb_id, payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
