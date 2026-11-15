<template>
  <div class="page agents-page">
    <header class="page-header apple-card">
      <div class="header-left">
        <div class="logo-pill">
          <AppleIcon name="cube" :size="20" />
        </div>
        <div>
          <h1>使用场景</h1>
          <p>我们预先为你配置了不同风格的智能体，分别擅长知识问答、文档整理和自动生成内容。</p>
        </div>
      </div>
    </header>

    <main class="page-main apple-card">
      <el-row :gutter="16">
        <el-col :span="10">
          <h2 class="sub-title">内置智能体</h2>
          <el-table
            :data="agents"
            border
            size="small"
            highlight-current-row
            @row-click="selectAgent"
            class="agents-table"
          >
            <el-table-column prop="name" label="名称" min-width="160" />
            <el-table-column prop="role" label="角色" min-width="140" />
            <el-table-column prop="skills" label="技能数" width="80" align="center">
              <template #default="{ row }">
                {{ row.skills.length }}
              </template>
            </el-table-column>
            <el-table-column prop="workflow" label="默认工作流" min-width="140">
              <template #default="{ row }">
                <span v-if="row.workflow">{{ row.workflow }}</span>
                <span v-else class="muted">未绑定</span>
              </template>
            </el-table-column>
          </el-table>
        </el-col>

        <el-col :span="14">
          <section v-if="current" class="agent-detail">
            <h2 class="sub-title">Agent 配置：{{ current.name }}</h2>
            <p class="muted">{{ current.description }}</p>

            <el-descriptions :column="1" size="small" border>
              <el-descriptions-item label="内部 ID">{{ current.id }}</el-descriptions-item>
              <el-descriptions-item label="角色设定">{{ current.role }}</el-descriptions-item>
              <el-descriptions-item label="默认模型">
                {{ current.model }}
              </el-descriptions-item>
              <el-descriptions-item label="默认工作流">
                {{ current.workflow || '未绑定' }}
              </el-descriptions-item>
            </el-descriptions>

            <h3 class="sub-title">绑定 Skills</h3>
            <div class="skills-pills">
              <el-tag
                v-for="s in current.skills"
                :key="s"
                size="small"
                type="success"
                class="pill"
              >
                {{ s }}
              </el-tag>
              <span v-if="!current.skills.length" class="muted">
                暂未绑定 Skill，将来可在这里做多选绑定，写回后端 Agent 配置。
              </span>
            </div>

            <h3 class="sub-title">安全策略概览</h3>
            <ul class="policy-list">
              <li v-for="p in current.policies" :key="p.key">
                <strong>{{ p.title }}：</strong>
                <span>{{ p.description }}</span>
              </li>
            </ul>
          </section>
        </el-col>
      </el-row>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AppleIcon from '@/components/AppleIcon.vue'

type Policy = {
  key: string
  title: string
  description: string
}

type Agent = {
  id: string
  name: string
  role: string
  description: string
  model: string
  skills: string[]
  workflow?: string
  policies: Policy[]
}

const agents = ref<Agent[]>([
  {
    id: 'qa',
    name: '知识问答 Agent',
    role: '面向知识库检索与引用的通用问答智能体。',
    description: '负责在指定知识库上执行 RAG 问答，保证引用清晰与答案可追溯。',
    model: 'deepseek-chat',
    skills: ['rag_answer', 'cite_snippets'],
    workflow: 'qa-default',
    policies: [
      { key: 'sandbox', title: '执行环境', description: '仅允许使用 RAG 类技能，不允许本地系统调用。' },
      { key: 'rate', title: '限流策略', description: '每分钟最多 10 次问答，避免滥用。' }
    ]
  },
  {
    id: 'doc',
    name: '文档助手 Agent',
    role: '面向本地文件与知识库文档的整理助手。',
    description: '聚焦文档读取、总结与多文档对比分析，可选绑定本地执行 Skill。',
    model: 'deepseek-chat',
    skills: ['read_local_file', 'summarize', 'compare_docs'],
    workflow: 'doc-review',
    policies: [
      { key: 'file_read', title: '文件访问', description: '只读访问白名单目录下文件，禁止写入与删除。' },
      { key: 'approval', title: '审批策略', description: '访问敏感目录前需要显式授权。' }
    ]
  }
])

const current = ref<Agent | null>(agents.value[0] || null)

const selectAgent = (row: Agent) => {
  current.value = row
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: var(--bg-100);
  padding: 24px 40px 40px;
  box-sizing: border-box;
}

.apple-card {
  background: var(--bg-200);
  border-radius: var(--apple-radius-lg);
  border: 1px solid var(--apple-border);
  padding: var(--apple-space-lg);
}

.page-header {
  margin: 0 auto var(--apple-space-lg);
  max-width: 960px;
}

.header-left {
  display: flex;
  gap: 12px;
  align-items: center;
}

.logo-pill {
  width: 40px;
  height: 40px;
  border-radius: var(--apple-radius-md);
  background: rgba(255, 90, 95, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-100);
}

.header-left h1 {
  margin: 0;
  font-size: var(--apple-font-size-h2);
}

.header-left p {
  margin: 4px 0 0;
  color: var(--apple-text-secondary);
  font-size: var(--apple-font-size-caption);
}

.page-main {
  padding: 0;
  max-width: 960px;
  margin: 0 auto;
}

.sub-title {
  margin: 0 0 8px;
  font-size: var(--apple-font-size-h3);
}

.muted {
  font-size: var(--apple-font-size-caption);
  color: var(--apple-text-secondary);
}

.agents-table {
  margin-top: 8px;
}

.agent-detail {
  padding-left: 8px;
}

.skills-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}

.pill {
  margin-right: 2px;
}

.policy-list {
  list-style: none;
  padding: 0;
  margin: 4px 0 0;
}

.policy-list li {
  font-size: var(--apple-font-size-caption);
  margin-bottom: 4px;
}
</style>

