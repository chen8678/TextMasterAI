"""R2-rule：用 max(retrieve_score) 离线扫 τ_rule（P12）。"""

from __future__ import annotations

from typing import Any, Optional


def max_retrieve_score(row: dict[str, Any]) -> float:
    scores = row.get("retrieve_scores") or []
    if not scores:
        return 0.0
    return float(max(scores))


def replay_r2_rule(rows: list[dict[str, Any]], tau_rule: float) -> list[dict[str, Any]]:
    out = []
    for r in rows:
        mx = max_retrieve_score(r)
        pred = mx >= float(tau_rule)
        row = dict(r)
        row["answerable_pred"] = pred  # 复用汇总列语义：rule 放行 ≈ 判可答
        row["generated"] = bool(pred)
        row["status"] = "answer" if pred else "refuse_evidence"
        row["threshold"] = float(tau_rule)
        row["max_retrieve_score"] = mx
        out.append(row)
    return out


def metrics_at_tau_rule(rows: list[dict[str, Any]], tau_rule: float) -> dict[str, Any]:
    replayed = replay_r2_rule(rows, tau_rule)
    n = len(replayed)
    type_a = [r for r in replayed if r.get("type") == "A"]
    type_b = [r for r in replayed if r.get("type") == "B"]
    n_gen = sum(1 for r in replayed if r.get("generated"))
    b_leak = sum(1 for r in type_b if r.get("answerable_pred") is True)
    a_block = sum(1 for r in type_a if r.get("answerable_pred") is False)

    def rate(num: int, den: int) -> Optional[float]:
        return round(num / den, 4) if den else None

    return {
        "tau_rule": float(tau_rule),
        "n": n,
        "B_leak_rate": rate(b_leak, len(type_b)),
        "B_leak_n": b_leak,
        "B_n": len(type_b),
        "A_false_block_rate": rate(a_block, len(type_a)),
        "A_false_block_n": a_block,
        "A_n": len(type_a),
        "gen_call_rate": rate(n_gen, n),
        "n_generated": n_gen,
    }


def scan_tau_rule(rows: list[dict[str, Any]], taus: list[float]) -> list[dict[str, Any]]:
    return [metrics_at_tau_rule(rows, t) for t in taus]


def choose_tau_rule(
    curve: list[dict[str, Any]],
    *,
    max_b_leak: float = 0.10,
    max_a_block: float = 0.20,
) -> tuple[float, str]:
    feasible = [
        r
        for r in curve
        if (r.get("B_leak_rate") is not None and r["B_leak_rate"] <= max_b_leak)
        and (r.get("A_false_block_rate") is not None and r["A_false_block_rate"] <= max_a_block)
    ]
    if feasible:
        # 在可行集中取 Gen 最低（更省）且 τ 居中
        chosen = min(feasible, key=lambda r: (r["gen_call_rate"], -r["tau_rule"]))
        reason = (
            f"仅 **dev** 离线重放 max(retrieve_score)；可行集 "
            f"(B漏≤{max_b_leak}, A误拦≤{max_a_block}) 内取 Gen 最低的 τ_rule={chosen['tau_rule']}。"
            f"B漏={chosen['B_leak_rate']} A误拦={chosen['A_false_block_rate']} Gen={chosen['gen_call_rate']}。"
            f"未使用 test。"
        )
        return float(chosen["tau_rule"]), reason

    # 无可行点：取漏放+误拦加权最小（诚实报告 rule 难分 A/B）
    def cost(r: dict[str, Any]) -> tuple:
        return (
            float(r.get("B_leak_rate") or 1) + float(r.get("A_false_block_rate") or 1),
            float(r.get("gen_call_rate") or 1),
        )

    chosen = min(curve, key=cost)
    reason = (
        f"dev 上 **无** τ_rule 同时满足 B漏≤{max_b_leak} 与 A误拦≤{max_a_block} "
        f"（检索分对 A/B 重叠大）。退而取漏放+误拦之和最小的 τ_rule={chosen['tau_rule']} "
        f"(B漏={chosen['B_leak_rate']} A误拦={chosen['A_false_block_rate']} Gen={chosen['gen_call_rate']})。"
        f"这正说明 Answerable 不是 max(score) 马甲。未使用 test。"
    )
    return float(chosen["tau_rule"]), reason


def format_curve_md(curve: list[dict[str, Any]], *, chosen: float | None = None, reason: str = "") -> str:
    lines = [
        "# R2-rule τ_rule 扫描（dev · 离线 max(score)）",
        "",
        "| τ_rule | B 漏放 | A 误拦 | Gen 调用率 |",
        "|--------|--------|--------|------------|",
    ]
    for r in curve:
        mark = " ← chosen" if chosen is not None and abs(r["tau_rule"] - chosen) < 1e-12 else ""
        lines.append(
            f"| {r['tau_rule']:.3f} | {r['B_leak_rate']:.4f} | {r['A_false_block_rate']:.4f} | "
            f"{r['gen_call_rate']:.4f} |{mark}"
        )
    lines.append("")
    if reason:
        lines.extend(["## 选择理由", "", reason, ""])
    lines.extend(
        [
            "## 口径",
            "",
            "- `pass = max(retrieve_scores) >= τ_rule`",
            "- Gen≈pass；不调用 Answerable LLM",
            "- **禁止**用 test 选 τ_rule",
            "",
        ]
    )
    return "\n".join(lines)
