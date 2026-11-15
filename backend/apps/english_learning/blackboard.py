"""MVP-B：session_state 黑板字段规范化与今日任务规则（无 LLM）。"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from django.utils import timezone


def now_iso() -> str:
    return timezone.now().isoformat()


def normalize_weak_dimensions(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    if isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    return []


def active_unit_id_from_outline(outline: Any) -> str:
    """从路线 outline_json 取当前学习单元标识（首周/首主题）。"""
    if not isinstance(outline, dict):
        return "week_1"
    weeks = outline.get("weeks")
    if isinstance(weeks, list) and weeks:
        w0 = weeks[0]
        if isinstance(w0, dict):
            wk = w0.get("week")
            th = w0.get("theme")
            parts = [p for p in (wk, th) if p]
            if parts:
                return ":".join(str(p) for p in parts)
    return "week_1"


def hours_since_iso(iso_ts: Optional[str]) -> Optional[float]:
    if not iso_ts or not isinstance(iso_ts, str):
        return None
    s = iso_ts.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    delta = timezone.now() - dt
    return delta.total_seconds() / 3600.0


def local_date_from_iso(iso_ts: Optional[str]) -> Optional[date]:
    """将 ISO 时间戳转为当前时区日历日期；解析失败返回 None。"""
    if not iso_ts or not isinstance(iso_ts, str):
        return None
    s = iso_ts.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return timezone.localtime(dt).date()


def missed_yesterday_drill(last_drill_iso: Optional[str]) -> bool:
    """本地日历：上次巩固日期早于「昨天」则视为昨日窗口未完成。"""
    last_d = local_date_from_iso(last_drill_iso)
    if last_d is None:
        return False
    today = timezone.localdate()
    return last_d < (today - timedelta(days=1))


def _parse_hh_mm(value: Any) -> Optional[tuple[int, int]]:
    if not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if 0 <= h <= 23 and 0 <= m <= 59:
        return (h, m)
    return None


def normalize_quiet_hours_dict(raw: Any) -> Dict[str, Any]:
    """
    将客户端写入的 quiet_hours 规范为 { enabled, start, end }，非法时间回退默认 22:00 / 07:00。
    """
    if not isinstance(raw, dict):
        raw = {}
    enabled = bool(raw.get("enabled"))
    st = _parse_hh_mm(str(raw.get("start") or "22:00").strip())
    en = _parse_hh_mm(str(raw.get("end") or "07:00").strip())
    if st is None:
        st = (22, 0)
    if en is None:
        en = (7, 0)
    return {
        "enabled": enabled,
        "start": f"{st[0]:02d}:{st[1]:02d}",
        "end": f"{en[0]:02d}:{en[1]:02d}",
    }


def minutes_now_local(now: Optional[datetime] = None) -> int:
    dt = now or timezone.now()
    t = timezone.localtime(dt)
    return t.hour * 60 + t.minute


def quiet_hours_active_now(quiet_cfg: Any, now: Optional[datetime] = None) -> bool:
    """
    安静时段是否命中（使用 Django 配置的当前时区 localtime）。
    quiet_cfg: { "enabled": bool, "start": "22:00", "end": "07:00" }；跨午夜：start > end。
    """
    cfg = normalize_quiet_hours_dict(quiet_cfg)
    if not cfg["enabled"]:
        return False
    start = _parse_hh_mm(cfg["start"])
    end = _parse_hh_mm(cfg["end"])
    if not start or not end:
        return False
    sm = start[0] * 60 + start[1]
    em = end[0] * 60 + end[1]
    cur = minutes_now_local(now)
    if sm == em:
        return False
    if sm > em:
        return cur >= sm or cur <= em
    return sm <= cur <= em


def reminder_prefs_from_state(session_state: Dict[str, Any]) -> Dict[str, Any]:
    """解析 session_state.reminder_prefs，供 API 回显与任务/回忆包裁剪。"""
    st = session_state or {}
    raw = st.get("reminder_prefs")
    if not isinstance(raw, dict):
        raw = {}
    dnd = bool(raw.get("do_not_disturb"))
    intensity = str(raw.get("intensity") or "normal").lower()
    if intensity not in ("low", "normal", "high"):
        intensity = "normal"
    qh = raw.get("quiet_hours")
    quiet_cfg = qh if isinstance(qh, dict) else {}
    quiet_norm = normalize_quiet_hours_dict(quiet_cfg)
    qh_active = quiet_hours_active_now(quiet_norm)
    return {
        "do_not_disturb": dnd,
        "intensity": intensity,
        "quiet_hours": quiet_norm,
        "quiet_hours_active": qh_active,
    }


def is_proactive_reminder_suppressed(session_state: Dict[str, Any]) -> bool:
    """免打扰开关或安静时段内：不推昨日/弱项/回忆包等主动项（向导非 tutor 阶段不受影响）。"""
    p = reminder_prefs_from_state(session_state)
    return bool(p["do_not_disturb"]) or bool(p["quiet_hours_active"])


def build_today_tasks(session_state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    返回前端可渲染的今日建议列表。
    cta_step: 向导步骤 0–3；cta_chat: true 时跳转智能问答（由前端拼 query）。
    """
    st = session_state or {}
    phase = str(st.get("phase") or "intake").lower()
    weak = normalize_weak_dimensions(st.get("weak_dimensions"))
    last_drill = st.get("last_drill_at") or ""
    hours = hours_since_iso(last_drill) if last_drill else None
    stale = hours is None or hours >= 20

    tasks: List[Dict[str, Any]] = []

    if phase == "intake":
        if st.get("bootstrap_completed"):
            tasks.append(
                {
                    "id": "post_bootstrap",
                    "title": "开始测评组卷",
                    "detail": "建档已完成，可进入测评页开始组卷。",
                    "cta_step": 1,
                    "cta_chat": False,
                }
            )
        else:
            tasks.append(
                {
                    "id": "bootstrap",
                    "title": "完成学习目标建档",
                    "detail": "选择级别标签与每周投入时间，保存档案。",
                    "cta_step": 0,
                    "cta_chat": False,
                }
            )
        return tasks

    if phase == "assessment":
        pc = str(st.get("placement_choice") or "full_test").lower()
        detail = "在测评页开始组卷并提交，以生成薄弱维度与路线输入。"
        if pc == "quick":
            detail = "当前为快速定级（题量较少）。开始组卷并提交后，可进入反馈与路线步骤。"
        tasks.append(
            {
                "id": "assessment",
                "title": "完成测评组卷与作答",
                "detail": detail,
                "cta_step": 1,
                "cta_chat": False,
            }
        )
        return tasks

    if phase in ("roadmap",):
        tasks.append(
            {
                "id": "roadmap_draft",
                "title": "生成学习路线草案",
                "detail": "在反馈页选择加强维度后生成 Markdown 路线。",
                "cta_step": 2,
                "cta_chat": False,
            }
        )
        return tasks

    if phase == "roadmap_review":
        tasks.append(
            {
                "id": "roadmap_finalize",
                "title": "审阅并定稿入库",
                "detail": "确认路线文案后写入私有知识库；多轮修订可先保存草稿（save-draft），再定稿。",
                "cta_step": 3,
                "cta_chat": False,
            }
        )
        return tasks

    if phase == "tutor":
        prefs = reminder_prefs_from_state(st)
        if is_proactive_reminder_suppressed(st):
            tasks.append(
                {
                    "id": "reminder_suppressed",
                    "title": "免打扰或安静时段",
                    "detail": "已暂停昨日/弱项等主动提醒与回忆包；仍可在智能问答中自主练习。",
                    "cta_step": None,
                    "cta_chat": True,
                    "english_delegate": None,
                }
            )
            return tasks

        intensity = prefs["intensity"]
        proactive_cap = 1 if intensity == "low" else 2
        proactive_added = 0
        unit = (st.get("active_unit_id") or "").strip() or "当前单元"

        def _can_add_proactive() -> bool:
            nonlocal proactive_added
            if proactive_added >= proactive_cap:
                return False
            proactive_added += 1
            return True

        if weak and missed_yesterday_drill(last_drill) and _can_add_proactive():
            tasks.append(
                {
                    "id": "yesterday_miss",
                    "title": "昨日巩固未完成",
                    "detail": "已超过一个自然日未在建议窗口内巩固，优先补上短练习或下方回忆包。",
                    "cta_step": None,
                    "cta_chat": True,
                    "english_delegate": "grammar" if "grammar" in weak else "vocab",
                }
            )
        if weak and stale and _can_add_proactive():
            tasks.append(
                {
                    "id": "weak_review",
                    "title": "弱项巩固",
                    "detail": f"建议今日回顾：{', '.join(weak)}（当前单元：{unit}）。",
                    "cta_step": None,
                    "cta_chat": True,
                    "english_delegate": "grammar" if "grammar" in weak else "vocab",
                }
            )
        tasks.append(
            {
                "id": "daily_chat",
                "title": "智能陪练",
                "detail": "打开智能问答，使用主编排与个人知识库继续练习。",
                "cta_step": None,
                "cta_chat": True,
                "english_delegate": None,
            }
        )
        return tasks

    tasks.append(
        {
            "id": "fallback",
            "title": "继续学习计划",
            "detail": "在向导中查看当前阶段并完成下一步。",
            "cta_step": 0,
            "cta_chat": False,
        }
    )
    return tasks
