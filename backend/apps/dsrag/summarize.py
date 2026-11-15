"""汇总表：从 scored cases 生成 summary.json / summary.md（P09）。"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

from apps.dsrag.score import score_predictions


def _rate(num: int, den: int) -> Optional[float]:
    if den <= 0:
        return None
    return round(num / den, 4)


def _percentile(values: list[float], p: float) -> Optional[float]:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return round(xs[0], 3)
    # nearest-rank
    k = max(1, min(len(xs), int(math.ceil(p / 100.0 * len(xs)))))
    return round(xs[k - 1], 3)


def summarize_scored(scored: list[dict[str, Any]], *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    n = len(scored)
    type_a = [r for r in scored if r.get("type") == "A"]
    type_b = [r for r in scored if r.get("type") == "B"]
    type_c = [r for r in scored if r.get("type") == "C"]

    n_gen = sum(1 for r in scored if r.get("generated"))
    # B 漏放：有 answerable_pred 的 B 题中判可答
    b_judged = [r for r in type_b if r.get("answerable_pred") is not None]
    b_leak_n = sum(1 for r in b_judged if r.get("answerable_pred") is True)
    # A 误拦：有 answerable_pred 的 A 题中判不可答
    a_judged = [r for r in type_a if r.get("answerable_pred") is not None]
    a_block_n = sum(1 for r in a_judged if r.get("answerable_pred") is False)

    # R0 无 D3 → B/A 门禁列标 null（表里写 —）
    has_d3 = any(r.get("answerable_pred") is not None for r in scored)

    lat = [float(r.get("latency_ms") or 0.0) for r in scored]
    costs = [float(r.get("cost_est") or 0.0) for r in scored]
    total_cost = sum(costs)
    cost_per_1k = round(total_cost / n * 1000.0, 6) if n else None

    a_with_gold = [r for r in type_a if r.get("a_success") is not None]
    a_success_n = sum(1 for r in a_with_gold if r.get("a_success"))
    # 条件正确率：实际给出 answer 的 A
    a_answered = [r for r in type_a if r.get("status") == "answer" and r.get("generated")]
    a_cond_ok = sum(1 for r in a_answered if r.get("a_correct"))

    # C 实质答案率：C 题中「调用了生成且非拒答短路」；R0-prompt 用模板拒答解析
    from apps.dsrag.generate_adapter import is_template_refuse

    c_sub_n = 0
    for r in type_c:
        if not r.get("generated"):
            continue
        if r.get("status") in ("refuse_scope", "refuse_evidence"):
            continue
        if is_template_refuse(str(r.get("answer_text") or "")):
            continue
        c_sub_n += 1

    out: dict[str, Any] = {
        "n": n,
        "n_A": len(type_a),
        "n_B": len(type_b),
        "n_C": len(type_c),
        "gen_call_rate": _rate(n_gen, n),
        "n_generated": n_gen,
        "short_circuit_rate": _rate(n - n_gen, n) if n else None,
        "B_leak_rate": _rate(b_leak_n, len(b_judged)) if has_d3 else None,
        "B_leak_n": b_leak_n if has_d3 else None,
        "B_judged_n": len(b_judged) if has_d3 else None,
        "A_false_block_rate": _rate(a_block_n, len(a_judged)) if has_d3 else None,
        "A_false_block_n": a_block_n if has_d3 else None,
        "A_judged_n": len(a_judged) if has_d3 else None,
        "latency_p50_ms": _percentile(lat, 50),
        "latency_p95_ms": _percentile(lat, 95),
        "cost_total_usd": round(total_cost, 6),
        "cost_per_1k_usd": cost_per_1k,
        "A_success_rate": _rate(a_success_n, len(a_with_gold)),
        "A_success_n": a_success_n,
        "A_with_gold_n": len(a_with_gold),
        "A_conditional_correct_rate": _rate(a_cond_ok, len(a_answered)),
        "has_answerable_gate": has_d3,
        "scope_metrics": "N/A_this_week",  # 本周无 D0
        "C_gen_rate": _rate(sum(1 for r in type_c if r.get("generated")), len(type_c)),
        "C_substantive_rate": _rate(c_sub_n, len(type_c)) if type_c else None,
        "C_substantive_n": c_sub_n,
    }
    if meta:
        out = {**meta, **out}
    return out


def summarize_run(
    *,
    predictions: list[dict[str, Any]],
    taskset: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    scored = score_predictions(taskset, predictions)
    # 若 pred 是全量而 taskset 过滤了 split，以 pred ids ∩ taskset
    summary = summarize_scored(scored, meta=meta)
    return summary, scored


def format_cell(v: Any, *, na: str = "—", kind: str = "auto") -> str:
    if v is None:
        return na
    if isinstance(v, float):
        if kind == "rate" or (kind == "auto" and 0 <= v <= 1.5):
            return f"{v:.4f}"
        if kind == "ms" or (kind == "auto" and v >= 10):
            return f"{v:.1f}"
        return f"{v:.4f}"
    return str(v)


def render_preview_table(rows: list[dict[str, Any]]) -> str:
    """预检主表（与 02 对齐；本周可少 Scope Acc）。"""
    lines = [
        "| Config | B 漏放 | A 误拦 | Gen 调用率 | P50 ms | $/k | A 成功率 |",
        "|--------|--------|--------|------------|--------|-----|----------|",
    ]
    for r in rows:
        cfg = r.get("config_label") or r.get("config_id") or "?"
        lines.append(
            "| {cfg} | {b} | {a} | {g} | {p50} | {cost} | {suc} |".format(
                cfg=cfg,
                b=format_cell(r.get("B_leak_rate"), kind="rate"),
                a=format_cell(r.get("A_false_block_rate"), kind="rate"),
                g=format_cell(r.get("gen_call_rate"), kind="rate"),
                p50=format_cell(r.get("latency_p50_ms"), kind="ms"),
                cost=format_cell(r.get("cost_per_1k_usd"), kind="rate"),
                suc=format_cell(r.get("A_success_rate"), kind="rate"),
            )
        )
    return "\n".join(lines) + "\n"


def write_summary_files(
    summary: dict[str, Any],
    out_dir: Path | str,
    *,
    preview_rows: list[dict[str, Any]] | None = None,
    scored: list[dict[str, Any]] | None = None,
) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jp = out_dir / "summary.json"
    mp = out_dir / "summary.md"
    jp.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    rows = preview_rows or [summary]
    md = [
        f"# Summary · {summary.get('run_id') or summary.get('config_id') or 'run'}",
        "",
        "## 预检表",
        "",
        render_preview_table(rows),
        "",
        "## 口径",
        "",
        "- B 漏放 = type=B 且 answerable_pred=true 的比例（无 D3 时为 —）",
        "- A 误拦 = type=A 且 answerable_pred=false 的比例",
        "- Gen 调用率 = generated 题数 / 总题数",
        "- A 成功率 = A 题中（status=answer 且归一化匹配 gold）比例；拒答/答错计失败",
        "- $/k = 单题 cost_est 均值 × 1000（USD）",
        "- Scope 指标本周 N/A（无 D0）",
        "",
        f"- n={summary.get('n')} · policy_hash=`{summary.get('policy_hash')}`",
        "",
    ]
    mp.write_text("\n".join(md), encoding="utf-8")
    paths = {"summary_json": jp, "summary_md": mp}
    if scored is not None:
        sp = out_dir / "scored_cases.jsonl"
        with sp.open("w", encoding="utf-8") as f:
            for row in scored:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        paths["scored_cases"] = sp
    return paths
