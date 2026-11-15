"""
Meta Skill: 自动创建新的内置 Skill（最小可用版本）

能力：
1) 根据用户需求生成 skill_id / name / description
2) 在 apps.skills.builtin 下创建 <skill_id>.py
3) 自动更新 builtin/__init__.py 的 import + register
4) 写入 Skill 元数据并尝试热注册
"""
from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Tuple

from django.conf import settings
from django.utils import timezone

from apps.skills.models import Skill, SkillEvolutionStaging
from apps.skills.registry import SkillRegistry


# 与「纯文字知识库问答」无关的需求关键词（命中则拒绝创建）
_NON_TEXT_KB_BLOCK = (
    "文生图",
    "图生视频",
    "生成视频",
    "视频剪辑",
    "语音合成",
    "语音识别",
    "游戏引擎",
    "爬虫爬取",
    "爬取互联网",
    "stable diffusion",
    "midjourney",
    "多模态",
    "画图生成",
)

_TRIGGERS = [
    "创建skill",
    "创建技能",
    "新增skill",
    "新增技能",
    "生成skill",
    "生成技能",
]


def _question_implies_non_text_kb_scope(question: str) -> bool:
    q = question or ""
    return any(b in q for b in _NON_TEXT_KB_BLOCK)


def is_triggered(question: str) -> bool:
    q = (question or "").strip().lower().replace(" ", "")
    return any(k in q for k in _TRIGGERS)


def _to_skill_id(raw: str) -> str:
    value = (raw or "").strip().lower()
    value = re.sub(r"[^a-z0-9_\- ]+", "", value)
    value = value.replace("-", "_").replace(" ", "_")
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        value = "custom_skill"
    if not re.match(r"^[a-z_][a-z0-9_]{1,63}$", value):
        if re.match(r"^[0-9]", value):
            value = f"s_{value}"
        value = re.sub(r"[^a-z0-9_]", "_", value)[:64]
        if len(value) < 2:
            value = "custom_skill"
    return value[:64]


def _parse_requirement(question: str, skill_name: str | None, skill_id: str | None) -> Tuple[str, str, str]:
    q = (question or "").strip()
    if skill_name:
        name = skill_name.strip()
    else:
        m = re.search(r"(创建|新增|生成)(?P<name>[\u4e00-\u9fa5A-Za-z0-9_\- ]{2,30})(skill|技能)", q, re.IGNORECASE)
        name = (m.group("name").strip() if m else "自定义技能")
    sid = _to_skill_id(skill_id or name)
    desc = f"由 skill_creator 根据需求自动生成：{q[:120] or name}"
    return sid, name, desc


def _render_skill_code(skill_id: str, skill_name: str, description: str) -> str:
    return f'''"""
{skill_name}
{description}
"""
from typing import Any


def execute(**kwargs) -> dict[str, Any]:
    """
    自动生成的 Skill 模板。
    你可以在此处补充真实业务逻辑（调用 API / 处理文档 / 执行工作流等）。
    """
    user_input = kwargs.get("question") or kwargs.get("input") or ""
    return {{
        "skill_id": "{skill_id}",
        "skill_name": "{skill_name}",
        "message": "Skill 已创建并可执行（模板逻辑）。",
        "echo_input": user_input,
        "received_keys": sorted(list(kwargs.keys())),
    }}
'''


def _append_if_missing(path: Path, marker: str, line_to_add: str) -> bool:
    content = path.read_text(encoding="utf-8")
    if marker in content:
        return False
    updated = content.rstrip() + "\n" + line_to_add + "\n"
    path.write_text(updated, encoding="utf-8")
    return True


