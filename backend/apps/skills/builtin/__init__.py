# 内置 Skill 实现
from .rag_answer import execute as rag_answer_execute
from .cite_snippets import execute as cite_snippets_execute
from .read_local_file import execute as read_local_file_execute
from .summarize import execute as summarize_execute
from .compare_docs import execute as compare_docs_execute
from .content_generation import execute as content_generation_execute
from .skill_creator import execute as skill_creator_execute
from .text_law_assist import execute as text_law_assist_execute
from .text_paper_assist import execute as text_paper_assist_execute
from .text_format_assist import execute as text_format_assist_execute
from .text_novel_assist import execute as text_novel_assist_execute
from .novel_continuer import execute as novel_continuer_execute
from .paper_section_generator import execute as paper_section_generator_execute
from .contract_filler import execute as contract_filler_execute
from .scar_retrieve import execute as scar_retrieve_execute
from .scar_generate import execute as scar_generate_execute

from apps.skills.registry import SkillRegistry

# 注册内置 Skill
SkillRegistry.register("rag_answer", rag_answer_execute, {"name": "知识库检索"})
SkillRegistry.register("cite_snippets", cite_snippets_execute, {"name": "引用生成"})
SkillRegistry.register("read_local_file", read_local_file_execute, {"name": "本地文件读取"})
SkillRegistry.register("summarize", summarize_execute, {"name": "摘要生成"})
SkillRegistry.register("compare_docs", compare_docs_execute, {"name": "文档对比"})
SkillRegistry.register("content_generation", content_generation_execute, {"name": "大模型内容生成"})
SkillRegistry.register("skill_creator", skill_creator_execute, {"name": "技能创建器"})
SkillRegistry.register("text_law_assist", text_law_assist_execute, {"name": "法律合同检索辅助"})
SkillRegistry.register("text_paper_assist", text_paper_assist_execute, {"name": "论文学术检索辅助"})
SkillRegistry.register("text_format_assist", text_format_assist_execute, {"name": "格式与引用辅助"})
SkillRegistry.register("text_novel_assist", text_novel_assist_execute, {"name": "小说创意检索辅助"})
SkillRegistry.register("novel_continuer", novel_continuer_execute, {"name": "小说续写"})
SkillRegistry.register("paper_section_generator", paper_section_generator_execute, {"name": "论文分节生成"})
SkillRegistry.register("contract_filler", contract_filler_execute, {"name": "合同补全"})
SkillRegistry.register("scar_retrieve", scar_retrieve_execute, {"name": "SCAR结构召回"})
SkillRegistry.register("scar_generate", scar_generate_execute, {"name": "SCAR证据生成"})
from .custom_skill import execute as custom_skill_execute
SkillRegistry.register("custom_skill", custom_skill_execute, {"name": "自定义技能"})
