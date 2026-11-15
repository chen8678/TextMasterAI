from apps.skills.registry import SkillRegistry

from .profile_tags import execute as english_profile_from_tags_execute
from .assessment_build import execute as english_assessment_build_execute
from .assessment_score import execute as english_assessment_score_execute
from .roadmap_draft import execute as english_roadmap_draft_execute
from .roadmap_finalize import execute as english_roadmap_finalize_execute
from .active_recall_pack import execute as english_active_recall_pack_execute


def register_english_skills():
    SkillRegistry.register(
        "english_profile_from_tags",
        english_profile_from_tags_execute,
        {"name": "英语档案：标签归一化"},
    )
    SkillRegistry.register(
        "english_assessment_build",
        english_assessment_build_execute,
        {"name": "英语测评组卷"},
    )
    SkillRegistry.register(
        "english_assessment_score",
        english_assessment_score_execute,
        {"name": "英语测评评分"},
    )
    SkillRegistry.register(
        "english_roadmap_draft",
        english_roadmap_draft_execute,
        {"name": "英语学习路线草案"},
    )
    SkillRegistry.register(
        "english_roadmap_finalize",
        english_roadmap_finalize_execute,
        {"name": "英语学习路线定稿入库"},
    )
    SkillRegistry.register(
        "english_active_recall_pack",
        english_active_recall_pack_execute,
        {"name": "英语主动回忆包（规则模板）"},
    )
