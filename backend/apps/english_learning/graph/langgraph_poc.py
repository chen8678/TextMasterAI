"""
Phase-C G1：可选 LangGraph POC——与 `nodes.WIZARD_GRAPH_NODE_NAMES` 一致的**线性占位链**
（每节点仅追加 `poc_trace`，末节点将 `phase` 置为 `tutor`）+ checkpointer。
未安装 `langgraph` 时 `LANGGRAPH_AVAILABLE` 为 False，业务路径不依赖本模块。

Checkpointer 选择（`settings.ENGLISH_LEARNING_LANGGRAPH_CHECKPOINTER`）：
- **auto**（默认）：Django 为 PostgreSQL 且已安装 `langgraph-checkpoint-postgres` 时用 **Postgres**；否则 **Sqlite**；再否则 **InMemory**。
- **postgres** / **sqlite** / **memory**：强制指定。

图编译时对每个节点设置 **interrupt_after**，支持 **单步推进**（`advance_english_graph_poc_step`）；
**invoke_english_graph_poc** 则循环 resume 直至跑完全链。

单测请调用 `reset_langgraph_poc_runtime_for_tests(use_isolated_sqlite=True)`（默认）。
"""

from __future__ import annotations

import importlib.util
import os
import sqlite3
import tempfile
import threading
from typing import Any, Dict, Literal, Optional, Tuple, TypedDict
from urllib.parse import quote_plus

from .nodes import WIZARD_GRAPH_NODE_NAMES
from .wizard_node_handlers import apply_wizard_node

LANGGRAPH_AVAILABLE = importlib.util.find_spec("langgraph") is not None

SQLITE_SAVER_AVAILABLE = False
POSTGRES_SAVER_AVAILABLE = False
if LANGGRAPH_AVAILABLE:
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: F401

        SQLITE_SAVER_AVAILABLE = True
    except ImportError:
        SQLITE_SAVER_AVAILABLE = False
    try:
        from langgraph.checkpoint.postgres import PostgresSaver  # noqa: F401

        POSTGRES_SAVER_AVAILABLE = True
    except ImportError:
        POSTGRES_SAVER_AVAILABLE = False

CheckpointerBackend = Literal["memory", "sqlite", "postgres"]

_compile_lock = threading.Lock()
_sqlite_conn: Optional[sqlite3.Connection] = None
_postgres_cm: Any = None
_saver = None  # type: ignore[var-annotated]
_compiled_app = None  # type: ignore[var-annotated]
_active_backend: Optional[CheckpointerBackend] = None
_test_isolated_sqlite_path: Optional[str] = None
_test_force_checkpointer_backend: Optional[CheckpointerBackend] = None


class EnglishGraphPocState(TypedDict, total=False):
    """演示用最小状态；与 `EnglishLearningState` 的 `phase` 对齐，另加 `poc_trace` 便于观测。"""

    phase: str
    poc_trace: list[str]


def _effective_sqlite_path() -> str:
    if _test_isolated_sqlite_path is not None:
        return _test_isolated_sqlite_path
    try:
        from django.conf import settings

        p = getattr(settings, "ENGLISH_LEARNING_LANGGRAPH_SQLITE_PATH", None)
        if p:
            return str(p)
    except Exception:
        pass
    return os.path.join(tempfile.gettempdir(), "english_learning_langgraph_default.sqlite")


def _configured_checkpointer_mode() -> str:
    try:
        from django.conf import settings

        return str(getattr(settings, "ENGLISH_LEARNING_LANGGRAPH_CHECKPOINTER", "auto") or "auto").strip().lower()
    except Exception:
        return "auto"


def _postgres_use_main_db() -> bool:
    try:
        from django.conf import settings

        raw = getattr(settings, "ENGLISH_LEARNING_LANGGRAPH_POSTGRES_USE_MAIN_DB", True)
        if isinstance(raw, str):
            return raw.lower() in ("1", "true", "yes", "on")
        return bool(raw)
    except Exception:
        return True


