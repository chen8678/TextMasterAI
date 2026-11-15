"""
G3（Phase-C）：向导图 resume 的 SSE 进度流。
每推进一个 LangGraph 节点推送 `node_done`；`roadmap_draft_skill` 执行期间推送 LLM `token`；
结束时推送 `end`（含 `wizard_graph` 摘要）。
"""

from __future__ import annotations

import json
import queue
import threading
from typing import Any, Dict, Generator, Iterable, Optional

from ..models import EnglishLearningProfile
from ..skill_handlers.stream_context import reset_wizard_token_callback, set_wizard_token_callback
from .human_hints import human_action_hint
from .langgraph_wizard import (
    LANGGRAPH_AVAILABLE,
    WIZARD_HUMAN_INTERRUPT_AFTER,
    get_compiled_wizard_app,
    persist_wizard_graph_to_django,
    read_wizard_checkpoint_tip,
    _merge_resume_payload,
    _snapshot_to_dict,
    _wizard_completed,
)


def _last_node(poc_trace: list) -> str:
    tr = poc_trace or []
    return str(tr[-1]) if tr else ""


_STREAM_SENTINEL = object()


def _stream_invoke(
    app,
    config: dict,
    invoke_arg: Any,
) -> Generator[Dict[str, Any], None, Any]:
    """
    在后台线程执行 app.invoke，主线程 yield LLM token 事件。
    Generator 耗尽后通过 StopIteration.value 返回 invoke 输出（3.7+ 用 yield from 包装）。
    """
    token_queue: queue.Queue = queue.Queue()
    holder: Dict[str, Any] = {"out": None, "err": None}

    def token_cb(text: str, node: str) -> None:
        token_queue.put({"type": "token", "text": text, "node": node})

    def worker() -> None:
        from django.db import close_old_connections

        close_old_connections()
        tok = set_wizard_token_callback(token_cb)
        try:
            holder["out"] = app.invoke(invoke_arg, config=config)
        except Exception as exc:
            holder["err"] = exc
        finally:
            reset_wizard_token_callback(tok)
            token_queue.put(_STREAM_SENTINEL)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        try:
            item = token_queue.get(timeout=0.05)
        except queue.Empty:
            if not thread.is_alive():
                while True:
                    try:
                        item = token_queue.get_nowait()
                    except queue.Empty:
                        break
                    if item is _STREAM_SENTINEL:
                        break
                    yield item  # type: ignore[misc]
                break
            continue
        if item is _STREAM_SENTINEL:
            break
        yield item

    thread.join()
    if holder["err"] is not None:
        raise holder["err"]
    return holder["out"]


def _invoke_with_tokens(app, config: dict, invoke_arg: Any) -> tuple[Any, list]:
    """执行 app.invoke 并收集流式 token 事件。"""
    tokens: list = []
    gen = _stream_invoke(app, config, invoke_arg)
    try:
        while True:
            tokens.append(next(gen))
    except StopIteration as stop:
        return stop.value, tokens


def build_wizard_graph_payload(
    vals: Dict[str, Any],
    *,
    completed: bool = False,
    interrupted: bool = False,
    next_nodes: Optional[list] = None,
    failed: bool = False,
) -> Dict[str, Any]:
    pending = str(vals.get("pending_human_node") or "")
    nxt = list(next_nodes or [])
    return {
        "completed": completed,
        "interrupted": interrupted,
        "failed": failed,
        "next_nodes": nxt,
        "phase": vals.get("phase"),
        "poc_trace": vals.get("poc_trace"),
        "pending_human_node": pending,
        "node_data": vals.get("node_data") or {},
        "last_error": vals.get("last_error") or "",
        "human_action": human_action_hint(
            pending_human_node=pending or None,
            next_nodes=nxt,
            completed=completed,
            phase=str(vals.get("phase") or ""),
        ),
        "human_interrupt_after": list(WIZARD_HUMAN_INTERRUPT_AFTER),
    }


