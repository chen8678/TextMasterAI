"""
Phase-C G1：向导状态机与 LangGraph 对齐的类型与节点名常量。
业务流仍以 Django 视图 + `session_state` 为主；`langgraph` 为可选（见 `LANGGRAPH_AVAILABLE`）。
"""

from .langgraph_poc import LANGGRAPH_AVAILABLE
from .nodes import WIZARD_GRAPH_NODE_NAMES

__all__ = ("LANGGRAPH_AVAILABLE", "WIZARD_GRAPH_NODE_NAMES")
