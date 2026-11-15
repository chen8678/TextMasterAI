"""DS-RAG 配置加载与 policy_hash（P05）。不硬编码密钥；业务常数来自 yaml。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent
CONFIGS_DIR = APP_DIR / "configs"
# 仓库根：.../backend/apps/dsrag → parents[2]
REPO_ROOT = APP_DIR.parents[2]


def _minimal_yaml_load(text: str) -> Any:
    """无 PyYAML 时的受限解析：支持嵌套 dict、标量、简单 list。"""
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lines.append(raw.rstrip())

    def parse_scalar(s: str) -> Any:
        s = s.strip()
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1]
        if s.startswith("'") and s.endswith("'"):
            return s[1:-1]
        if s in ("true", "True"):
            return True
        if s in ("false", "False"):
            return False
        if s in ("null", "Null", "~", ""):
            return None
        try:
            if "." in s:
                return float(s)
            return int(s)
        except ValueError:
            return s

    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]

    i = 0
    while i < len(lines):
        line = lines[i]
        indent = len(line) - len(line.lstrip(" "))
        content = line.lstrip(" ")

        while stack and indent <= stack[-1][0]:
            if len(stack) == 1:
                break
            if indent == stack[-1][0] and content.startswith("- "):
                break
            if indent <= stack[-1][0] and not content.startswith("- "):
                stack.pop()
                continue
            break

        parent = stack[-1][1]

        if content.startswith("- "):
            item_raw = content[2:].strip()
            if isinstance(parent, list):
                if ":" in item_raw and not item_raw.startswith("{"):
                    # list of dicts starting
                    key, _, val = item_raw.partition(":")
                    d: dict[str, Any] = {key.strip(): parse_scalar(val)}
                    parent.append(d)
                    stack.append((indent, d))
                else:
                    parent.append(parse_scalar(item_raw))
            i += 1
            continue

        if ":" not in content:
            i += 1
            continue
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        if not isinstance(parent, dict):
            i += 1
            continue

        if rest == "":
            # peek next
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            nindent = len(nxt) - len(nxt.lstrip(" ")) if nxt else indent
            if nxt.lstrip().startswith("- "):
                lst: list[Any] = []
                parent[key] = lst
                stack.append((indent, lst))
            else:
                child: dict[str, Any] = {}
                parent[key] = child
                stack.append((indent, child))
        else:
            parent[key] = parse_scalar(rest)
        i += 1

    return root


def load_yaml(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
    except ImportError:
        data = _minimal_yaml_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"config root must be mapping: {path}")
    return data


def resolve_path(p: str | Path, *, base: Path | None = None) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path
    base = base or REPO_ROOT
    return (base / path).resolve()


def load_base_config(path: Path | str | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else CONFIGS_DIR / "base.yaml"
    cfg = load_yaml(cfg_path)
    # 解析相对仓库根的路径键
    for key in ("corpus_chunks", "index_dir", "taskset", "scope_spec"):
        if key in cfg and isinstance(cfg[key], str):
            cfg[f"{key}_resolved"] = str(resolve_path(cfg[key]))
    cfg["_config_path"] = str(cfg_path.resolve())
    return cfg


def load_policy(path: Path | str | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else CONFIGS_DIR / "policy_dev.yaml"
    policy = load_yaml(cfg_path)
    policy["_config_path"] = str(cfg_path.resolve())
    return policy


def compute_policy_hash(
    *,
    policy: dict[str, Any],
    base: dict[str, Any],
    prompt_version: str = "v0",
) -> str:
    """阈值 + 模型名 + 提示版本 → 稳定 sha256 前 16 位。"""
    payload = {
        "score_threshold": policy.get("score_threshold"),
        "answerable_threshold": policy.get("answerable_threshold"),
        "scope_threshold": policy.get("scope_threshold"),
        "policy_version": policy.get("policy_version"),
        "generator_model": base.get("generator_model"),
        "answerable_model": base.get("answerable_model"),
        "embedding_model": base.get("embedding_model"),
        "top_k": base.get("top_k"),
        "temperature": base.get("temperature"),
        "max_tokens": base.get("max_tokens"),
        "prompt_version": prompt_version or policy.get("prompt_version") or "v0",
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def make_run_id(config_id: str, split: str, yyyymmdd: str | None = None) -> str:
    """命名：{config}_{split}_{YYYYMMDD}"""
    from datetime import datetime, timezone

    day = yyyymmdd or datetime.now(timezone.utc).strftime("%Y%m%d")
    cfg = re.sub(r"[^A-Za-z0-9_-]+", "", config_id)
    sp = re.sub(r"[^A-Za-z0-9_-]+", "", split)
    return f"{cfg}_{sp}_{day}"


def load_merged(*, base_path: Path | str | None = None, policy_path: Path | str | None = None) -> dict[str, Any]:
    base = load_base_config(base_path)
    policy = load_policy(policy_path)
    prompt_version = str(policy.get("prompt_version") or base.get("prompt_version") or "v0")
    ph = compute_policy_hash(policy=policy, base=base, prompt_version=prompt_version)
    return {
        "base": base,
        "policy": policy,
        "policy_hash": ph,
        "prompt_version": prompt_version,
    }
