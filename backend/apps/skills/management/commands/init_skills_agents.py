"""
初始化 Skill 与 Agent 预置数据（Text Master AI：场景化 Skill + evolution_domain）

用法：python manage.py init_skills_agents
"""
from django.core.management.base import BaseCommand
from apps.skills.models import Skill
from apps.agents.models import Agent
from apps.skills.prompt_builder import AGENT_ROLE_FALLBACK


def _m(evolution_domain: str, use_case: str, primary_env: str = "rag"):
    return {
        "requires": {},
        "primary_env": primary_env,
        "evolution_domain": evolution_domain,
        "use_case": use_case,
    }


class Command(BaseCommand):
    help = "初始化 Skill 与 Agent 预置数据"

    def handle(self, *args, **options):
        skills_data = [
            {
                "id": "rag_answer",
                "name": "知识库检索",
                "description": "使用混合检索在知识库中查找相关文档（通用增强）",
                "input_schema": {"query": "string", "knowledge_base_id": "string"},
                "output_schema": {"documents": "list"},
                "permission_level": "rag",
                "metadata": _m(
                    "qa_enhancement",
                    "通用私有知识库问答与检索增强",
                ),
            },
            {
                "id": "cite_snippets",
                "name": "引用生成",
                "description": "从文档中提取可引用片段",
                "input_schema": {"documents": "list", "query": "string"},
                "output_schema": {"snippets": "list"},
                "permission_level": "rag",
                "metadata": _m("citation", "引用片段与参考文献格式辅助"),
            },
            {
                "id": "read_local_file",
                "name": "本地文件读取",
                "description": "读取白名单目录内的本地文件内容",
                "input_schema": {"file_path": "string"},
                "output_schema": {"content": "string", "path": "string"},
                "permission_level": "file_read",
                "metadata": _m("format_extraction", "本地文本文件读取与结构化", "file_read"),
            },
            {
                "id": "summarize",
                "name": "摘要生成",
                "description": "对给定文本生成简洁摘要",
                "input_schema": {"text": "string"},
                "output_schema": {"summary": "string"},
                "permission_level": "rag",
                "metadata": _m("summary", "长文摘要与要点提炼"),
            },
            {
                "id": "compare_docs",
                "name": "文档对比",
                "description": "对比多份文档的异同",
                "input_schema": {"documents": "list", "query": "string"},
                "output_schema": {"comparison": "string"},
                "permission_level": "rag",
                "metadata": _m("qa_enhancement", "多文档差异与一致性对比"),
            },
            {
                "id": "content_generation",
                "name": "大模型内容生成",
                "description": "关键词触发：总结、摘要、问答集等内容生成",
                "input_schema": {"question": "string", "knowledge_base_id": "string"},
                "output_schema": {"answer": "string", "content_types": "list"},
                "permission_level": "rag",
                "metadata": _m("qa_enhancement", "基于知识库的结构化内容生成"),
            },
            {
                "id": "skill_creator",
                "name": "技能创建器",
                "description": "根据需求创建 Skill 模板（管理员或策略允许时）",
                "input_schema": {"question": "string", "skill_name": "string", "skill_id": "string"},
                "output_schema": {"created": "bool", "skill_id": "string", "file_path": "string"},
                "permission_level": "system",
                "metadata": _m("qa_enhancement", "扩展内置能力（受定向策略约束）", "system"),
            },
            {
                "id": "text_law_assist",
                "name": "法律合同检索辅助",
                "description": "面向合同/案例库的知识库检索（纯文字；自进化 domain=law）",
                "input_schema": {"query": "string", "knowledge_base_id": "string"},
                "output_schema": {"documents": "list"},
                "permission_level": "rag",
                "metadata": _m("law", "律师/合同：条款、义务与风险相关检索"),
            },
            {
                "id": "text_paper_assist",
                "name": "论文学术检索辅助",
                "description": "面向学术资料库的知识库检索（纯文字；domain=paper_writing）",
                "input_schema": {"query": "string", "knowledge_base_id": "string"},
                "output_schema": {"documents": "list"},
                "permission_level": "rag",
                "metadata": _m("paper_writing", "论文：结构、文献与术语相关检索"),
            },
            {
                "id": "text_format_assist",
                "name": "格式与引用辅助",
                "description": "面向格式整理、表格与参考文献场景的知识库检索（domain=format_extraction）",
                "input_schema": {"query": "string", "knowledge_base_id": "string"},
                "output_schema": {"documents": "list"},
                "permission_level": "rag",
                "metadata": _m("format_extraction", "表格、标题层级与参考文献结构"),
            },
            {
                "id": "text_novel_assist",
                "name": "小说创意检索辅助",
                "description": "面向小说/创意文本库的一致性检索（domain=novel_writing）",
                "input_schema": {"query": "string", "knowledge_base_id": "string"},
                "output_schema": {"documents": "list"},
                "permission_level": "rag",
                "metadata": _m("novel_writing", "人物、设定与时间线一致性检索"),
            },
            {
                "id": "novel_continuer",
                "name": "小说续写",
                "description": "根据上下文延续章节风格与人物设定（PRO）",
                "input_schema": {"question": "string", "knowledge_base_id": "string"},
                "output_schema": {"answer": "string"},
                "permission_level": "rag",
                "metadata": _m("novel_writing", "章节续写与情节衔接"),
            },
            {
                "id": "paper_section_generator",
                "name": "论文分节生成",
                "description": "生成论文小节草稿与结构化段落（PRO）",
                "input_schema": {"question": "string", "knowledge_base_id": "string"},
                "output_schema": {"answer": "string"},
                "permission_level": "rag",
                "metadata": _m("paper_writing", "论文分节生成与措辞规范"),
            },
            {
                "id": "contract_filler",
                "name": "合同补全",
                "description": "生成合同条款补全文本建议（PRO）",
                "input_schema": {"question": "string", "knowledge_base_id": "string"},
                "output_schema": {"answer": "string"},
                "permission_level": "rag",
                "metadata": _m("law", "合同条款补全与风险提示"),
            },
            {
                "id": "english_profile_from_tags",
                "name": "英语档案：标签归一化",
                "description": "将 level_tags / 目标整理为 learner_constraints（MVP 规则）",
                "input_schema": {"level_tags": "array", "exam_goal": "string", "weekly_minutes": "int"},
                "output_schema": {"learner_constraints": "object", "summary_for_user": "string"},
                "permission_level": "rag",
                "metadata": _m("education", "英语学习定制：档案"),
            },
            {
                "id": "english_assessment_build",
                "name": "英语测评组卷",
                "description": "按级别与维度从内置题库抽题",
                "input_schema": {"learner_constraints": "object", "question_count": "int"},
                "output_schema": {"items": "array", "items_scoring": "array"},
                "permission_level": "rag",
                "metadata": _m("education", "英语学习定制：组卷"),
            },
            {
                "id": "english_assessment_score",
                "name": "英语测评评分",
                "description": "客观题判分与维度薄弱项",
                "input_schema": {"items": "array", "responses": "array"},
                "output_schema": {"scores": "object", "gap_summary": "string", "weak_dimensions": "array"},
                "permission_level": "rag",
                "metadata": _m("education", "英语学习定制：评分"),
            },
            {
                "id": "english_roadmap_draft",
                "name": "英语学习路线草案",
                "description": "综合测评与加强维度生成 Markdown 路线",
                "input_schema": {"scores": "object", "focus_dimensions": "array"},
                "output_schema": {"roadmap_markdown": "string", "outline_json": "object"},
                "permission_level": "rag",
                "metadata": _m("education", "英语学习定制：路线草案"),
            },
            {
                "id": "english_roadmap_finalize",
                "name": "英语学习路线定稿入库",
                "description": "将定稿 Markdown 写入用户知识库并尝试向量化",
                "input_schema": {"roadmap_markdown": "string", "kb_id": "uuid"},
                "output_schema": {"document_id": "uuid", "version": "int"},
                "permission_level": "rag",
                "metadata": _m("education", "英语学习定制：路线入库"),
            },
            {
                "id": "english_active_recall_pack",
                "name": "英语主动回忆包",
                "description": "基于弱项与路线单元的规则型微练习条目（无 LLM）",
                "input_schema": {"weak_dimensions": "array", "learner_constraints": "object"},
                "output_schema": {"pack_items": "array", "schema_version": "int"},
                "permission_level": "rag",
                "metadata": _m("education", "英语学习定制：主动回忆"),
            },
            {
                "id": "scar_retrieve",
                "name": "SCAR结构召回",
                "description": "结构编译 Agentic RAG：StructureUnit 召回 → EvidencePack",
                "input_schema": {
                    "query": "string",
                    "knowledge_base_id": "string",
                    "domain": "string",
                },
                "output_schema": {"evidence_pack": "object"},
                "permission_level": "rag",
                "lifecycle_status": "active",
                "is_active": True,
                "evolution_enabled": True,
                "metadata": {
                    **_m("scar_retrieval", "SCAR 召回策略受控进化（消歧/别名/重试，不含工程数值）"),
                    "scar_strategy_patch": {
                        "patch_type": "recall_strategy",
                        "alias_overrides": {},
                        "disambiguation_priority": [],
                        "retry_rules": [],
                        "prefer_field_order": [],
                        "notes": "seed empty patch",
                    },
                },
            },
            {
                "id": "scar_generate",
                "name": "SCAR证据生成",
                "description": "基于 EvidencePack 生成带 path 引用的答案；证据不足则拒答",
                "input_schema": {"query": "string", "evidence_pack": "object"},
                "output_schema": {"answer": "string", "citations": "list", "abstained": "bool"},
                "permission_level": "rag",
                "lifecycle_status": "active",
                "is_active": True,
                "metadata": _m("scar_retrieval", "SCAR 证据生成（不写 StructureUnit 数值）"),
            },
        ]
        for s in skills_data:
            Skill.objects.update_or_create(id=s["id"], defaults=s)
            self.stdout.write(f"Skill: {s['id']}")

        agents_data = [
            {
                "id": "qa",
                "name": "知识问答助手",
                "description": "通用私有知识库问答；绑定通用检索与引用",
                "skills": ["content_generation", "rag_answer", "cite_snippets"],
                "default_model": "deepseek-chat",
            },
            {
                "id": "doc",
                "name": "文档整理助手",
                "description": "阅读、摘要、对比与本地文件；适合长文档工作流",
                "skills": [
                    "content_generation",
                    "rag_answer",
                    "cite_snippets",
                    "read_local_file",
                    "summarize",
                    "compare_docs",
                ],
                "default_model": "deepseek-chat",
            },
            {
                "id": "builder",
                "name": "技能构建助手",
                "description": "专用于根据需求创建新 Skill（管理员场景）",
                "skills": ["skill_creator"],
                "default_model": "deepseek-chat",
            },
            {
                "id": "law_kb",
                "name": "法律合同助手",
                "description": "合同与案例库场景；检索绑定 law 领域自进化",
                "skills": ["content_generation", "text_law_assist", "cite_snippets"],
                "default_model": "deepseek-chat",
            },
            {
                "id": "paper_kb",
                "name": "论文资料助手",
                "description": "学术与写作资料库场景；绑定 paper_writing 领域",
                "skills": ["content_generation", "text_paper_assist", "cite_snippets"],
                "default_model": "deepseek-chat",
            },
            {
                "id": "format_kb",
                "name": "格式整理助手",
                "description": "格式提取、表格与引用结构；绑定 format_extraction",
                "skills": ["content_generation", "text_format_assist", "cite_snippets"],
                "default_model": "deepseek-chat",
            },
            {
                "id": "novel_kb",
                "name": "小说创作助手",
                "description": "创意文本与章节一致性；绑定 novel_writing",
                "skills": ["content_generation", "text_novel_assist", "cite_snippets"],
                "default_model": "deepseek-chat",
            },
            {
                "id": "studio_pro",
                "name": "PRO 写作工作室助手",
                "description": "PRO 专属：合同/论文/小说增强生成",
                "skills": [
                    "content_generation",
                    "novel_continuer",
                    "paper_section_generator",
                    "contract_filler",
                    "cite_snippets",
                ],
                "default_model": "deepseek-chat",
            },
            {
                "id": "english_vocab",
                "name": "英语词汇专项",
                "description": "词汇释义、搭配与记忆操练；绑定个人知识库与路线",
                "skills": ["content_generation", "rag_answer", "cite_snippets"],
                "default_model": "deepseek-chat",
            },
            {
                "id": "english_grammar",
                "name": "英语语法专项",
                "description": "语法讲解、纠错与对比练习；绑定个人知识库与路线",
                "skills": ["content_generation", "rag_answer", "cite_snippets"],
                "default_model": "deepseek-chat",
            },
            {
                "id": "english_listen",
                "name": "英语听力专项",
                "description": "听力训练步骤与复述任务；绑定个人知识库与路线",
                "skills": ["content_generation", "rag_answer", "cite_snippets"],
                "default_model": "deepseek-chat",
            },
            {
                "id": "english_orchestrator",
                "name": "英语学习主编排",
                "description": "测评与路线后的陪练：检索个人路线文档并结构化练习建议",
                "skills": [
                    "content_generation",
                    "rag_answer",
                    "cite_snippets",
                    "english_roadmap_draft",
                ],
                "default_model": "deepseek-chat",
            },
        ]
        for a in agents_data:
            # 与 prompt_builder.AGENT_ROLE_FALLBACK 对齐，写入 DB 便于后台改字而无需改代码
            a["system_prompt"] = AGENT_ROLE_FALLBACK.get(a["id"], AGENT_ROLE_FALLBACK["qa"])
            Agent.objects.update_or_create(id=a["id"], defaults=a)
            self.stdout.write(f"Agent: {a['id']}")

        self.stdout.write(self.style.SUCCESS("初始化完成"))
