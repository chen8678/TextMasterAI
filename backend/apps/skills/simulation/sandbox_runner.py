"""
PRO 沙盒 runner（最小可运行版，P2-T22 起点）：
- 输入采样片段
- 组装简版候选草案（markdown）
- 交由现有 guard 过滤
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import List

from apps.skills.evolution.guard import draft_markdown_allowed
from apps.chat.ai_services import AIServiceFactory
from .test_generator import SampleCase


@dataclass
class SandboxResult:
    accepted: bool
    reason: str
    markdown: str
    used_cases: int


def _build_candidate_markdown(cases: List[SampleCase]) -> str:
    lines = [
        "## [PRO 沙盒草案] 检索与回答策略补充",
        "",
        "- 回答前优先复述用户目标与约束（风格、格式、长度）。",
        "- 证据不足时明确标注“不确定”，并给出可执行补充信息建议。",
        "- 在引用时优先返回文档标题，必要时附关键原句片段。",
        "",
        "### 采样证据（节选）",
    ]
    for i, c in enumerate(cases[:5], start=1):
        lines.extend(
            [
                f"{i}. 文档：{c.title or c.doc_id}",
                f"   片段：{c.snippet[:180]}",
            ]
        )
    return "\n".join(lines).strip()


def _judge_candidate_with_llm(candidate: str, cases: List[SampleCase]) -> tuple[bool, str]:
    key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        return True, "no_api_key_skip_judge"
    try:
        svc = AIServiceFactory.create_service("deepseek-chat", key)
    except Exception:
        return True, "judge_init_failed"
    evidence = "\n".join(f"- {c.title}: {c.snippet[:120]}" for c in cases[:6])
    prompt = (
        "你是文字准确性审查器。请判断候选草案是否与证据一致，"
        "且没有多模态/越权内容。只输出一行 JSON："
        '{"pass": true/false, "reason": "..." }\n'
        f"证据:\n{evidence}\n\n候选草案:\n{candidate[:2500]}"
    )
    raw = svc.generate_response([{"role": "user", "content": prompt}])
    text = (raw or "").strip().lower()
    if '"pass": false' in text or '"pass":false' in text:
        return False, "judge_rejected"
    return True, "judge_passed"


def run_sandbox(cases: List[SampleCase]) -> SandboxResult:
    if not cases:
        return SandboxResult(
            accepted=False,
            reason="no_cases",
            markdown="",
            used_cases=0,
        )
    candidate = _build_candidate_markdown(cases)
    judge_ok, judge_reason = _judge_candidate_with_llm(candidate, cases)
    if not judge_ok:
        return SandboxResult(
            accepted=False,
            reason=judge_reason,
            markdown="",
            used_cases=len(cases),
        )
    ok, reason = draft_markdown_allowed(candidate)
    return SandboxResult(
        accepted=ok,
        reason=reason if ok else f"{judge_reason}:{reason}",
        markdown=candidate if ok else "",
        used_cases=len(cases),
    )

