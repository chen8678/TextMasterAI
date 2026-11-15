"""
Skill 环境资格评估，移植自 OpenClaw config-eval.ts + skills/config.ts
"""
import os
import platform
import shutil
from typing import Callable, Optional


def has_binary(bin_name: str) -> bool:
    """检查 PATH 中是否存在某 bin"""
    return shutil.which(bin_name) is not None


def evaluate_runtime_requires(
    requires: Optional[dict],
    has_bin: Callable[[str], bool] = has_binary,
    has_env: Callable[[str], bool] = lambda e: bool(os.environ.get(e)),
    is_config_truthy: Callable[[str], bool] = lambda _: False,
) -> bool:
    """检查 requires.bins、anyBins、env、config 是否满足"""
    if not requires:
        return True
    for b in (requires.get("bins") or []):
        if not has_bin(b):
            return False
    for bins in (requires.get("anyBins") or []):
        if not any(has_bin(x) for x in bins):
            return False
    for e in (requires.get("env") or []):
        if not has_env(e):
            return False
    for c in (requires.get("config") or []):
        if not is_config_truthy(c):
            return False
    return True


def evaluate_runtime_eligibility(
    requires: Optional[dict] = None,
    os_list: Optional[list] = None,
    always: Optional[bool] = None,
    has_bin: Callable[[str], bool] = has_binary,
    has_env: Callable[[str], bool] = lambda e: bool(os.environ.get(e)),
    is_config_truthy: Callable[[str], bool] = lambda _: False,
) -> bool:
    """综合 os、always、requires 判断 Skill 是否可用"""
    current_platform = platform.system().lower()
    if os_list and len(os_list) > 0:
        os_normalized = [o.lower() for o in os_list]
        darwin_match = "darwin" in os_normalized and current_platform == "darwin"
        linux_match = "linux" in os_normalized and current_platform == "linux"
        win_match = any(
            w in os_normalized for w in ["win32", "windows"]
        ) and current_platform == "windows"
        if not (darwin_match or linux_match or win_match):
            return False
    if always is True:
        return True
    return evaluate_runtime_requires(
        requires, has_bin=has_bin, has_env=has_env, is_config_truthy=is_config_truthy
    )


def should_include_skill(skill, config: Optional[dict] = None) -> bool:
    """
    综合判断 Skill 是否应纳入本次运行。
    结合 Skill.is_active、metadata.enabled、evaluate_runtime_eligibility
    """
    if not getattr(skill, "is_active", True):
        return False
    metadata = getattr(skill, "metadata", None) or {}
    if metadata.get("enabled") is False:
        return False
    return evaluate_runtime_eligibility(
        requires=metadata.get("requires"),
        os_list=metadata.get("os"),
        always=metadata.get("always"),
    )
