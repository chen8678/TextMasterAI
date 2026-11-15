"""Answerable 阈值离线重放（P08）：不重调 LLM，仅用已存 answerable_prob。"""

from __future__ import annotations

from typing import Any, Optional


def replay_at_threshold(rows: list[dict[str, Any]], tau: float) -> list[dict[str, Any]]:
    """按 τ 重放 answerable_pred / generated（生成调用 ≈ pred）。"""
    out: list[dict[str, Any]] = []
    for r in rows:
        prob = r.get("answerable_prob")
        if prob is None:
            raise ValueError(f"missing answerable_prob: id={r.get('id')}")
        pred = float(prob) >= float(tau)
        row = dict(r)
        row["answerable_pred"] = pred
        row["answerable_label"] = "answerable" if pred else "not_answerable"
        # 离线近似：可答则会计一次 generate；不可答短路
        row["generated"] = bool(pred)
        row["status"] = "answer" if pred else "refuse_evidence"
        row["threshold"] = float(tau)
        out.append(row)
    return out


def metrics_at_tau(rows: list[dict[str, Any]], tau: float) -> dict[str, Any]:
    replayed = replay_at_threshold(rows, tau)
    n = len(replayed)
    type_a = [r for r in replayed if r.get("type") == "A"]
    type_b = [r for r in replayed if r.get("type") == "B"]
    n_gen = sum(1 for r in replayed if r.get("generated"))
    b_leak = sum(1 for r in type_b if r.get("answerable_pred") is True)
    a_block = sum(1 for r in type_a if r.get("answerable_pred") is False)

    def rate(num: int, den: int) -> Optional[float]:
        return round(num / den, 4) if den else None

    return {
        "tau": float(tau),
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


def scan_thresholds(
    rows: list[dict[str, Any]],
    taus: list[float],
) -> list[dict[str, Any]]:
    return [metrics_at_tau(rows, t) for t in taus]


def choose_tau(
    curve: list[dict[str, Any]],
    *,
    max_b_leak: float = 0.10,
    max_a_block: float = 0.20,
    prefer: str = "mid_safe",
) -> tuple[float, str]:
    """
    预检选点：B 漏放 ≤ max_b_leak 且 A 误拦 ≤ max_a_block。
    prefer=mid_safe：在可行集中取中位 τ；若空则取误拦+漏放加权最小。
    """
    feasible = [
        r
        for r in curve
        if (r.get("B_leak_rate") is not None and r["B_leak_rate"] <= max_b_leak)
        and (r.get("A_false_block_rate") is not None and r["A_false_block_rate"] <= max_a_block)
    ]
    if feasible:
        if prefer == "highest_tau":
            # 更保守：更高 τ → 更少放行（同带内 Gen 可能不变）
            chosen = max(feasible, key=lambda r: r["tau"])
            reason = (
                f"可行集（B漏≤{max_b_leak} 且 A误拦≤{max_a_block}）内取最高 τ={chosen['tau']}，"
                f"偏保守；B漏={chosen['B_leak_rate']} A误拦={chosen['A_false_block_rate']} "
                f"Gen={chosen['gen_call_rate']}。"
            )
        else:
            # mid of feasible taus
            taus = sorted(r["tau"] for r in feasible)
            mid = taus[len(taus) // 2]
            chosen = next(r for r in feasible if r["tau"] == mid)
            reason = (
                f"仅用 **dev** 离线重放；可行集 τ∈[{taus[0]}, {taus[-1]}] "
                f"（B漏≤{max_b_leak} 且 A误拦≤{max_a_block}）取中位 τ={mid}。"
                f"该点 B漏={chosen['B_leak_rate']} A误拦={chosen['A_false_block_rate']} "
                f"Gen={chosen['gen_call_rate']}。未使用 test。"
            )
        return float(chosen["tau"]), reason

    # fallback: minimize B_leak + A_block
    def cost(r: dict[str, Any]) -> float:
        return float(r.get("B_leak_rate") or 1) + float(r.get("A_false_block_rate") or 1)

    chosen = min(curve, key=cost)
    reason = (
        f"无点同时满足 B漏≤{max_b_leak} 与 A误拦≤{max_a_block}；"
        f"退而取漏放+误拦之和最小的 τ={chosen['tau']} "
        f"(B漏={chosen['B_leak_rate']} A误拦={chosen['A_false_block_rate']})。"
        f"建议先修提示/题集后再锁 τ。未使用 test。"
    )
    return float(chosen["tau"]), reason


def format_curve_md(curve: list[dict[str, Any]], *, chosen: float | None = None, reason: str = "") -> str:
    lines = [
        "# Answerable τ 扫描（dev · 离线重放）",
        "",
        "| τ | B 漏放 | A 误拦 | Gen 调用率 |",
        "|---|--------|--------|------------|",
    ]
    for r in curve:
        mark = " ← chosen" if chosen is not None and abs(r["tau"] - chosen) < 1e-9 else ""
        lines.append(
            f"| {r['tau']:.2f} | {r['B_leak_rate']:.4f} | {r['A_false_block_rate']:.4f} | "
            f"{r['gen_call_rate']:.4f} |{mark}"
        )
    lines.append("")
    if reason:
        lines.extend(["## 选择理由", "", reason, ""])
    lines.extend(
        [
            "## 口径",
            "",
            "- 数据源：已有 R2 predictions 的 `answerable_prob`（校准后的 p_yes）",
            "- 重放：`answerable_pred = (prob >= τ)`；`Gen≈pred`（不重调 LLM）",
            "- **禁止**用 test 选 τ",
            "",
        ]
    )
    return "\n".join(lines)


def format_curve_csv(curve: list[dict[str, Any]]) -> str:
    lines = ["tau,B_leak_rate,A_false_block_rate,gen_call_rate,B_leak_n,A_false_block_n,n_generated,n"]
    for r in curve:
        lines.append(
            f"{r['tau']},{r['B_leak_rate']},{r['A_false_block_rate']},{r['gen_call_rate']},"
            f"{r['B_leak_n']},{r['A_false_block_n']},{r['n_generated']},{r['n']}"
        )
    return "\n".join(lines) + "\n"
