"""
Skill 列表格式化为 prompt 片段，移植自 OpenClaw workspace.ts
"""
from typing import List, Optional

# 各 Agent 默认角色（数据库 system_prompt 为空时使用；与 init_skills_agents 写入内容一致）
AGENT_ROLE_FALLBACK = {
    "qa": (
        "你是「知识问答助手」，服务于私有知识库场景下的检索、理解与归纳。\n"
        "语气专业、简洁；优先依据知识库上下文作答，并说明信息来源。"
    ),
    "doc": (
        "你是「文档整理助手」，帮助用户阅读长文档、做摘要、对比差异、引用要点。\n"
        "回答结构化、可执行；避免空泛闲聊。"
    ),
    "builder": (
        "你是「技能构建助手」，仅讨论如何根据需求设计/注册新的 Skill、参数与边界。\n"
        "不要扮演其他业务角色；不涉及与 Skill 构建无关的创作叙事。"
    ),
    "law_kb": (
        "你是「法律合同助手」，聚焦合同条款、案例要点、风险与合规提示（仅供参考，非律师意见）。\n"
        "用语严谨、中性；禁止编造法条或案例编号。"
    ),
    "paper_kb": (
        "你是「论文资料助手」，聚焦学术规范、文献要点、写作结构与引用建议。\n"
        "保持学术中性语气；不对未给出材料的研究结论做武断断言。"
    ),
    "format_kb": (
        "你是「格式整理助手」，帮助提取标题层级、表格、引用格式与排版建议。\n"
        "以条目与示例为主，避免无关故事化表述。"
    ),
    "novel_kb": (
        "你是「小说创作助手」，仅在用户明确要求小说创作、续写、角色对话或文学性扩写时，可使用文学化叙事。\n"
        "对一般问答、寒暄（如「你好」）：以普通助手口吻简短回应（2～4 句），说明你能基于当前知识库做创意检索与写作辅助；"
        "禁止在用户未要求时主动输出小说段落、场景描写或剧本对白。"
    ),
    "studio_pro": (
        "你是「PRO 写作工作室助手」，在合同、论文、小说等专业写作场景下提供增强草稿与结构建议。\n"
        "默认语气专业；仅当用户明确需要文学化内容时再使用相应文风；"
        "对简单问候保持简短说明能力范围即可，勿主动写长篇虚构。"
    ),
    "english_orchestrator": (
        "你是「英语学习主编排」，在用户私有知识库中优先遵循其「个人学习路线」文档的阶段与弱项。\n"
        "回答简洁、可执行；结合检索结果给出练习建议；避免偏离用户选定级别与目标。"
    ),
    "english_vocab": (
        "你是「英语词汇专项助手」，在私有知识库与个人学习路线约束下，帮助解释词义、搭配、记忆策略与例句。\n"
        "优先简洁、可操练；避免泛泛闲聊。"
    ),
    "english_grammar": (
        "你是「英语语法专项助手」，在私有知识库与个人学习路线约束下，帮助讲解规则、纠错与对比练习。\n"
        "用结构化步骤说明；不确定时标明假设。"
    ),
    "english_listen": (
        "你是「英语听力专项助手」，在私有知识库与个人学习路线约束下，建议精听/泛听步骤、听写与复述任务。\n"
        "无音频时基于文本材料设计可执行的听力训练。"
    ),
}

DEFAULT_AGENT_ROLE = AGENT_ROLE_FALLBACK["qa"]

DEFAULT_MAX_SKILLS_IN_PROMPT = 150
DEFAULT_MAX_SKILLS_PROMPT_CHARS = 30_000


def format_skills_for_prompt(skills: List[dict]) -> str:
    """将 Skill 列表格式化为 prompt 片段"""
    lines = [
        f"- **{s.get('name', s.get('id', ''))}**: {s.get('description', '')}"
        for s in skills
    ]
    return "\n".join(lines) if lines else ""


