from typing import Any, Callable, Dict, List, Optional, Tuple


def pop_skill_log_metadata(kwargs: Dict[str, Any]) -> Tuple[Optional[Any], str]:
    """从 kwargs 中取出仅用于 SkillExecutionLog 的审计字段，避免传入 execute()。"""
    refs = kwargs.pop("_log_retrieval_refs", None)
    trigger = (kwargs.pop("_log_trigger_source", None) or "") or ""
    return refs, str(trigger)[:64]

# 权限等级：rag < file_read < system
_PERMISSION_ORDER = {"rag": 0, "file_read": 1, "system": 2}


def _user_permission_level(user) -> int:
    """根据用户身份返回权限等级"""
    if user is None:
        return 0
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return 2
    if getattr(user, "is_authenticated", True):
        return 1
    return 0


def _is_privileged_user(user) -> bool:
    return bool(
        user
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "is_staff", False)
        )
    )


def check_skill_lifecycle(skill_id: str, user=None) -> tuple[bool, Optional[str]]:
    """
    生命周期硬门禁：
    - 普通用户：仅 is_active 且 lifecycle_status=active
    - staff：可试跑 draft / is_active=false
    - disabled / rolled_back：仅 superuser
    """
    try:
        from .models import Skill

        skill = Skill.objects.filter(id=skill_id).first()
        if not skill:
            return (False, f"Skill 不存在或未入库: {skill_id}")

        status = (skill.lifecycle_status or "active").strip().lower()
        privileged = _is_privileged_user(user)
        is_super = bool(user and getattr(user, "is_superuser", False))

        if status in ("disabled", "rolled_back"):
            if is_super:
                return (True, None)
            return (False, f"Skill 生命周期为 {status}，不可执行: {skill_id}")

        if status == "draft" or not skill.is_active:
            if privileged:
                return (True, None)
            detail = "draft" if status == "draft" else "is_active=false"
            return (False, f"Skill 未对普通用户开放（{detail}）: {skill_id}")

        return (True, None)
    except Exception as e:
        return (False, str(e))


def check_skill_permission(skill_id: str, user=None) -> tuple[bool, Optional[str]]:
    """
    检查用户是否有权执行该 Skill。
    返回 (allowed, error_message)，allowed=False 时 error_message 说明原因。
    """
    try:
        from .models import Skill
        skill = Skill.objects.filter(id=skill_id).first()
        level = skill.permission_level if skill else "rag"
        required = _PERMISSION_ORDER.get(level, 0)
        user_level = _user_permission_level(user)
        if user_level >= required:
            return (True, None)
        return (False, f"权限不足：执行 {skill_id} 需要 {level} 级别")
    except Exception as e:
        return (False, str(e))


def log_skill_execution(
    skill_id: str,
    status: str,
    input_summary: str = "",
    output_summary: str = "",
    session_id=None,
    user=None,
    retrieval_refs=None,
    trigger_source: str = "",
):
    """写入 SkillExecutionLog，失败时静默忽略。可供 AgentOrchestrator 等外部调用。"""
    try:
        from .models import SkillExecutionLog

        refusal = ""
        if status in ("denied", "failed"):
            refusal = (output_summary or "")[:128]
        refs = retrieval_refs if retrieval_refs is not None else []
        if isinstance(refs, dict):
            refs_payload: Any = refs
        elif isinstance(refs, list):
            refs_payload = refs
        else:
            refs_payload = []
        SkillExecutionLog.objects.create(
            skill_id=skill_id,
            session_id=session_id,
            user=user if user and getattr(user, "is_authenticated", False) else None,
            input_summary=(input_summary or "")[:500],
            output_summary=(output_summary or "")[:500],
            status=status,
            refusal_reason=refusal,
            retrieval_refs=refs_payload,
            trigger_source=(trigger_source or "")[:64],
        )
    except Exception:
        pass


class SkillRegistry:
    """Skill 运行时注册表"""
    _skills: Dict[str, dict] = {}

    @classmethod
    def register(cls, skill_id: str, execute_func: Callable, meta: Optional[dict] = None):
        cls._skills[skill_id] = {
            "execute": execute_func,
            "meta": meta or {},
        }

    @classmethod
    def get(cls, skill_id: str) -> Optional[dict]:
        return cls._skills.get(skill_id)

    @classmethod
    def list_ids(cls) -> List[str]:
        return list(cls._skills.keys())

    @classmethod
    def execute(cls, skill_id: str, **kwargs) -> dict:
        skill = cls.get(skill_id)
        if not skill:
            raise ValueError(f"Unknown skill: {skill_id}")
        return skill["execute"](**kwargs)

    @classmethod
    def execute_safe(cls, skill_id: str, session_id=None, user=None, **kwargs) -> tuple[Optional[dict], Optional[str]]:
        """安全执行：先生命周期门禁，再 permission_level，并写入 SkillExecutionLog。"""
        log_refs, log_trigger = pop_skill_log_metadata(kwargs)
        input_summary = str(kwargs)[:200] if kwargs else ""

        life_ok, life_err = check_skill_lifecycle(skill_id, user)
        if not life_ok:
            log_skill_execution(
                skill_id, "denied", input_summary, life_err or "", session_id, user=user,
                retrieval_refs=log_refs, trigger_source=log_trigger,
            )
            return (None, life_err)

        allowed, perm_err = check_skill_permission(skill_id, user)
        if not allowed:
            log_skill_execution(
                skill_id, "denied", input_summary, perm_err or "", session_id, user=user,
                retrieval_refs=log_refs, trigger_source=log_trigger,
            )
            return (None, perm_err)
        try:
            result = cls.execute(skill_id, **kwargs)
            output_summary = str(result)[:200] if result else ""
            log_skill_execution(
                skill_id, "success", input_summary, output_summary, session_id, user=user,
                retrieval_refs=log_refs, trigger_source=log_trigger,
            )
            return (result, None)
        except Exception as e:
            err_msg = str(e)[:200]
            log_skill_execution(
                skill_id, "failed", input_summary, err_msg, session_id, user=user,
                retrieval_refs=log_refs, trigger_source=log_trigger,
            )
            return (None, str(e))
