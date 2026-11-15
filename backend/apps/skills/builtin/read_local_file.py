"""
本地文件读取 Skill：仅允许读取白名单目录内的文件
"""
import os
from django.conf import settings


def _is_path_allowed(file_path: str) -> bool:
    """检查路径是否在白名单目录内"""
    real_path = os.path.realpath(os.path.abspath(file_path))
    whitelist = getattr(settings, "SKILL_FILE_WHITELIST", [])
    if not whitelist:
        return False
    for allowed_dir in whitelist:
        allowed_real = os.path.realpath(os.path.abspath(allowed_dir))
        if real_path == allowed_real or real_path.startswith(allowed_real + os.sep):
            return True
    return False


def execute(file_path: str, max_chars: int = 50000, **kwargs) -> dict:
    """
    读取本地文件内容（仅白名单目录）
    
    Args:
        file_path: 文件路径（相对或绝对，必须在 SKILL_FILE_WHITELIST 内）
        max_chars: 最大读取字符数，防止大文件
    
    Returns:
        {"content": str, "path": str, "truncated": bool}
    """
    if not _is_path_allowed(file_path):
        raise PermissionError(f"路径不在白名单内: {file_path}")
    
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read(max_chars)
    
    truncated = len(content) >= max_chars
    return {
        "content": content,
        "path": os.path.abspath(file_path),
        "truncated": truncated,
    }