def execute(
    question: str,
    skill_name: str | None = None,
    skill_id: str | None = None,
    permission_level: str = "rag",
    overwrite: bool = False,
    run_after_create: bool = True,
    user=None,
    **kwargs,
) -> dict:
    """
    根据需求自动创建 Skill 模板，并注册到运行时。
    """
    if not is_triggered(question):
        return {
            "triggered": False,
            "created": False,
            "message": "未命中 skill 创建触发词。",
        }

    # 普通用户版默认不限制；SKILL_CREATOR_REQUIRE_STAFF=true 或未来 VIP 策略可在此扩展
    if getattr(settings, "SKILL_CREATOR_REQUIRE_STAFF", False):
        if user is None or not (
            getattr(user, "is_authenticated", False)
            and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
        ):
            return {
                "triggered": True,
                "created": False,
                "message": "当前仅管理员可创建自定义 Skill，以避免与「本地知识库文字问答」产品范围不符的任意生成。",
            }

    if _question_implies_non_text_kb_scope(question):
        return {
            "triggered": True,
            "created": False,
            "message": "本产品聚焦私有知识库与纯文字处理；不支持通过此处创建图像、视频、多模态或游戏类等 Skill。",
        }

    sid, sname, desc = _parse_requirement(question, skill_name, skill_id)
    builtin_dir = Path(__file__).resolve().parent
    skill_file = builtin_dir / f"{sid}.py"
    init_file = builtin_dir / "__init__.py"

    if skill_file.exists() and not overwrite:
        return {
            "triggered": True,
            "created": False,
            "skill_id": sid,
            "skill_name": sname,
            "message": f"Skill 文件已存在：{skill_file.name}。如需覆盖请传 overwrite=true。",
        }

    skill_file.write_text(_render_skill_code(sid, sname, desc), encoding="utf-8")

    import_line = f"from .{sid} import execute as {sid}_execute"
    register_line = f'SkillRegistry.register("{sid}", {sid}_execute, {{"name": "{sname}"}})'
    _append_if_missing(init_file, import_line, import_line)
    _append_if_missing(init_file, f'SkillRegistry.register("{sid}"', register_line)

    # A0.2：新建 Skill 默认 draft + 未激活；须审批/人工置 active 后普通用户才可执行
    Skill.objects.update_or_create(
        id=sid,
        defaults={
            "name": sname,
            "description": desc,
            "input_schema": {"question": "string", "input": "string"},
            "output_schema": {"message": "string"},
            "permission_level": permission_level if permission_level in {"rag", "file_read", "system"} else "rag",
            "metadata": {"requires": {}, "primary_env": "custom", "generated_by": "skill_creator"},
            "is_active": False,
            "lifecycle_status": "draft",
        },
    )

    # 尝试热注册：无需重启即可在当前进程调用
    try:
        module = importlib.import_module(f"apps.skills.builtin.{sid}")
        if hasattr(module, "execute"):
            SkillRegistry.register(sid, module.execute, {"name": sname})
    except Exception:
        pass

    payload = {
        "triggered": True,
        "created": True,
        "skill_id": sid,
        "skill_name": sname,
        "file_path": str(skill_file),
        "message": (
            f"Skill 创建成功：{sid}（lifecycle=draft, is_active=false）。"
            f"已尝试热注册；普通用户不可执行，须审批激活后再生效。"
        ),
    }
    # 小闭环：创建成功后，立即试运行一次，便于确认可调用性与最小产出。
    if run_after_create:
        trial_result, trial_err = SkillRegistry.execute_safe(
            sid,
            user=user,
            question=question,
            input=question,
        )
        payload["trial_run"] = {
            "ok": trial_err is None,
            "error": trial_err,
            "result": trial_result or {},
        }
        # 记录到自进化可见草案：便于管理员在「自进化管理」统一审计创建与试跑结果。
        try:
            md = [
                f"# skill_creator 创建与试运行记录",
                f"",
                f"- skill_id: `{sid}`",
                f"- skill_name: `{sname}`",
                f"- created_by: `{getattr(user, 'email', '') or getattr(user, 'username', '') or 'anonymous'}`",
                f"- trial_ok: `{trial_err is None}`",
            ]
            if trial_err:
                md.append(f"- trial_error: `{trial_err}`")
            if trial_result:
                md.append("")
                md.append("## trial_result")
                md.append("```json")
                md.append(json.dumps(trial_result, ensure_ascii=False, indent=2))
                md.append("```")
            st = SkillEvolutionStaging.objects.create(
                skill_id=sid,
                user=user if user and getattr(user, "is_authenticated", False) else None,
                status=SkillEvolutionStaging.Status.APPLIED,
                provenance="skill_creator_trial",
                draft_markdown="\n".join(md)[:8000],
                reviewed_at=timezone.now(),
            )
            payload["staging_id"] = str(st.id)
        except Exception:
            pass
    return payload
