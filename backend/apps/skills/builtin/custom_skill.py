"""
自定义技能
由 skill_creator 根据需求自动生成：创建技能：记录试跑结果skill
"""
from typing import Any


def execute(**kwargs) -> dict[str, Any]:
    """
    自动生成的 Skill 模板。
    你可以在此处补充真实业务逻辑（调用 API / 处理文档 / 执行工作流等）。
    """
    user_input = kwargs.get("question") or kwargs.get("input") or ""
    return {
        "skill_id": "custom_skill",
        "skill_name": "自定义技能",
        "message": "Skill 已创建并可执行（模板逻辑）。",
        "echo_input": user_input,
        "received_keys": sorted(list(kwargs.keys())),
    }
