"""系统预置英语 curriculum 知识库定义（小学 → 六级）。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

# 原始数据目录（由 scripts/download_english_curriculum_data.sh 填充）
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "curriculum"
RAW_DIR = DATA_DIR / "raw"
MANIFEST_PATH = DATA_DIR / "manifest.json"

SYSTEM_KB_SETTINGS_KEY = "curriculum_slug"
SYSTEM_KB_FLAG = "is_system_curriculum"

# 默认每篇 Document 词条数（控制向量检索粒度）
DEFAULT_CHUNK_SIZE = 120

SYSTEM_USERNAME = "__english_curriculum_system__"


@dataclass(frozen=True)
class CurriculumTier:
    slug: str
    title: str
    description: str
    source: str  # kylebing_json | kajweb_pep_primary
    source_file: str  # 相对 RAW_DIR
    level_tags: List[str]  # 用于 recommend 匹配


CURRICULUM_TIERS: List[CurriculumTier] = [
    CurriculumTier(
        slug="primary",
        title="小学英语词汇库",
        description="人教版 PEP 小学 3–6 年级词汇（系统预置，只读）",
        source="kajweb_pep_primary",
        source_file="primary_merged.jsonl",
        level_tags=["stage:primary", "小学", "goal:primary"],
    ),
    CurriculumTier(
        slug="junior",
        title="初中英语词汇库",
        description="初中核心词汇（KyleBing/english-vocabulary）",
        source="kylebing_json",
        source_file="1-初中-顺序.json",
        level_tags=["stage:junior", "初中", "goal:junior"],
    ),
    CurriculumTier(
        slug="senior",
        title="高中英语词汇库",
        description="高中核心词汇（KyleBing/english-vocabulary）",
        source="kylebing_json",
        source_file="2-高中-顺序.json",
        level_tags=["stage:senior", "高中", "goal:senior"],
    ),
    CurriculumTier(
        slug="cet4",
        title="大学英语四级词汇库",
        description="CET-4 考纲词汇（KyleBing/english-vocabulary）",
        source="kylebing_json",
        source_file="3-CET4-顺序.json",
        level_tags=["stage:cet4", "goal:CET", "goal:cet4", "四级", "CET4"],
    ),
    CurriculumTier(
        slug="cet6",
        title="大学英语六级词汇库",
        description="CET-6 考纲词汇（KyleBing/english-vocabulary）",
        source="kylebing_json",
        source_file="4-CET6-顺序.json",
        level_tags=["stage:cet6", "goal:cet6", "六级", "CET6"],
    ),
]

TIER_BY_SLUG = {t.slug: t for t in CURRICULUM_TIERS}


def tier_for_level_tags(level_tags: Optional[List[str]]) -> CurriculumTier:
    """根据 profile.level_tags / session 标签推荐 curriculum tier。"""
    joined = " ".join(str(t) for t in (level_tags or [])).lower()
    if any(k in joined for k in ("cet6", "六级", "stage:cet6", "goal:cet6")):
        return TIER_BY_SLUG["cet6"]
    if any(k in joined for k in ("cet4", "四级", "goal:cet", "stage:cet4")):
        return TIER_BY_SLUG["cet4"]
    if any(k in joined for k in ("senior", "高中", "stage:senior", "gaozhong")):
        return TIER_BY_SLUG["senior"]
    if any(k in joined for k in ("primary", "小学", "stage:primary", "xiaoxue", "三年级", "四年级", "五年级", "六年级")):
        return TIER_BY_SLUG["primary"]
    if any(k in joined for k in ("junior", "初中", "stage:junior", "chuzhong", "初一", "初二", "初三", ":7", ":8", ":9")):
        return TIER_BY_SLUG["junior"]
    return TIER_BY_SLUG["junior"]
