#!/usr/bin/env python3
"""P09 单元：3 条假数据手算对齐。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from apps.dsrag.score import answers_match, score_predictions  # noqa: E402
from apps.dsrag.summarize import summarize_scored  # noqa: E402


def main() -> None:
    assert answers_match("连续使用不得超过四小时。", "四小时，除非特批") or answers_match(
        "四小时除非特批", "四小时，除非特批"
    )
    assert answers_match("四小时，除非特批", "四小时，除非特批")
    assert not answers_match("不知道", "四小时，除非特批")

    taskset = [
        {"id": "A-1", "type": "A", "split": "dev", "gold_answer": "双人双锁", "answerable": 1},
        {"id": "B-1", "type": "B", "split": "dev", "gold_answer": None, "answerable": 0},
        {"id": "A-2", "type": "A", "split": "dev", "gold_answer": "五分钟内", "answerable": 1},
    ]
    preds = [
        {
            "id": "A-1",
            "config_id": "R2",
            "status": "answer",
            "generated": True,
            "answer_text": "实行双人双锁。",
            "answerable_pred": True,
            "latency_ms": 100,
            "cost_est": 0.001,
        },
        {
            "id": "B-1",
            "config_id": "R2",
            "status": "refuse_evidence",
            "generated": False,
            "answer_text": "",
            "answerable_pred": False,
            "latency_ms": 50,
            "cost_est": 0.0002,
        },
        {
            "id": "A-2",
            "config_id": "R2",
            "status": "refuse_evidence",
            "generated": False,
            "answer_text": "",
            "answerable_pred": False,  # A 误拦
            "latency_ms": 80,
            "cost_est": 0.0003,
        },
    ]
    scored = score_predictions(taskset, preds)
    s = summarize_scored(scored)
    # 手算：n=3, gen=1/3, B漏放=0/1, A误拦=1/2, A成功=1/2（A-1对、A-2拒答失败）
    assert s["n"] == 3
    assert s["gen_call_rate"] == round(1 / 3, 4)
    assert s["B_leak_rate"] == 0.0
    assert s["A_false_block_rate"] == 0.5
    assert s["A_success_rate"] == 0.5
    assert s["cost_per_1k_usd"] == round((0.001 + 0.0002 + 0.0003) / 3 * 1000, 6)
    print("unit_ok", s)


if __name__ == "__main__":
    main()