def _postgres_conn_string_from_django() -> Optional[str]:
    if not _postgres_use_main_db():
        return None
    try:
        from django.conf import settings

        url = os.getenv("DATABASE_URL", "").strip()
        if url:
            return url
        db = settings.DATABASES.get("default") or {}
        engine = str(db.get("ENGINE") or "")
        if "postgresql" not in engine:
            return None
        user = quote_plus(str(db.get("USER") or ""))
        password = quote_plus(str(db.get("PASSWORD") or ""))
        host = db.get("HOST") or "127.0.0.1"
        port = db.get("PORT") or "5432"
        name = str(db.get("NAME") or "")
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"
    except Exception:
        return None


def resolve_checkpointer_backend() -> CheckpointerBackend:
    """解析将使用的 checkpointer 类型（不创建连接）。"""
    if _test_force_checkpointer_backend is not None:
        return _test_force_checkpointer_backend
    mode = _configured_checkpointer_mode()
    if mode == "memory":
        return "memory"
    if mode == "sqlite":
        return "sqlite" if SQLITE_SAVER_AVAILABLE else "memory"
    if mode == "postgres":
        if POSTGRES_SAVER_AVAILABLE and _postgres_conn_string_from_django():
            return "postgres"
        return "sqlite" if SQLITE_SAVER_AVAILABLE else "memory"
    # auto
    if POSTGRES_SAVER_AVAILABLE and _postgres_conn_string_from_django():
        return "postgres"
    if SQLITE_SAVER_AVAILABLE:
        return "sqlite"
    return "memory"


def get_checkpointer_backend() -> CheckpointerBackend:
    """当前进程内已编译图实际使用的 backend；未编译时返回 `resolve_checkpointer_backend()`。"""
    if _active_backend is not None:
        return _active_backend
    return resolve_checkpointer_backend()


def poc_trace_to_node_cursor(poc_trace: list[str] | None) -> int:
    """LangGraph `poc_trace` 长度 → 占位 `node_cursor`（最后一项对应游标）。"""
    names = WIZARD_GRAPH_NODE_NAMES
    if not names:
        return 0
    n = len(names)
    tr = poc_trace or []
    if not tr:
        return 0
    return min(max(0, len(tr) - 1), n - 1)


def _build_graph_with_saver(saver: Any) -> Any:
    from langgraph.graph import END, START, StateGraph

    names = tuple(WIZARD_GRAPH_NODE_NAMES)
    if not names:
        raise RuntimeError("WIZARD_GRAPH_NODE_NAMES 为空，无法编译 POC 图")

    def make_step(logical_name: str, *, is_last: bool):
        def step(state: EnglishGraphPocState) -> Dict[str, Any]:
            return apply_wizard_node(logical_name, dict(state), is_last=is_last)

        return step

    g = StateGraph(EnglishGraphPocState)
    last = len(names) - 1
    for i, nm in enumerate(names):
        g.add_node(nm, make_step(nm, is_last=(i == last)))
    g.add_edge(START, names[0])
    for a, b in zip(names, names[1:]):
        g.add_edge(a, b)
    g.add_edge(names[-1], END)
    return g.compile(checkpointer=saver, interrupt_after=list(names))


def _make_saver_and_conn() -> Tuple[Any, Optional[sqlite3.Connection], CheckpointerBackend]:
    backend = resolve_checkpointer_backend()
    if backend == "postgres" and POSTGRES_SAVER_AVAILABLE:
        from langgraph.checkpoint.postgres import PostgresSaver

        global _postgres_cm
        conn = _postgres_conn_string_from_django()
        if not conn:
            backend = "sqlite" if SQLITE_SAVER_AVAILABLE else "memory"
        else:
            _postgres_cm = PostgresSaver.from_conn_string(conn)
            saver = _postgres_cm.__enter__()
            saver.setup()
            return saver, None, "postgres"
    if backend == "sqlite" and SQLITE_SAVER_AVAILABLE:
        from langgraph.checkpoint.sqlite import SqliteSaver

        path = _effective_sqlite_path()
        parent = os.path.dirname(os.path.abspath(path))
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        return SqliteSaver(conn), conn, "sqlite"
    from langgraph.checkpoint.memory import InMemorySaver

    return InMemorySaver(), None, "memory"


