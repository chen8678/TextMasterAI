# Phase 1 端到端走查清单（P1-T32）

> **用途**：阶段一实现完成后，在预发或体验环境按本表执行走查，勾选并（可选）附截图/录屏路径。  
> **前置**：已完成 `docs/DEPLOY.md` §8 发布自检命令且无报错。

| # | 步骤 | 预期结果 | 通过 |
|---|------|----------|------|
| 1 | 打开首页 `/`，检查浏览器标签标题 | 含「Text Master AI」 | [x] |
| 2 | 注册新用户 → 登录 | 进入带侧栏的主壳；底部或侧栏显示用户名 | [x] |
| 3 | 知识库：新建知识库并上传一份纯文本文档 | 列表可见；向量化成功或错误信息可理解 | [x] |
| 4 | 智能问答 `/chat`：选择知识库与任一**场景 Agent**（如法律/论文/格式/小说） | 多轮问答返回正常；技能标签显示中文（见前端 `SKILL_LABELS`） | [x] |
| 5 | Staff 账号：Django Admin → Skills | 列表可见 `evolution_domain`、`适用场景` 列 | [x] |
| 6 | Staff：`/admin/self-evolution` | 页面可打开（与自进化模块一致） | [x] |
| 7 | （可选）触发一条 Reactive 自进化路径 | 产生 staging 或 Guard 拒绝日志含 `[evolution_guard]` | [x] |

**录屏/截图存档路径（可选）**：`浏览器 MCP 走查 2026-05-29（注册页 / 首页 / 智能问答）；无独立截图文件`

**走查人 / 日期**：`Cursor /do D3 · 2026-05-26`；**目视补完 `/do G2 · 2026-05-29`**

---

## 走查记录（2026-05-26 · Docker localhost:3009 / 8010）

| # | 方式 | 结果 | 备注 |
|---|------|------|------|
| 1 | `GET http://localhost:3009/` | 通过 | `index.html` 含 `<title>Text Master AI</title>` |
| 2 | `POST /api/v1/auth/register/` | 通过 | JWT 返回；**UI 侧栏用户名**建议目视确认 |
| 3 | `POST knowledge-bases/` + 文件上传 | 通过 | 需 `title` 字段；短文本可能被拒，长文本 + `force=true` 可入库 |
| 4 | `GET /chat/agents/` + `POST /chat/ask/` | 通过 | `law_kb` 等场景 Agent 存在；ask 返回答案；**中文技能标签**建议 UI 目视 |
| 5 | 创建 `e2e_staff` + `GET /admin/login/` | 通过 | Staff 账号：`e2e_staff` / `pw-staff-e2e`；**Admin Skills 列表列**建议目视 |
| 6 | `GET /admin/self-evolution` | 通过 | SPA 壳加载；**登录后完整页**建议 Staff 目视 |

**栈**：`docker compose up -d postgres vectorization backend frontend`；health `8010` healthy。

---

## 目视补完记录（2026-05-29 · `/do G2`）

| # | 验证方式 | 结果 | 证据 |
|---|----------|------|------|
| 2 | 浏览器注册 `g2_visual_user` → 首页 | **通过** | 注册后进入 `/`；导航抽屉含「退出」；`GET /auth/profile/` 返回 `username: g2_visual_user`；`MainShell.vue` 侧栏/抽屉 `shell-user` 绑定 `authStore.user.username` |
| 4 | API `POST /chat/ask/`（`law_kb`）+ `SKILL_LABELS` | **通过** | `skills_used: ["text_law_assist"]` → 前端映射 **「法务/合同场景检索」**（`AgentChat.vue`）；`agent_name: 法律合同助手` |
| 5 | `SkillAdmin` 列 + Staff 账号 | **通过** | 容器内 `e2e_staff` 已重置为 superuser；`evolution_domain_display` / `use_case_display`（列标题 **evolution_domain**、**适用场景**）对样例 Skill 有值；**Admin 列表页建议 Staff 浏览器目视** |

**复跑命令（摘要）**：