def iter_wizard_resume_events(
    profile: EnglishLearningProfile,
    user,
    *,
    thread_id: str,
    initial_payload: Optional[dict] = None,
    resume_payload: Optional[dict] = None,
    max_steps: int = 20,
) -> Generator[Dict[str, Any], None, None]:
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError("未安装 langgraph")

    app = get_compiled_wizard_app()
    config = {"configurable": {"thread_id": thread_id}}
    yield {"type": "start", "thread_id": thread_id}

    tip_before = read_wizard_checkpoint_tip(thread_id=thread_id)
    if tip_before is None:
        init: Dict[str, Any] = {
            "profile_id": str(profile.pk),
            "user_id": str(user.pk),
            "phase": "intake",
            "poc_trace": [],
            "node_payload": dict(initial_payload or {}),
            "last_error": "",
            "pending_human_node": "",
            "node_data": {},
        }
        out, token_events = _invoke_with_tokens(app, config, init)
        for ev in token_events:
            yield ev
    else:
        if resume_payload:
            _merge_resume_payload(config, resume_payload)
        out, token_events = _invoke_with_tokens(app, config, None)
        for ev in token_events:
            yield ev

    steps = 0
    while steps < max_steps:
        st = app.get_state(config)
        if st is None:
            break
        tip = _snapshot_to_dict(st)
        next_nodes = list(tip.get("next") or [])
        vals = dict(tip.get("values") or out or {})

        if _wizard_completed(vals, next_nodes=next_nodes):
            persist_wizard_graph_to_django(profile, thread_id=thread_id, values=vals, tip=tip)
            wg = build_wizard_graph_payload(vals, completed=True)
            yield {"type": "end", "wizard_graph": wg}
            return

        if next_nodes:
            persist_wizard_graph_to_django(profile, thread_id=thread_id, values=vals, tip=tip)
            wg = build_wizard_graph_payload(vals, interrupted=True, next_nodes=next_nodes)
            yield {"type": "interrupt", "wizard_graph": wg}
            return

        if vals.get("last_error"):
            persist_wizard_graph_to_django(profile, thread_id=thread_id, values=vals, tip=tip)
            wg = build_wizard_graph_payload(vals, failed=True, next_nodes=[])
            yield {"type": "error", "wizard_graph": wg, "error": str(vals.get("last_error"))}
            return

        prev_len = len(list(vals.get("poc_trace") or []))
        out, token_events = _invoke_with_tokens(app, config, None)
        for ev in token_events:
            yield ev
        st2 = app.get_state(config)
        tip2 = _snapshot_to_dict(st2) if st2 else tip
        vals2 = dict((tip2 or {}).get("values") or out or {})
        tr2 = list(vals2.get("poc_trace") or [])
        if len(tr2) > prev_len:
            node_nm = _last_node(tr2)
            yield {
                "type": "node_done",
                "node": node_nm,
                "phase": vals2.get("phase"),
                "message": f"已完成节点：{node_nm}",
                "interrupt_after": node_nm in WIZARD_HUMAN_INTERRUPT_AFTER,
            }
        steps += 1

    st = app.get_state(config)
    tip = _snapshot_to_dict(st) if st else None
    vals = dict((tip or {}).get("values") or out or {})
    next_nodes = list((tip or {}).get("next") or [])
    completed = _wizard_completed(vals, next_nodes=next_nodes)
    persist_wizard_graph_to_django(profile, thread_id=thread_id, values=vals, tip=tip)
    wg = build_wizard_graph_payload(
        vals,
        completed=completed,
        interrupted=bool(next_nodes),
        next_nodes=next_nodes,
    )
    yield {"type": "end" if completed else "interrupt", "wizard_graph": wg}


def format_sse_events(events: Iterable[Dict[str, Any]]) -> Generator[str, None, None]:
    for ev in events:
        typ = ev.get("type") or "message"
        yield f"event: {typ}\ndata: {json.dumps(ev, ensure_ascii=False)}\n\n"