def get_compiled_poc_app() -> Any:
    """进程内单例编译图 + 共享 checkpointer（懒加载）。"""
    global _saver, _compiled_app, _sqlite_conn, _active_backend
    if _compiled_app is not None:
        return _compiled_app
    with _compile_lock:
        if _compiled_app is not None:
            return _compiled_app
        if _saver is None:
            _saver, _sqlite_conn, _active_backend = _make_saver_and_conn()
        _compiled_app = _build_graph_with_saver(_saver)
        return _compiled_app


def reset_langgraph_poc_runtime_for_tests(
    *,
    use_isolated_sqlite: bool = True,
    force_backend: Optional[CheckpointerBackend] = "sqlite",
) -> None:
    """单测隔离：关闭连接、清空单例；默认每次换新的临时 SQLite 文件并强制 sqlite backend。"""
    global _saver, _compiled_app, _sqlite_conn, _postgres_cm, _active_backend, _test_isolated_sqlite_path
    global _test_force_checkpointer_backend
    _test_force_checkpointer_backend = force_backend
    with _compile_lock:
        _compiled_app = None
        _saver = None
        _active_backend = None
        if _sqlite_conn is not None:
            try:
                _sqlite_conn.close()
            except Exception:
                pass
            _sqlite_conn = None
        if _postgres_cm is not None:
            try:
                _postgres_cm.__exit__(None, None, None)
            except Exception:
                pass
            _postgres_cm = None
        if use_isolated_sqlite:
            old = _test_isolated_sqlite_path
            if old and os.path.isfile(old):
                try:
                    os.unlink(old)
                except OSError:
                    pass
            fd, path = tempfile.mkstemp(suffix=".sqlite")
            os.close(fd)
            _test_isolated_sqlite_path = path
        else:
            if _test_isolated_sqlite_path and os.path.isfile(_test_isolated_sqlite_path):
                try:
                    os.unlink(_test_isolated_sqlite_path)
                except OSError:
                    pass
            _test_isolated_sqlite_path = None


def _snapshot_to_dict(st: Any) -> Dict[str, Any]:
    md = getattr(st, "metadata", None) or {}
    cfg = getattr(st, "config", None) or {}
    conf = cfg.get("configurable") or {}
    nxt = getattr(st, "next", None)
    return {
        "values": dict(getattr(st, "values", {}) or {}),
        "step": md.get("step"),
        "checkpoint_id": conf.get("checkpoint_id"),
        "next": list(nxt) if nxt else [],
    }


def _is_poc_chain_complete(values: Dict[str, Any], *, next_nodes: list[str]) -> bool:
    names = list(WIZARD_GRAPH_NODE_NAMES)
    tr = list(values.get("poc_trace") or [])
    if names and tr == names and not next_nodes:
        return True
    return False


def read_langgraph_checkpoint_tip(*, thread_id: str) -> Optional[Dict[str, Any]]:
    """读取当前线程在 LangGraph checkpointer 中的最新 `StateSnapshot`（可 JSON 序列化子集）。"""
    if not LANGGRAPH_AVAILABLE:
        return None
    try:
        app = get_compiled_poc_app()
        st = app.get_state({"configurable": {"thread_id": thread_id}})
    except Exception:
        return None
    if st is None or getattr(st, "values", None) is None:
        return None
    tip = _snapshot_to_dict(st)
    vals = tip.get("values") or {}
    if not tip.get("checkpoint_id") and not vals:
        return None
    return tip