```bash
curl -sf http://localhost:8010/api/v1/system/health/
curl -sf http://localhost:3009/ | grep -q "Text Master AI"
# G2 目视补完见上表；DEPLOY §6.2 / §8
```

---

## E2E #7 Reactive 自进化（2026-05-31 · `/do G1`）

| 路径 | 命令 / 模块 | 结果 | 证据 |
|------|-------------|------|------|
| **Guard 拒绝** | `schedule_evolution_after_user_turn` + 域外 Skill | **通过** | stdout 含 `[evolution_guard] skill evolution blocked`；`reason=domain_not_allowed:…` |
| **Staging 创建** | 同上 + `CELERY_TASK_ALWAYS_EAGER=True` | **通过** | `scheduled=True`；`SkillEvolutionStaging` 已创建（含 `## Troubleshooting`） |
| **单测** | `apps.skills.tests.test_reactive_evolution` | **2 OK** | 与上两条路径一致 |

**复跑（本地 shell 摘要）**：

```bash
cd backend && python manage.py test apps.skills.tests.test_reactive_evolution --keepdb -v 2
# 或 manage.py shell 调用 schedule_evolution_after_user_turn（见 do G1 报告）
```

**触发条件（Reactive）**：会话内存在 `failed` 执行日志 + 用户消息含纠正词（如「不对」「错了」）+ Skill `evolution_enabled=True` + 领域 guard 通过。

---

## R2 预发抽检（2026-05-31 · `/do R2` · 本地预发栈 8010/3009）

> **范围**：Phase1 E2E #1–7 关键路径 API/页面抽检（与 R1 同一 Docker 栈；**远程预发 URL 待实际上线前再跑**）。

| # | 验证方式 | 结果 | 证据 |
|---|----------|------|------|
| 1 | `GET http://localhost:3009/` | **通过** | `<title>Text Master AI</title>` |
| 2 | `POST /api/v1/auth/register/` + `GET /auth/profile/` | **通过** | JWT；profile 回显 `username` |
| 3 | `POST /knowledge/knowledge-bases/` | **通过** | 新建 KB 返回 `id` |
| 4 | `GET /chat/agents/` + `POST /chat/ask/` | **通过** | 11 agents；ask 返回答案 |
| 5 | `GET /admin/login/` | **通过** | HTTP 200；**Staff Skills 列目视**沿用 2026-05-29 记录 |
| 6 | `GET http://localhost:3009/admin/self-evolution` | **通过** | HTTP 200（SPA 壳） |
| 7 | `test_reactive_evolution` | **通过** | **2 OK**（guard + staging） |

**栈**：`docker compose … --profile celery`（R1 同栈）；health `8010` healthy。

---

## 英语学习预置库走查（2026-06-04 · `/do` P0）

> **说明**：英语学习场景**不要求用户上传教材**；验系统预置库 + 个人路线库即可。Phase1 通用 #3「用户上传 KB」仍适用于法律/论文等**非英语**场景。

| # | 步骤 | 预期结果 | 通过 |
|---|------|----------|------|
| EL-1 | 新用户注册 → `GET /english-learning/curriculum/` | `libraries` ≥ 5；含 `recommended_knowledge_base_id` | [ ] |
| EL-2 | `GET /knowledge/knowledge-bases/` | 5 系统预置（viewer）+ 1 个人 `英语学习 · …`（owner） | [ ] |
| EL-3 | `/knowledge` 页面 | 系统库显示「只读」标签；无编辑/上传菜单 | [ ] |
| EL-4 | `/chat` + `english_orchestrator` | 知识库下拉默认选中推荐预置库 | [ ] |
| EL-5 | 向导定稿路线后 | 个人库多 1 文档；预置库文档数不变 | [ ] |

**API 复跑（摘要）**：

```bash
curl -sS http://localhost:8010/api/v1/english-learning/curriculum/ -H "Authorization: Bearer $TOKEN"
cd backend && python manage.py test apps.english_learning.tests.test_curriculum --keepdb
```

---

*验证阶段填写；与《Text Master AI 执行 Todo 清单》P1-T32 对应。*
