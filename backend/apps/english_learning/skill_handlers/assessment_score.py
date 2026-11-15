"""
english_assessment_score：客观题判分 + 维度聚合 + 简短薄弱说明（无 Key 时跳过 LLM 总结）。
"""

from .llm_utils import chat_completion


def execute(items=None, responses=None, model: str = "deepseek-chat", **kwargs) -> dict:
    items = list(items or [])
    responses = list(responses or [])
    by_dim = {}
    correct = 0
    total = 0

    resp_by_id = {}
    for r in responses:
        if isinstance(r, dict) and r.get("item_id"):
            resp_by_id[str(r["item_id"])] = r.get("answer")

    for it in items:
        iid = str(it.get("id", ""))
        dim = it.get("dimension") or "general"
        if dim not in by_dim:
            by_dim[dim] = {"correct": 0, "total": 0}

        if it.get("type") == "single_choice":
            total += 1
            by_dim[dim]["total"] += 1
            key = it.get("answer_key")
            got = resp_by_id.get(iid)
            ok = key is not None and got is not None and str(got).strip() == str(key).strip()
            if ok:
                correct += 1
                by_dim[dim]["correct"] += 1

    pct = round(100.0 * correct / total, 1) if total else 0.0
    dim_scores = {}
    weak_dimensions = []
    for dim, st in by_dim.items():
        if st["total"] == 0:
            continue
        d_pct = round(100.0 * st["correct"] / st["total"], 1)
        dim_scores[dim] = d_pct
        if d_pct < 70:
            weak_dimensions.append(dim)

    summary_seed = (
        f"共 {total} 题，答对 {correct} 题，得分约 {pct}%。"
        f"维度得分：{dim_scores}。"
        f"建议加强：{', '.join(weak_dimensions) or '保持均衡练习'}。"
    )

    gap_summary = summary_seed
    llm = chat_completion(
        system="你是英语老师，用 2～4 句中文简要反馈测评结果与下一步建议，语气鼓励。",
        user=summary_seed,
        model=model,
    )
    if llm:
        gap_summary = llm.strip()

    scores = {
        "overall_percent": pct,
        "correct": correct,
        "total": total,
        "by_dimension": dim_scores,
    }
    return {
        "scores": scores,
        "gap_summary": gap_summary,
        "weak_dimensions": weak_dimensions,
    }