def list_langgraph_checkpoint_summaries(*, thread_id: str, limit: int = 20) -> list[Dict[str, Any]]:
    """枚举 checkpointer 中某 `thread_id` 的最近若干 checkpoint（摘要，可 JSON）。"""
    if not LANGGRAPH_AVAILABLE:
        return []
    lim = max(1, min(int(limit), 100))
    try:
        app = get_compiled_poc_app()
        saver = app.checkpointer
    except Exception:
        return []
    cfg: Dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    rows: list[Dict[str, Any]] = []
    try:
        for tup in saver.list(cfg, limit=lim):
            ck = tup.checkpoint or {}
            ch = ck.get("channel_values") or {}
            md = tup.metadata or {}
            rows.append(
                {
                    "checkpoint_id": ck.get("id"),
                    "step": md.get("step"),
                    "source": md.get("source"),
                    "phase": ch.get("phase"),
                    "poc_trace": ch.get("poc_trace"),
                }
            )
    except Exception:
        return []
    return rows


def advance_english_graph_poc_step(
    *,
    thread_id: str,
    initial: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], bool, list[str]]:
    """
    单步推进 POC（每个节点后 interrupt）。
    返回 `(本步输出 state, checkpoint 尖端, 是否已跑完全链, 下一步节点名列表)`。
    """
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError("未安装 langgraph，请执行: pip install 'langgraph>=0.2,<0.3'")
    app = get_compiled_poc_app()
    config = {"configurable": {"thread_id": thread_id}}
    tip_before = read_langgraph_checkpoint_tip(thread_id=thread_id)
    if tip_before is None:
        init: Dict[str, Any] = dict(initial or {})
        init.setdefault("phase", "intake")
        init.setdefault("poc_trace", [])
        out = app.invoke(init, config=config)
    else:
        out = app.invoke(None, config=config)
    st = app.get_state(config)
    tip: Optional[Dict[str, Any]] = None
    next_nodes: list[str] = []
    completed = False
    if st is not None and getattr(st, "values", None) is not None:
        tip = _snapshot_to_dict(st)
        next_nodes = list(tip.get("next") or [])
        completed = _is_poc_chain_complete(dict(tip.get("values") or {}), next_nodes=next_nodes)
    return out, tip, completed, next_nodes


def invoke_english_graph_poc(
    *,
    thread_id: str,
    initial: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """跑完整 POC 链（多步 resume）；返回 `(最终输出, checkpoint 尖端快照)`。"""
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError("未安装 langgraph，请执行: pip install 'langgraph>=0.2,<0.3'")
    app = get_compiled_poc_app()
    init: Dict[str, Any] = dict(initial or {})
    init.setdefault("phase", "intake")
    init.setdefault("poc_trace", [])
    config = {"configurable": {"thread_id": thread_id}}
    out = app.invoke(init, config=config)
    for _ in range(len(WIZARD_GRAPH_NODE_NAMES) + 2):
        st = app.get_state(config)
        if st is None:
            break
        nxt = getattr(st, "next", None) or ()
        if not nxt:
            break
        out = app.invoke(None, config=config)
    tip: Optional[Dict[str, Any]] = None
    try:
        st = app.get_state(config)
        if st is not None and getattr(st, "values", None) is not None:
            tip = _snapshot_to_dict(st)
    except Exception:
        tip = None
    return out, tip


def delete_langgraph_poc_thread(*, thread_id: str) -> None:
    """删除 LangGraph checkpointer 中该 `thread_id` 的全部 checkpoint。"""
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError("未安装 langgraph，请执行: pip install 'langgraph>=0.2,<0.3'")
    app = get_compiled_poc_app()
    saver = app.checkpointer
    deleter = getattr(saver, "delete_thread", None)
    if not callable(deleter):
        raise RuntimeError("当前 checkpointer 不支持 delete_thread，无法重置线程")
    deleter(thread_id)
