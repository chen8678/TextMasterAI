"""
KB 问答采集器 — 按知识库匹配「提问角色」配置。

角色影响：LLM 生成问题的口吻、种子问题文件、SFT instruction、默认 agent。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings

DEFAULT_INSTRUCTION = (
    "你是知识库问答助手。请根据提供的检索上下文准确回答用户问题；"
    "若上下文不足，请明确说明不知道，不要编造。"
)

PERSONAS_DIR = Path(settings.BASE_DIR) / "data" / "training_collector" / "personas"
SEEDS_DIR = Path(settings.BASE_DIR) / "data" / "training_collector" / "seeds"


@dataclass
class CollectorPersona:
    id: str
    role_name: str
    role_description: str
    knowledge_base_ids: List[str] = field(default_factory=list)
    title_keywords: List[str] = field(default_factory=list)
    question_style: str = ""
    question_examples: List[str] = field(default_factory=list)
    instruction: str = DEFAULT_INSTRUCTION
    agent_id: str = "qa"
    seed_path: str = ""
    llm_question_count: int = 12

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role_name": self.role_name,
            "role_description": self.role_description,
            "knowledge_base_ids": self.knowledge_base_ids,
            "title_keywords": self.title_keywords,
            "question_style": self.question_style,
            "question_examples": self.question_examples,
            "instruction": self.instruction,
            "agent_id": self.agent_id,
            "seed_path": self.seed_path,
            "llm_question_count": self.llm_question_count,
        }


def _persona(
    *,
    id: str,
    role_name: str,
    role_description: str,
    kb_id: str,
    title_keyword: str,
    question_style: str,
    question_examples: List[str],
    instruction: str,
    seed_file: str,
    agent_id: str = "qa",
    llm_question_count: int = 12,
) -> CollectorPersona:
    return CollectorPersona(
        id=id,
        role_name=role_name,
        role_description=role_description,
        knowledge_base_ids=[kb_id],
        title_keywords=[title_keyword],
        question_style=question_style,
        question_examples=question_examples,
        instruction=instruction,
        agent_id=agent_id,
        seed_path=f"data/training_collector/seeds/{seed_file}",
        llm_question_count=llm_question_count,
    )


BUILTIN_PERSONAS: List[CollectorPersona] = [
    _persona(
        id="english_primary_parent",
        role_name="小学生家长",
        role_description="孩子读小学 3–6 年级，想查 PEP 课本单词怎么读、怎么用",
        kb_id="4fe6ed80-a6e2-4ccb-a354-be3198d5d9f8",
        title_keyword="小学英语",
        question_style=(
            "用家长口吻提问，句子短、口语化，常问「怎么读」「什么意思」「"
            "三年级/四年级课本里有没有这个词」。可夹杂简单中文。"
        ),
        question_examples=[
            "pencil 有哪些常用短语？",
            "fruit 是什么意思？",
            "spring 和 summer 分别是什么意思？",
        ],
        instruction=(
            "你是小学英语词汇助教，面向小学生家长。请用简单易懂的中文解释单词读音、"
            "词义和例句；必要时给出音标或拼读提示。依据检索到的词汇库内容作答，不要编造。"
        ),
        seed_file="english_primary.json",
        llm_question_count=10,
    ),
    _persona(
        id="english_junior_student",
        role_name="初二学生",
        role_description="正在积累中考词汇，关心词义、搭配和易混词",
        kb_id="6178a9c2-4446-4df8-9a03-44525f09277d",
        title_keyword="初中英语",
        question_style=(
            "以初中生口吻提问，关注中考常考词、固定搭配、形近词/近义词辨析，"
            "可问「这个词怎么用」「和 xxx 有什么区别」。"
        ),
        question_examples=[
            "accept 和 except 怎么区分？",
            "silence 和 silent 有什么区别？",
            "deal with 是什么意思？",
        ],
        instruction=(
            "你是初中英语学习助手。请结合检索到的词汇解释词义、用法和常见搭配，"
            "辨析易混词时给出简短例句。适合中考备考，不要超出知识库编造内容。"
        ),
        seed_file="english_junior.json",
        llm_question_count=12,
    ),
    _persona(
        id="english_senior_student",
        role_name="高三备考学生",
        role_description="备战高考英语，需要高频词、写作词和熟词生义",
        kb_id="fdba18e8-9de2-49a5-864a-33e2afeead21",
        title_keyword="高中英语",
        question_style=(
            "以高三学生口吻提问，偏高考场景：写作高级替换词、熟词生义、"
            "完形填空易错词、词性转换等。"
        ),
        question_examples=[
            "influence 和 effect 有什么区别？",
            "patient 和 patience 怎么区分？",
            "address 除了地址还有什么意思？",
        ],
        instruction=(
            "你是高中英语词汇教练，面向高考备考。请基于检索内容讲解词义、搭配、"
            "熟词生义与写作替换表达，并给出贴近高考题的例句。信息不足时明确说明。"
        ),
        seed_file="english_senior.json",
        llm_question_count=12,
    ),
    _persona(
        id="english_cet4_student",
        role_name="大二 CET-4 备考者",
        role_description="准备大学英语四级，关注考纲词、听力阅读和翻译词汇",
        kb_id="e34d217d-161e-4995-995d-5caabdc19a5f",
        title_keyword="四级",
        question_style=(
            "以大学生口吻提问四级备考：核心词汇、听力易混词、阅读同义替换、"
            "翻译固定搭配。可提及「四级」「CET-4」。"
        ),
        question_examples=[
            "available 有哪些固定搭配？",
            "influence 和 impact 怎么区分？",
            "affect 和 effect 怎么区分？",
        ],
        instruction=(
            "你是大学英语四级词汇助教。请依据检索到的 CET-4 词库解释词义、"
            "搭配和考点，可标注听/读/写常见用法。不要编造考纲外的内容。"
        ),
        seed_file="english_cet4.json",
        llm_question_count=15,
    ),
    _persona(
        id="english_cet6_student",
        role_name="研一 CET-6 备考者",
        role_description="冲击六级高分，关注学术词汇、长难句关键词和高级表达",
        kb_id="e3535603-81b0-442c-88a3-3fb894824497",
        title_keyword="六级",
        question_style=(
            "以研究生或大四学生口吻提问六级：学术词汇、抽象名词、高级副词、"
            "写作与翻译地道表达，问题可稍长、更专业。"
        ),
        question_examples=[
            "comprehensive 和 extensive 有什么区别？",
            "justice 有哪些常见搭配？",
            "hypothesis 是什么意思？",
        ],
        instruction=(
            "你是大学英语六级词汇教练。请基于检索内容讲解学术词汇、抽象表达和"
            "高级搭配，例句可偏书面语。若词库无依据，请直说不知道。"
        ),
        seed_file="english_cet6.json",
        llm_question_count=15,
    ),
]

_PERSONA_BY_ID: Dict[str, CollectorPersona] = {p.id: p for p in BUILTIN_PERSONAS}
_PERSONA_BY_KB_ID: Dict[str, CollectorPersona] = {}
for _p in BUILTIN_PERSONAS:
    for _kb in _p.knowledge_base_ids:
        _PERSONA_BY_KB_ID[_kb.lower()] = _p


def list_personas() -> List[Dict[str, Any]]:
    return [p.to_dict() for p in BUILTIN_PERSONAS]


def get_persona_by_id(persona_id: str) -> Optional[CollectorPersona]:
    return _PERSONA_BY_ID.get((persona_id or "").strip())


def resolve_persona_for_kb(
    *,
    knowledge_base_id: str = "",
    knowledge_base_title: str = "",
    persona_id: str = "",
) -> Optional[CollectorPersona]:
    if persona_id:
        found = get_persona_by_id(persona_id)
        if found:
            return found
    kb_key = (knowledge_base_id or "").strip().lower()
    if kb_key and kb_key in _PERSONA_BY_KB_ID:
        return _PERSONA_BY_KB_ID[kb_key]
    title = (knowledge_base_title or "").strip()
    if title:
        for persona in BUILTIN_PERSONAS:
            if any(kw in title for kw in persona.title_keywords):
                return persona
    return None


def build_workflow_config_from_persona(
    persona: CollectorPersona,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """将角色配置转为采集工作流可用的 JSON 配置。"""
    overrides = overrides or {}
    cfg = {
        "persona_id": persona.id,
        "role_name": persona.role_name,
        "question_source": overrides.get("question_source", "inline"),
        "questions": overrides.get("questions") or [],
        "seed_path": overrides.get("seed_path") or persona.seed_path,
        "llm_question_count": int(
            overrides.get("llm_question_count") or persona.llm_question_count
        ),
        "agent_id": overrides.get("agent_id") or persona.agent_id,
        "instruction": overrides.get("instruction") or persona.instruction,
        "ai_model": overrides.get("ai_model", "deepseek"),
        "config": overrides.get("config") or {"max_tokens": 2000, "temperature": 0.3},
        "retrieval_params": overrides.get("retrieval_params")
        or {
            "strategy": "hybrid",
            "top_k": 5,
            "score_threshold": 0.15,
            "alpha": 0.5,
        },
        "delay_seconds": float(overrides.get("delay_seconds", 0.5)),
        "max_questions": int(overrides.get("max_questions", 20)),
        "output_path": overrides.get("output_path", ""),
        "dry_run": bool(overrides.get("dry_run", False)),
    }
    if (
        not cfg["questions"]
        and cfg.get("seed_path")
        and cfg["question_source"] == "inline"
    ):
        pass
    elif (
        not cfg["questions"]
        and not cfg.get("seed_path")
        and cfg["question_source"] == "inline"
        and cfg["llm_question_count"] > 0
    ):
        cfg["question_source"] = "llm_from_kb"
    return cfg


def build_question_generation_prompt(
    persona: CollectorPersona,
    kb_text: str,
    count: int,
) -> tuple[str, str]:
    examples = "\n".join(f"- {q}" for q in persona.question_examples[:5])
    prompt = f"""你正在扮演「{persona.role_name}」为知识库问答采集训练数据。
角色说明：{persona.role_description}
提问风格：{persona.question_style}

请参考下列示例问题的语气（不要照抄）：
{examples}

请根据以下知识库内容，生成 {count} 个该角色会问的问题。

要求：
1. 问题必须符合上述角色身份与口吻
2. 问题应能在知识库材料中找到答案依据
3. 覆盖不同词汇/知识点，避免重复
4. 只输出 JSON 字符串数组，不要 markdown 代码块

知识库内容：
---
{kb_text[:15000]}
---"""
    system = (
        f"你是数据标注员，模拟「{persona.role_name}」提问。"
        "只输出合法 JSON 字符串数组，例如 [\"问题1\", \"问题2\"]。"
    )
    return prompt, system


def load_persona_registry(path: str = "") -> Dict[str, Any]:
    registry_path = Path(path) if path else PERSONAS_DIR / "english_curriculum.json"
    if not registry_path.is_file():
        alt = Path(settings.BASE_DIR) / registry_path
        registry_path = alt if alt.is_file() else registry_path
    if not registry_path.is_file():
        return {"personas": [p.to_dict() for p in BUILTIN_PERSONAS]}
    with registry_path.open("r", encoding="utf-8") as f:
        return json.load(f)