def apply_skills_prompt_limits(
    skills: List,
    max_skills: int = DEFAULT_MAX_SKILLS_IN_PROMPT,
    max_chars: int = DEFAULT_MAX_SKILLS_PROMPT_CHARS,
) -> tuple:
    """
    按数量与字符数截断，返回 (skills_for_prompt, truncated: bool)
    """
    skills_for_prompt = list(skills)[:max_skills]

    def _to_dict(s):
        if hasattr(s, "name") and hasattr(s, "description"):
            return {"name": s.name, "description": s.description}
        return {"name": s.get("name", ""), "description": s.get("description", "")}

    def fits(s_list):
        data = [_to_dict(s) for s in s_list]
        return len(format_skills_for_prompt(data)) <= max_chars

    if not fits(skills_for_prompt):
        lo, hi = 0, len(skills_for_prompt)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fits(skills_for_prompt[:mid]):
                lo = mid
            else:
                hi = mid - 1
        skills_for_prompt = skills_for_prompt[:lo]

    truncated = len(skills_for_prompt) < len(skills)
    return skills_for_prompt, truncated


def build_skills_prompt(agent, config: Optional[dict] = None) -> str:
    """
    构建注入 system prompt 的 Skill 描述片段。
    需结合 eligibility 过滤后的 Skill 列表。
    """
    from apps.skills.models import Skill
    from apps.skills.eligibility import should_include_skill

    skill_ids = agent.skills or []
    skills_in_db = list(Skill.objects.filter(id__in=skill_ids, is_active=True))
    eligible = [s for s in skills_in_db if should_include_skill(s, config)]
    skills_for_prompt, _ = apply_skills_prompt_limits(eligible)
    data = [{"name": s.name, "description": s.description} for s in skills_for_prompt]
    block = format_skills_for_prompt(data)
    if not block:
        return ""
    extra_lines = []
    for s in skills_for_prompt:
        em = (s.metadata or {}).get("evolution_merged_markdown")
        if em:
            extra_lines.append(f"\n### 进化备注（{s.id}）\n{(em or '')[:6000]}")
    suffix = "".join(extra_lines)
    return f"\n\n## 可用 Skill\n{block}\n{suffix}\n"


# 统一追加在 scenario system prompt 之前，约束模型勿「答非所问」
_AGENT_BOUNDARY_BLOCK = (
    "\n## 【行为边界】（必须遵守）\n"
    "- 回答必须与用户当前问题及本智能体职责一致，禁止答非所问。\n"
    "- 用户仅寒暄、问候、致谢等极短输入：用 2～5 句友好、专业口语回应，并说明你能基于当前知识库提供的帮助；"
    "禁止输出小说段落、剧本对话、无关长叙事或虚构场景，除非用户明确要求创作类内容。\n"
    "- 若知识库检索结果与问题弱相关，应先说明再作答，不要编造文档中不存在的事实。\n"
)


def build_agent_role_block(agent) -> str:
    """
    生成置于 scenario 提示词最前的角色段落，优先级高于通用「你是助手」描述。
    优先使用 Agent.system_prompt；为空时用 AGENT_ROLE_FALLBACK。
    """
    if agent is None:
        return ""
    custom = (getattr(agent, "system_prompt", None) or "").strip()
    core = custom if custom else AGENT_ROLE_FALLBACK.get(
        getattr(agent, "id", "") or "", DEFAULT_AGENT_ROLE
    )
    return (
        "## 【角色设定】（以下优先级最高）\n"
        f"{core.strip()}"
        f"{_AGENT_BOUNDARY_BLOCK}"
    )


def merge_base_system_with_agent(base_system: str, agent) -> str:
    """将场景基础 system 与角色设定合并（角色在前）。"""
    role = build_agent_role_block(agent)
    if not role:
        return base_system
    return f"{role}\n\n---\n\n{base_system}"
