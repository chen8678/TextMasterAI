"""DRF 响应辅助。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from rest_framework import status
from rest_framework.response import Response


def blocked_input_response(detail: Dict[str, Any]) -> Response:
    return Response(
        {
            "error": detail.get("message") or "内容未通过安全检测",
            "content_safety": {
                "blocked": True,
                "direction": detail.get("direction", "input"),
                "category": detail.get("category"),
                "category_label": detail.get("category_label"),
            },
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def merge_output_safety_result(result: dict, *, replaced: bool, detail: Optional[Dict[str, Any]]) -> dict:
    if not replaced:
        return result
    out = dict(result)
    out["content_safety"] = {
        "blocked": True,
        "direction": "output",
        "category": (detail or {}).get("category"),
        "category_label": (detail or {}).get("category_label"),
    }
    return out
