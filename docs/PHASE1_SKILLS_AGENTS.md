# Phase 1 预置 Skill / Agent 对照（P1-T13）

> **单一事实来源（代码）**：`backend/apps/skills/management/commands/init_skills_agents.py`  
> 部署后执行 `python manage.py init_skills_agents` 将以下数据写入数据库。

## 场景化 Skill 与 `evolution_domain`（P1-T10～T12）

| Skill `id` | 产品名 | `metadata.evolution_domain` | 适用场景摘要 |
|------------|--------|----------------------------|--------------|
| `text_law_assist` | 法律合同检索辅助 | `law` | 律师/合同：条款、义务与风险相关检索 |
| `text_paper_assist` | 论文学术检索辅助 | `paper_writing` | 论文：结构、文献与术语相关检索 |
| `text_format_assist` | 格式与引用辅助 | `format_extraction` | 表格、标题层级与参考文献结构 |
| `text_novel_assist` | 小说创意检索辅助 | `novel_writing` | 人物、设定与时间线一致性检索 |
| `rag_answer` | 知识库检索 | `qa_enhancement` | 通用私有知识库问答与检索增强 |

上述领域须落在 `EVOLUTION_ALLOWED_DOMAINS`（见 `settings.py` 默认值或环境变量）内。

## 默认与场景 Agent 绑定（`Agent.skills`）

| Agent `id` | 名称 | 绑定 Skill 子集 |
|--------------|------|-------------------|
| `qa` | 知识问答助手 | `content_generation`, `rag_answer`, `cite_snippets` |
| `doc` | 文档整理助手 | `content_generation`, `rag_answer`, `cite_snippets`, `read_local_file`, `summarize`, `compare_docs` |
| `law_kb` | 法律合同助手 | `content_generation`, `text_law_assist`, `cite_snippets` |
| `paper_kb` | 论文资料助手 | `content_generation`, `text_paper_assist`, `cite_snippets` |
| `format_kb` | 格式整理助手 | `content_generation`, `text_format_assist`, `cite_snippets` |
| `novel_kb` | 小说创作助手 | `content_generation`, `text_novel_assist`, `cite_snippets` |
| `builder` | 技能构建助手 | `skill_creator`（前端列表默认隐藏） |

---

*与《自进化 Skill 与 Agent 的定向控制方案》白名单交叉校验。*
