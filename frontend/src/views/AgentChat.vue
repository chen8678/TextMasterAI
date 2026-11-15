<template>
  <div class="agent-chat-page">
    <PageScaffold class="chat-scaffold">
      <template #header>
        <PageHeader class="chat-top">
          <div class="chat-brand">
            <BrandMark :size="56" circular :padded="false" />
            <div class="chat-title">
              <h2>Text Master AI · 智能问答</h2>
              <p>基于私有知识库的纯文字检索与生成（不含图像/视频等多模态）。</p>
            </div>
          </div>
          <template #actions>
            <div class="chat-controls">
              <el-select
                v-model="selectedKnowledgeBaseId"
                size="small"
                class="control-select"
                placeholder="选择知识库"
                filterable
              >
                <el-option
                  v-for="kb in knowledgeBases"
                  :key="kb.id"
                  :label="kbOptionLabel(kb)"
                  :value="kb.id"
                />
              </el-select>
              <el-select
                v-model="currentAgentId"
                size="small"
                class="control-select agent-select"
                filterable
                placeholder="选择智能体"
              >
                <el-option
                  v-for="agent in agents"
                  :key="agent.id"
                  :label="agent.name"
                  :value="agent.id"
                >
                  <div class="agent-option">
                    <span class="agent-option-name">{{ agent.name }}</span>
                    <span v-if="agent.description" class="agent-option-desc">{{ agent.description }}</span>
                  </div>
                </el-option>
              </el-select>
              <el-select
                v-if="currentAgentId === 'english_orchestrator'"
                v-model="englishDelegate"
                size="small"
                class="control-select"
                placeholder="专项"
                style="min-width: 120px"
              >
                <el-option label="主编排默认" value="default" />
                <el-option label="词汇" value="vocab" />
                <el-option label="语法" value="grammar" />
                <el-option label="听力" value="listen" />
              </el-select>
              <el-tooltip content="演示用：强制走 SCAR 结构召回（需库内已编译文档）" placement="bottom">
                <el-switch
                  v-model="scarMode"
                  size="small"
                  inline-prompt
                  active-text="SCAR"
                  inactive-text="Hybrid"
                  class="scar-mode-switch"
                />
              </el-tooltip>
              <el-button size="small" type="primary" @click="showSessionList = true">
                <el-icon><ChatDotRound /></el-icon>
                会话管理
              </el-button>
              <el-button size="small" plain @click="createNewSession">
                <el-icon><Plus /></el-icon>
                新建对话
              </el-button>
              <el-button size="small" type="primary" plain @click="goToKnowledge">
                知识库管理
              </el-button>
              <el-tag v-if="!ENABLE_PRO_STUDIO || !authStore.user?.is_pro" size="small" type="info" effect="plain">
                当前为免费版
              </el-tag>
              <el-button
                v-else-if="ENABLE_PRO_STUDIO"
                size="small"
                type="success"
                plain
                @click="router.push('/writing/studio')"
              >
                文字工作室
              </el-button>
              <el-button size="small" plain class="chat-back-btn" @click="goBack">
                <el-icon><ArrowLeft /></el-icon>
                返回
              </el-button>
            </div>
          </template>
        </PageHeader>
      </template>
      <el-alert
        v-if="englishTodaySummary || englishGraphLine"
        type="info"
        :closable="false"
        class="english-today-bar"
      >
        <div class="english-today-inner">
          <span v-if="englishTodaySummary" class="english-today-text">{{ englishTodaySummary }}</span>
          <span v-if="englishGraphLine" class="english-graph-hint">{{ englishGraphLine }}</span>
          <el-button
            v-if="englishRecallPrompt"
            type="primary"
            link
            @click="useChip(englishRecallPrompt)"
          >
            {{ englishRecallLabel }}
          </el-button>
          <el-button type="primary" link @click="router.push('/english-learning')">学习向导</el-button>
        </div>
      </el-alert>
      <main class="chat-main">
        <section class="chat-messages" ref="messagesRef">
          <div v-if="messages.length === 0" class="chat-empty">
            <div class="zero-hero">
              <p class="zero-eyebrow">Text Master AI</p>
              <h1 class="zero-title">私有知识库 · 文字问答</h1>
              <p class="zero-subtitle">
                用自然语言提问，在纯文字场景下检索文档并生成答案或草稿；能力边界见「关于产品」。
              </p>
              <div class="zero-chips">
                <button
                  v-for="chip in chips"
                  :key="chip.text"
                  class="chip"
                  type="button"
                  @click="useChip(chip.example)"
                >
                  {{ chip.text }}
                </button>
              </div>
            </div>
          </div>
          <div
            v-for="msg in messages"
            :key="msg.id"
            class="chat-message"
            :class="msg.role === 'user' ? 'from-user' : 'from-agent'"
          >
            <div class="bubble">
              <div class="bubble-text markdown-body" v-html="renderMarkdown(msg.content)"></div>
              <div
                v-if="msg.meta?.citations?.length"
                class="scar-citations"
              >
                <div class="scar-citations-title">结构引用</div>
                <div
                  v-for="(c, idx) in msg.meta.citations"
                  :key="`${msg.id}-cite-${idx}`"
                  class="scar-citation-row"
                >
                  <span class="scar-cite-file">{{ c.file || c.file_id || '文档' }}</span>
                  <span class="scar-cite-sep">·</span>
                  <code class="scar-cite-path">{{ c.path }}</code>
                </div>
              </div>
              <div v-if="msg.meta" class="bubble-meta">
                <span v-if="msg.meta.agentName" class="agent-tag">{{ msg.meta.agentName }}</span>
                  <span v-if="msg.meta.evolutionPath" class="evo-path-tag">
                    {{ msg.meta.evolutionPath === 'pro_sandbox' ? 'PRO 沙盒进化' : '标准自进化' }}
                  </span>
                <span v-if="msg.meta.answerSource === 'scar'" class="scar-source-tag">SCAR</span>
                <template v-if="msg.meta.skills?.length">
                  <span class="meta-label">调用能力：</span>
                  <span
                    v-for="s in msg.meta.skills"
                    :key="s"
                    class="skill-tag"
                  >
                    {{ SKILL_LABELS[s] || s }}
                  </span>
                </template>
                <div v-if="msg.role === 'agent' && analyticsEnabled" class="feedback-actions">
                  <el-button
                    size="small"
                    text
                    :type="msg.meta.feedback === 'like' ? 'success' : 'default'"
                    @click="submitFeedbackEvent(msg, 'like')"
                  >
                    👍 有帮助
                  </el-button>
                  <el-button
                    size="small"
                    text
                    :type="msg.meta.feedback === 'dislike' ? 'danger' : 'default'"
                    @click="submitFeedbackEvent(msg, 'dislike')"
                  >
                    👎 需改进
                  </el-button>
                </div>
              </div>
            </div>
          </div>
          <!-- 加载状态在消息列表末尾，紧跟最新一条用户消息之后 -->
          <div v-if="isThinking" class="chat-message from-agent">
            <div class="bubble thinking-bubble">
              <span class="thinking-spinner"></span>
              <p class="thinking-text">智能体正在调用：{{ thinkingSkillsText }}</p>
            </div>
          </div>
        </section>
      </main>

    <!-- 会话列表弹窗 -->
    <el-dialog
      v-model="showSessionList"
      title="会话管理"
      width="560px"
      class="session-dialog"
      @open="loadSessions"
    >
      <div class="session-list">
        <div
          v-for="session in sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: currentSessionId === session.id }"
          @click="loadSession(session.id)"
        >
          <div class="session-avatar">
            <el-icon><ChatDotRound /></el-icon>
          </div>
          <div class="session-info">
            <div class="session-title">{{ session.title || '未命名对话' }}</div>
            <div class="session-meta">
              <span class="session-time">{{ formatTime(session.last_activity || session.created_at) }}</span>
              <span class="session-count">{{ session.message_count || 0 }} 条消息</span>
            </div>
            <div v-if="session.last_message" class="last-message">
              {{ typeof session.last_message === 'object' ? session.last_message?.question : session.last_message }}
            </div>
          </div>
          <div class="session-actions">
            <el-button type="danger" size="small" circle @click.stop="deleteSession(session.id)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </div>
        </div>
        <div v-if="sessions.length === 0" class="empty-sessions">
          <el-icon class="empty-icon"><ChatDotRound /></el-icon>
          <h3>暂无会话记录</h3>
          <p>开始新的对话，创建您的第一个会话</p>
        </div>
      </div>
      <template #footer>
        <el-button @click="showSessionList = false">关闭</el-button>
        <el-button type="primary" @click="createNewSession">
          <el-icon><Plus /></el-icon>
          新建对话
        </el-button>
      </template>
    </el-dialog>

    <template #feedback>
      <footer class="chat-footer">
      <div class="input-shell">
        <!-- 自定义输入框架：adapters/chatComposer.ts → setActiveCustomComposer + registerCustomComposer -->
        <component
          :is="customComposer"
          v-if="customComposer"
          v-model="inputText"
          :disabled="generationRunning"
          @send="handleSend"
        />
        <el-input
          v-else
          v-model="inputText"
          type="textarea"
          :autosize="{ minRows: composerConfig.minRows, maxRows: composerConfig.maxRows }"
          :placeholder="composerConfig.placeholder"
          :disabled="generationRunning"
          @keyup.enter.exact.prevent="onComposerEnter"
        />
        <div class="footer-actions">
          <el-button
            v-if="generationRunning"
            size="small"
            type="warning"
            plain
            @click="stopStreamGeneration"
          >
            {{ composerConfig.stopButtonLabel }}
          </el-button>
          <el-button
            class="send-button"
            type="primary"
            :loading="isThinking"
            :disabled="generationRunning"
            @click="handleSend"
          >
            {{ composerConfig.sendButtonLabel }}
          </el-button>
        </div>
      </div>
      </footer>
    </template>
    </PageScaffold>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { ArrowLeft, ChatDotRound, Plus, Delete } from '@element-plus/icons-vue'
import { marked } from 'marked'
import BrandMark from '@/components/BrandMark.vue'
import api from '@/utils/api'
import { ENABLE_PRO_STUDIO } from '@/config/featureFlags'
import PageScaffold from '@/components/templates/PageScaffold.vue'
import PageHeader from '@/components/templates/PageHeader.vue'
import {
  chatComposerConfig,
  activeCustomComposerId,
  resolveCustomComposer,
} from '@/adapters/chatComposer'

const composerConfig = chatComposerConfig
const customComposer = computed(() => resolveCustomComposer(activeCustomComposerId))

const onComposerEnter = () => {
  if (composerConfig.sendOnEnter) handleSend()
}

marked.setOptions({ gfm: true, breaks: true })

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const goToKnowledge = () => router.push('/knowledge')
const goBack = () => router.push('/')

const SKILL_LABELS: Record<string, string> = {
  rag_answer: '知识库检索',
  cite_snippets: '引用生成',
  read_local_file: '本地文件读取',
  summarize: '摘要生成',
  compare_docs: '文档对比',
  content_generation: '大模型内容生成',
  text_law_assist: '法务/合同场景检索',
  text_paper_assist: '论文/学术场景检索',
  text_format_assist: '格式与排版辅助',
  text_novel_assist: '小说/创作场景检索',
  skill_creator: '技能构建',
  scar_retrieve: 'SCAR 结构召回',
  scar_generate: 'SCAR 证据生成'
}

type ScarCitation = {
  file?: string
  file_id?: string
  path?: string
  unit_id?: string
}

type Agent = {
  id: string
  name: string
  description: string
  skills: string[]
}

type KnowledgeBase = {
  id: string
  title: string
  description?: string
  is_system_curriculum?: boolean
  is_owner?: boolean
  access_role?: 'owner' | 'viewer'
}

type ChatMessage = {
  id: string
  role: 'user' | 'agent'
  content: string
  meta?: {
    skills: string[]
    agentName: string
    evolutionPath?: string
    messageId?: string
    feedback?: 'like' | 'dislike'
    citations?: ScarCitation[]
    answerSource?: string
  }
}

const agents = ref<Agent[]>([])
const knowledgeBases = ref<KnowledgeBase[]>([])
const selectedKnowledgeBaseId = ref<string>('')
const currentAgentId = ref<string>('qa')
const messages = ref<ChatMessage[]>([])
const inputText = ref('')
const messagesRef = ref<HTMLElement | null>(null)
const isThinking = ref(false)
/** 从点击发送到本轮完全结束（含等待接口、读 SSE），用于显示「暂停生成」与禁用输入 */
const generationRunning = ref(false)
const streamAbortRef = ref<AbortController | null>(null)
const sessions = ref<any[]>([])
const showSessionList = ref(false)
const currentSessionId = ref<string | null>(null)
const analyticsEnabled = ref(false)
/** MVP-B：主编排下由后端路由到 english_vocab / grammar / listen */
const englishDelegate = ref<'default' | 'vocab' | 'grammar' | 'listen'>('default')
/** T5.4：演示用 SCAR 模式开关（true 时请求带 scar_mode） */
const scarMode = ref(false)

const ENGLISH_CHAT_AGENT_IDS = new Set([
  'english_orchestrator',
  'english_vocab',
  'english_grammar',
  'english_listen'
])

const englishTodaySummary = ref('')
const englishGraphLine = ref('')
const englishRecallPrompt = ref('')
const englishRecallLabel = ref('')
const recommendedCurriculumKbId = ref('')

function kbOptionLabel(kb: KnowledgeBase): string {
  if (kb.is_system_curriculum) return `${kb.title}（系统预置）`
  if (kb.title?.includes('英语学习 ·')) return `${kb.title}（个人路线）`
  return kb.title
}

function applyEnglishKnowledgeBaseSelection(force = false) {
  if (!ENGLISH_CHAT_AGENT_IDS.has(currentAgentId.value)) return
  const qKb = typeof route.query.kb === 'string' ? route.query.kb : ''
  if (qKb && knowledgeBases.value.some((k) => k.id === qKb)) return
  const rec = recommendedCurriculumKbId.value
  if (rec && knowledgeBases.value.some((k) => k.id === rec)) {
    if (force || !selectedKnowledgeBaseId.value || selectedKnowledgeBaseId.value !== rec) {
      selectedKnowledgeBaseId.value = rec
    }
  }
}

async function refreshEnglishTodayBar() {
  if (!ENGLISH_CHAT_AGENT_IDS.has(currentAgentId.value)) {
    englishTodaySummary.value = ''
    englishGraphLine.value = ''
    englishRecallPrompt.value = ''
    englishRecallLabel.value = ''
    return
  }
  englishGraphLine.value = ''
  const [todayResult, graphResult] = await Promise.allSettled([
    api.get('/english-learning/today/'),
    api.get('/english-learning/graph/status/')
  ])

  if (graphResult.status === 'fulfilled') {
    const gd = graphResult.value.data as {
      current_node?: string | null
      node_cursor?: number | null
    }
    const curRaw = gd.current_node
    const cur = curRaw != null && String(curRaw).trim() !== '' ? String(curRaw) : ''
    const c = gd.node_cursor
    if (cur) {
      englishGraphLine.value =
        typeof c === 'number' ? `向导图：${cur}（游标 ${c}）` : `向导图：${cur}`
    } else if (typeof c === 'number') {
      englishGraphLine.value = `向导图：游标 ${c}`
    }
  }

  if (todayResult.status !== 'fulfilled') {
    englishTodaySummary.value = ''
    englishRecallPrompt.value = ''
    englishRecallLabel.value = ''
    return
  }

  try {
    const data = todayResult.value.data as Record<string, unknown>
    const phase = String(data.phase || '')
    const tasks = (data.tasks || []) as { title: string }[]
    const t0 = tasks[0]
    const prefs = data.reminder_prefs as { do_not_disturb?: boolean; quiet_hours_active?: boolean } | undefined
    const suppressed = !!(prefs?.do_not_disturb || prefs?.quiet_hours_active)
    if (t0) {
      englishTodaySummary.value = suppressed
        ? phase
          ? `「${phase}」免打扰/安静时段 · ${t0.title}`
          : `免打扰/安静时段 · ${t0.title}`
        : phase
          ? `「${phase}」今日：${t0.title}`
          : `今日：${t0.title}`
    } else {
      englishTodaySummary.value = phase ? `当前阶段：${phase}` : ''
    }
    const pack = data.recall_pack as { pack_items?: { title: string; prompt: string }[] } | null
    const recKb = data.recommended_curriculum_kb_id
    if (typeof recKb === 'string' && recKb.trim()) {
      recommendedCurriculumKbId.value = recKb.trim()
      applyEnglishKnowledgeBaseSelection()
    }
    const first = pack?.pack_items?.[0]
    if (first?.prompt) {
      englishRecallPrompt.value = String(first.prompt)
      englishRecallLabel.value = first.title ? `回忆：${first.title}` : '插入回忆题'
    } else {
      englishRecallPrompt.value = ''
      englishRecallLabel.value = ''
    }
  } catch {
    englishTodaySummary.value = ''
    englishRecallPrompt.value = ''
    englishRecallLabel.value = ''
  }
}

watch(currentAgentId, (id) => {
  if (id !== 'english_orchestrator') englishDelegate.value = 'default'
  void refreshEnglishTodayBar()
  applyEnglishKnowledgeBaseSelection(true)
})

function normalizeApiList<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[]
  if (data && typeof data === 'object' && Array.isArray((data as { results?: unknown }).results)) {
    return (data as { results: T[] }).results
  }
  return []
}

onMounted(async () => {
  void authStore.hydrateFromProfile()
  try {
    const [agentsRes, kbRes, curriculumRes] = await Promise.all([
      api.get('/chat/agents/'),
      api.get('/knowledge/knowledge-bases/'),
      api.get('/english-learning/curriculum/').catch(() => ({ data: {} }))
    ])
    try {
      const analyticsRes = await api.get('/system/analytics/config/')
      analyticsEnabled.value = !!analyticsRes.data?.enabled
    } catch {
      analyticsEnabled.value = false
    }
    // 前端测试阶段先移除「技能构建助手」：builder agent 禁止在 UI 中选择
    agents.value = normalizeApiList<Agent>(agentsRes.data).filter(a => a.id !== 'builder')
    knowledgeBases.value = normalizeApiList<KnowledgeBase>(kbRes.data).map((kb) => ({
      ...kb,
      id: String(kb.id)
    }))
    const cur = curriculumRes.data as { recommended_knowledge_base_id?: string }
    if (cur?.recommended_knowledge_base_id) {
      recommendedCurriculumKbId.value = String(cur.recommended_knowledge_base_id)
    }
    if (agents.value.length) {
      const found = agents.value.find(a => a.id === currentAgentId.value)
      if (!found) currentAgentId.value = agents.value[0].id
    }
    if (knowledgeBases.value.length && !selectedKnowledgeBaseId.value) {
      if (ENGLISH_CHAT_AGENT_IDS.has(currentAgentId.value) && recommendedCurriculumKbId.value) {
        selectedKnowledgeBaseId.value = recommendedCurriculumKbId.value
      } else {
        selectedKnowledgeBaseId.value = knowledgeBases.value[0].id
      }
    }

    const qKb = typeof route.query.kb === 'string' ? route.query.kb : ''
    const qAgent = typeof route.query.agent === 'string' ? route.query.agent : ''
    if (qKb && knowledgeBases.value.some((k) => k.id === qKb)) {
      selectedKnowledgeBaseId.value = qKb
    }
    if (qAgent && agents.value.some((a) => a.id === qAgent)) {
      currentAgentId.value = qAgent
    }
    const qDel = typeof route.query.english_delegate === 'string' ? route.query.english_delegate.trim().toLowerCase() : ''
    if (currentAgentId.value === 'english_orchestrator' && ['vocab', 'grammar', 'listen'].includes(qDel)) {
      englishDelegate.value = qDel as 'vocab' | 'grammar' | 'listen'
    }
    await refreshEnglishTodayBar()
  } catch (e) {
    console.error('加载智能体或知识库失败:', e)
    ElMessage.warning('加载智能体或知识库失败，请刷新重试')
  }
})

const chips = ref([
  { text: '问答', example: '根据员工手册，总结考勤相关的三条关键规则。' },
  { text: '生成总结', example: '帮我生成这个知识库的内容总结。' },
  { text: '生成问答集', example: '生成这个知识库的常见问答集。' },
  { text: '计划', example: '根据公司 OKR，生成一个下周的工作计划草案。' },
  { text: '学习', example: '用通俗的方式解释一下我们安全规范里的“最小权限原则”。' }
])

const currentAgent = computed(() =>
  agents.value.find(a => a.id === currentAgentId.value) || agents.value[0] || null
)

/** 英语学习：URL 显式 phase 优先，否则英语类 Agent 默认 tutor（与后端路线摘录一致） */
const englishPhasePayload = computed(() => {
  const q =
    typeof route.query.english_phase === 'string' ? route.query.english_phase.trim().toLowerCase() : ''
  if (q) return q
  if (ENGLISH_CHAT_AGENT_IDS.has(currentAgentId.value)) return 'tutor'
  return ''
})

const englishProfileIdPayload = computed(() => {
  const q =
    typeof route.query.english_profile_id === 'string'
      ? route.query.english_profile_id.trim()
      : ''
  return q || undefined
})

const thinkingSkillsText = computed(() => {
  const agent = currentAgent.value
  if (!agent?.skills?.length) return '知识库检索'
  return agent.skills.slice(0, 2).map(s => SKILL_LABELS[s] || s).join('、')
})

function scrollChatToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function stopStreamGeneration() {
  streamAbortRef.value?.abort()
}

function normalizeCitations(citations: unknown, sources: unknown): ScarCitation[] {
  if (Array.isArray(citations) && citations.length) {
    return citations
      .map((c: any) => ({
        file: c?.file || c?.title || '',
        file_id: c?.file_id ? String(c.file_id) : '',
        path: c?.path || '',
        unit_id: c?.unit_id || ''
      }))
      .filter((c) => c.path)
  }
  if (Array.isArray(sources) && sources.length) {
    return sources
      .map((s) => (typeof s === 'string' ? { path: s } : { path: String((s as any)?.path || '') }))
      .filter((c) => c.path)
  }
  return []
}

const handleSend = async () => {
  const text = inputText.value.trim()
  if (!text) {
    ElMessage.info('请输入内容')
    return
  }
  if (!selectedKnowledgeBaseId.value) {
    ElMessage.warning('请先选择知识库')
    return
  }

  const userMsg: ChatMessage = {
    id: `${Date.now()}-u`,
    role: 'user',
    content: text
  }
  messages.value.push(userMsg)
  inputText.value = ''

  const agent = currentAgent.value
  const usedSkills = agent?.skills?.slice(0, 2) || ['rag_answer', 'cite_snippets']
  const assistantId = `${Date.now()}-a`

  const payload: Record<string, unknown> = {
    question: text,
    knowledge_base_id: selectedKnowledgeBaseId.value,
    agent_id: currentAgentId.value,
    use_agent: true
  }
  if (currentSessionId.value) payload.session_id = currentSessionId.value
  const elPhase = englishPhasePayload.value
  if (elPhase) payload.english_phase = elPhase
  const elPid = englishProfileIdPayload.value
  if (elPid) payload.english_profile_id = elPid
  if (currentAgentId.value === 'english_orchestrator' && englishDelegate.value !== 'default') {
    payload.english_delegate = englishDelegate.value
  }
  if (scarMode.value) {
    payload.scar_mode = true
    payload.scar_domain = 'construction'
  }

  isThinking.value = true
  generationRunning.value = true
  streamAbortRef.value = new AbortController()
  const token = localStorage.getItem('token') || ''

  scrollChatToBottom()

  const yieldToPaint = () =>
    new Promise<void>((resolve) => {
      requestAnimationFrame(() => resolve())
    })

  const runSseStream = async () => {
    const res = await fetch('/api/v1/chat/ask/stream/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: JSON.stringify(payload),
      signal: streamAbortRef.value!.signal
    })
    if (!res.ok || !res.body) {
      throw new Error('stream_not_available')
    }

    const agentMsg: ChatMessage = {
      id: assistantId,
      role: 'agent',
      content: '',
      meta: {
        skills: usedSkills,
        agentName: agent?.name || '智能助手',
        evolutionPath: ''
      }
    }
    messages.value.push(agentMsg)
    isThinking.value = false

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    let chunkTick = 0
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const blocks = buf.split('\n\n')
      buf = blocks.pop() || ''
      for (const block of blocks) {
        const lines = block.split('\n')
        const event = (lines.find((x) => x.startsWith('event:')) || '').replace('event:', '').trim()
        const dataLine = lines.find((x) => x.startsWith('data:'))
        const data = dataLine ? dataLine.replace('data:', '').trim() : ''
        if (event === 'chunk' && data) {
          try {
            const parsed = JSON.parse(data)
            const delta = String(parsed.delta || '')
            const msg = messages.value.find((m) => m.id === assistantId)
            if (msg) msg.content += delta
            chunkTick += 1
            // 同一次事件循环内会处理上千个 chunk，浏览器只画一帧；让出主线程才能「逐字」可见
            if (chunkTick % 2 === 0) {
              await yieldToPaint()
            }
            if (chunkTick % 20 === 0) scrollChatToBottom()
          } catch {
            /* ignore */
          }
        }
        if (event === 'end' && data) {
          try {
            const parsed = JSON.parse(data)
            const msg = messages.value.find((m) => m.id === assistantId)
            if (msg?.meta) {
              msg.meta.skills = parsed.skills_used || msg.meta.skills
              msg.meta.agentName = parsed.agent_name || msg.meta.agentName
              msg.meta.evolutionPath = parsed.evolution_path || ''
              msg.meta.messageId = parsed.message_id ? String(parsed.message_id) : msg.meta.messageId
              msg.meta.citations = normalizeCitations(parsed.citations, parsed.sources)
              msg.meta.answerSource = parsed.answer_source || msg.meta.answerSource
            }
            if (parsed.session_id) currentSessionId.value = String(parsed.session_id)
          } catch {
            /* ignore */
          }
        }
      }
    }
    scrollChatToBottom()
  }

  try {
    await runSseStream()
  } catch (e: unknown) {
    const aborted = (e as { name?: string })?.name === 'AbortError'
    if (aborted) {
      const msg = messages.value.find((m) => m.id === assistantId)
      if (msg && !msg.content.includes('已停止展示')) {
        msg.content += '\n\n*（已停止展示后续输出）*'
      }
      ElMessage.info('已停止生成展示')
      isThinking.value = false
      scrollChatToBottom()
      return
    }
    const partial = messages.value.find((m) => m.id === assistantId)
    if (partial) {
      ElMessage.error('流式输出中断，请稍后重试或换用同步接口')
      isThinking.value = false
      scrollChatToBottom()
      return
    }
    try {
      const response = await api.post('/chat/ask/', payload)
      const data = response.data
      if (data.session_id) currentSessionId.value = data.session_id
      messages.value.push({
        id: assistantId,
        role: 'agent',
        content: data.answer || '暂无回答',
        meta: {
          skills: data.skills_used || usedSkills,
          agentName: data.agent_name || agent?.name || '智能助手',
          evolutionPath: data.evolution_path || '',
          messageId: data.message_id ? String(data.message_id) : undefined,
          citations: normalizeCitations(data.citations, data.sources),
          answerSource: data.answer_source || ''
        }
      })
    } catch (e2: unknown) {
      const err = e2 as { response?: { data?: { error?: string } }; message?: string }
      const msg = err.response?.data?.error || err.message || '发送失败，请重试'
      ElMessage.error(msg)
      messages.value.push({
        id: `${Date.now()}-err`,
        role: 'agent',
        content: `请求失败：${msg}`,
        meta: { skills: [], agentName: '' }
      })
    }
  } finally {
    isThinking.value = false
    generationRunning.value = false
    streamAbortRef.value = null
    scrollChatToBottom()
  }
}

const submitFeedbackEvent = async (msg: ChatMessage, feedback: 'like' | 'dislike') => {
  if (!analyticsEnabled.value || msg.role !== 'agent') return
  msg.meta = {
    skills: msg.meta?.skills || [],
    agentName: msg.meta?.agentName || '',
    evolutionPath: msg.meta?.evolutionPath || '',
    messageId: msg.meta?.messageId,
    feedback
  }
  try {
    await api.post('/system/analytics/track/', {
      event_name: feedback === 'like' ? 'chat_feedback_like' : 'chat_feedback_dislike',
      session_id: currentSessionId.value || undefined,
      payload: {
        message_id: msg.meta?.messageId || '',
        agent_name: msg.meta?.agentName || '',
      }
    })
    ElMessage.success(feedback === 'like' ? '已记录：有帮助' : '已记录：需改进')
  } catch {
    ElMessage.warning('反馈记录失败，请稍后重试')
  }
}

const useChip = (example: string) => {
  inputText.value = example
}

function formatTime(val: string | Date | undefined): string {
  if (!val) return '-'
  const d = typeof val === 'string' ? new Date(val) : val
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

const loadSessions = async () => {
  try {
    const res = await api.get('/chat/sessions/')
    sessions.value = res.data || []
  } catch (e) {
    console.error('加载会话列表失败:', e)
  }
}

const loadSession = async (sessionId: string) => {
  try {
    const res = await api.get(`/chat/sessions/${sessionId}/`)
    const msgs = res.data?.messages || []
    messages.value = msgs.map((m: any) => ({
      id: m.id,
      role: m.message_type === 'user' ? 'user' : 'agent',
      content: m.message_type === 'user' ? m.question : m.answer,
      meta: m.message_type === 'assistant' ? { skills: [], agentName: '' } : undefined
    }))
    currentSessionId.value = sessionId
    showSessionList.value = false
    nextTick(() => {
      if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    })
  } catch (e) {
    console.error('加载会话失败:', e)
    ElMessage.error('加载会话失败')
  }
}

const createNewSession = () => {
  messages.value = []
  currentSessionId.value = null
  showSessionList.value = false
}

const deleteSession = async (sessionId: string) => {
  try {
    await api.delete(`/chat/sessions/${sessionId}/delete/`)
    await loadSessions()
    if (currentSessionId.value === sessionId) createNewSession()
    ElMessage.success('会话已删除')
  } catch (e) {
    console.error('删除会话失败:', e)
    ElMessage.error('删除会话失败')
  }
}

/** 将「主要参考文档」标题及其后紧邻的列表包一层，便于高亮展示 */
function wrapMainRefDocsBlock(html: string): string {
  const block =
    /<p>\s*<strong>\s*主要参考文档\s*<\/strong>\s*<\/p>\s*(?:<ul>[\s\S]*?<\/ul>|<ol>[\s\S]*?<\/ol>)?/gi
  return html.replace(block, (m) => `<div class="ref-docs-highlight">${m}</div>`)
}

function renderMarkdown(text: string): string {
  if (!text || typeof text !== 'string') return ''
  const cleaned = text.replace(/^```json\s*/i, '').replace(/\s*```\s*$/i, '').trim()
  const raw = marked.parse(cleaned) as string
  return wrapMainRefDocsBlock(raw)
}
</script>

<style scoped>
.english-today-bar {
  flex-shrink: 0;
}
.english-today-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
}
.english-today-text {
  flex: 1;
  min-width: 160px;
  font-size: 0.9rem;
}
.english-graph-hint {
  font-size: 0.8rem;
  color: var(--text-200);
  white-space: nowrap;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}
.agent-chat-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: radial-gradient(circle at top, var(--bg-100) 0, var(--bg-200) 45%, var(--bg-100) 100%);
  padding: 24px 32px 32px;
  box-sizing: border-box;
}

.chat-scaffold {
  height: 100%;
  background: var(--apple-background);
}

.chat-scaffold :deep(.page-scaffold) {
  height: 100%;
  gap: 0;
  background: var(--apple-background);
}

.chat-scaffold :deep(.page-scaffold__content),
.chat-scaffold :deep(.page-scaffold__feedback) {
  background: var(--apple-background);
}

.chat-top {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin: 0 auto 16px;
  padding: 8px 12px;
  border-radius: var(--apple-radius-lg);
  background: var(--apple-surface);
  border: 1px solid var(--bg-300);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  max-width: 960px;
}

.chat-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.chat-title h2 {
  margin: 0;
  font-size: var(--apple-font-size-h3);
}

.chat-title p {
  margin: 4px 0 0;
  font-size: var(--apple-font-size-caption);
  color: var(--apple-text-secondary);
}

.chat-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
  max-width: 100%;
}

.chat-back-btn {
  flex-shrink: 0;
}

/* 固定宽度，避免单独占一行时被 flex 拉成 600px+ */
.control-select {
  flex: 0 0 auto;
  width: 220px;
  max-width: min(260px, 46vw);
  min-width: 140px;
}

/* EP 2.4+ 使用 el-select__wrapper；overflow 放在 wrapper 上避免裁切内部 z-index 层 */
.control-select :deep(.el-select__wrapper) {
  width: 100%;
  max-width: 100%;
  overflow: hidden;
  border-radius: var(--apple-radius-pill);
  background: rgba(255, 255, 255, 0.65) !important;
  box-shadow: 0 0 0 1px var(--bg-300) inset !important;
  color: var(--apple-text-primary) !important;
}

/*
 * 勿对 .el-select__selection 设 overflow:hidden：选中项在 EP 里常放在 z-index:-1 的 placeholder 上，
 * 会被裁切或看起来像「框里没有字」。ellipsis 改在 wrapper / input 层处理。
 */
.control-select :deep(.el-select__selection) {
  min-width: 0;
  overflow: visible;
}

.control-select :deep(.el-select__selected-item) {
  min-width: 0;
}

.control-select :deep(.el-select__tags-text) {
  color: var(--apple-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 选中项占位层默认 z-index:-1，提到正值避免被兄弟层挡住 */
.control-select :deep(.el-select__placeholder) {
  z-index: 1 !important;
  color: var(--apple-text-primary) !important;
  -webkit-text-fill-color: var(--apple-text-primary) !important;
}

.control-select :deep(.el-select__placeholder.is-transparent) {
  color: var(--apple-text-primary) !important;
  -webkit-text-fill-color: var(--apple-text-primary) !important;
  opacity: 1 !important;
}

/* filterable：真实输入框文字必须可见 */
.control-select :deep(.el-select__input) {
  color: var(--apple-text-primary) !important;
  -webkit-text-fill-color: var(--apple-text-primary) !important;
  caret-color: var(--apple-text-primary);
}

.control-select :deep(.el-select__input-wrapper:not(.is-hidden)) {
  flex: 1;
  min-width: 0;
}

.control-select :deep(.el-select__caret),
.control-select :deep(.el-select__suffix) {
  color: var(--apple-text-secondary);
}

.control-select :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 2px rgba(255, 90, 95, 0.2) inset !important;
}

.agent-option {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.35;
  padding: 4px 0;
  max-width: 420px;
}
.agent-option-name {
  font-weight: 600;
  color: var(--apple-text-primary);
}
.agent-option-desc {
  font-size: 12px;
  color: var(--apple-text-secondary);
  white-space: normal;
  word-break: break-word;
}

.chat-main {
  flex: 1;
  display: flex;
  justify-content: center;
  padding: 24px 0 8px;
  background: var(--apple-background);
}

.chat-messages {
  width: 100%;
  max-width: 760px;
  background: transparent;
  border-radius: 0;
  border: none;
  padding: 0 0 12px;
  overflow-y: auto;
}

.chat-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-top: 40px;
}

.zero-hero {
  max-width: 640px;
  text-align: center;
}

.zero-eyebrow {
  font-size: var(--apple-font-size-caption);
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--apple-text-secondary);
  margin: 0 0 8px;
}

.zero-title {
  margin: 0 0 12px;
  font-size: 32px;
  font-weight: 600;
}

.zero-subtitle {
  margin: 0 auto 18px;
  max-width: 520px;
  font-size: var(--apple-font-size-body);
  color: var(--apple-text-secondary);
  line-height: 1.5;
}

.zero-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
}

.chip {
  border-radius: 999px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  padding: 6px 14px;
  background: var(--bg-200);
  font-size: var(--apple-font-size-caption);
  cursor: pointer;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.chip:hover {
  border-color: rgba(15, 23, 42, 0.16);
  background: var(--bg-300);
}

.chat-message {
  margin-bottom: 14px;
  display: flex;
}

.from-user {
  justify-content: flex-end;
}

.bubble {
  max-width: 72%;
  padding: 10px 14px;
  border-radius: 18px;
  background: var(--bg-300);
}

.from-user .bubble {
  background: var(--primary-100);
  color: var(--text-on-primary);
}

.bubble-text {
  margin: 0 0 4px;
  word-break: break-word;
  line-height: 1.6;
  font-size: 14px;
}

.bubble-text.markdown-body :deep(h1),
.bubble-text.markdown-body :deep(h2),
.bubble-text.markdown-body :deep(h3),
.bubble-text.markdown-body :deep(h4) {
  margin: 1em 0 0.5em;
  font-weight: 600;
  line-height: 1.3;
}

.bubble-text.markdown-body :deep(h1) { font-size: 1.2rem; }
.bubble-text.markdown-body :deep(h2) { font-size: 1.1rem; }
.bubble-text.markdown-body :deep(h3) { font-size: 1rem; }
.bubble-text.markdown-body :deep(h4) { font-size: 0.95rem; }

.bubble-text.markdown-body :deep(p) { margin: 0.5em 0; }
.bubble-text.markdown-body :deep(ul),
.bubble-text.markdown-body :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.4em;
}

.bubble-text.markdown-body :deep(li) { margin: 0.25em 0; }
.bubble-text.markdown-body :deep(strong) { font-weight: 600; }

/* 「主要参考文档」整块高亮（由 wrapMainRefDocsBlock 注入 .ref-docs-highlight） */
.bubble-text.markdown-body :deep(.ref-docs-highlight) {
  margin: 0.85em 0;
  padding: 12px 14px 12px 16px;
  border-radius: 12px;
  background: linear-gradient(
    125deg,
    rgba(255, 90, 95, 0.12) 0%,
    rgba(99, 102, 241, 0.1) 50%,
    rgba(59, 130, 246, 0.08) 100%
  );
  border: 1px solid rgba(255, 90, 95, 0.22);
  border-left: 4px solid var(--primary-100, #ff5a5f);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.6) inset;
}

.bubble-text.markdown-body :deep(.ref-docs-highlight p) {
  margin: 0 0 0.4em;
}

.bubble-text.markdown-body :deep(.ref-docs-highlight p:last-child:not(:only-child)) {
  margin-bottom: 0.35em;
}

.bubble-text.markdown-body :deep(.ref-docs-highlight ul),
.bubble-text.markdown-body :deep(.ref-docs-highlight ol) {
  margin: 0.35em 0 0;
  padding-left: 1.35em;
}

.bubble-text.markdown-body :deep(.ref-docs-highlight li:last-child) {
  margin-bottom: 0;
}

.bubble-text.markdown-body :deep(.ref-docs-highlight strong) {
  color: var(--primary-100, #c42d32);
  font-weight: 700;
  letter-spacing: 0.02em;
}

.bubble-text.markdown-body :deep(code) {
  padding: 0.15em 0.4em;
  font-size: 0.9em;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
}

.bubble-text.markdown-body :deep(pre) {
  margin: 0.5em 0;
  padding: 10px 12px;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 8px;
  overflow-x: auto;
  font-size: 13px;
}

.bubble-text.markdown-body :deep(:first-child) { margin-top: 0; }
.bubble-text.markdown-body :deep(:last-child) { margin-bottom: 0; }

.bubble-meta {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.scar-citations {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.04);
  border: 1px solid rgba(15, 23, 42, 0.06);
}

.scar-citations-title {
  font-size: 12px;
  color: var(--apple-text-secondary);
  margin-bottom: 6px;
}

.scar-citation-row {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  font-size: 12px;
  line-height: 1.4;
  margin-bottom: 4px;
}

.scar-cite-file {
  color: var(--apple-text-secondary);
}

.scar-cite-sep {
  opacity: 0.45;
}

.scar-cite-path {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--apple-text-primary);
}

.scar-source-tag {
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
  font-size: 11px;
}

.scar-mode-switch {
  margin: 0 4px;
}

.agent-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--apple-radius-pill);
  background: rgba(255, 90, 95, 0.12);
  color: var(--primary-100);
  margin-right: 4px;
}

.meta-label {
  font-size: 12px;
  color: var(--text-200);
}

.skill-tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: var(--apple-radius-pill);
  background: rgba(0, 166, 153, 0.12);
  color: var(--accent-100);
}

.evo-path-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: var(--apple-radius-pill);
  background: rgba(59, 130, 246, 0.12);
  color: #2563eb;
}

.feedback-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: 6px;
}

.thinking-bubble {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 48px;
}

.thinking-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid var(--bg-300);
  border-top-color: var(--primary-100);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.thinking-text {
  margin: 0;
  font-size: 13px;
  color: var(--text-200);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.chat-footer {
  padding: 16px 0 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  background: var(--apple-background);
  border-top: none;
  margin-top: 0;
}

.input-shell {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  padding: 8px 10px;
  border-radius: 999px;
  background: var(--apple-elevated);
  border: 1px solid var(--apple-border);
  box-shadow: none;
}

.footer-actions {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
}

.send-button {
  flex-shrink: 0;
}

.chat-footer :deep(.el-textarea) {
  flex: 1;
}

.chat-footer :deep(.el-textarea__inner) {
  border-radius: 999px;
  background-color: transparent;
  border: none;
  min-height: var(--apple-input-height);
  padding-top: 6px;
  padding-bottom: 6px;
  box-shadow: none;
}

/* 会话列表弹窗 */
.session-dialog :deep(.el-dialog) {
  border-radius: 16px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
}

.session-dialog :deep(.el-dialog__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--bg-300);
}

.session-dialog :deep(.el-dialog__body) {
  padding: 16px 20px;
  max-height: 420px;
  overflow-y: auto;
}

.session-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: var(--bg-200);
  border: 1px solid var(--bg-300);
  cursor: pointer;
  transition: all 0.2s ease;
}

.session-item:hover {
  border-color: var(--primary-100);
  background: rgba(255, 90, 95, 0.04);
}

.session-item.active {
  border-color: var(--primary-100);
  background: rgba(255, 90, 95, 0.08);
}

.session-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--primary-100);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--apple-text-primary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  font-size: 12px;
  color: var(--apple-text-secondary);
  display: flex;
  gap: 12px;
}

.last-message {
  font-size: 12px;
  color: var(--apple-text-secondary);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-actions {
  flex-shrink: 0;
}

.empty-sessions {
  text-align: center;
  padding: 40px 20px;
  color: var(--apple-text-secondary);
}

.empty-sessions .empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
  opacity: 0.5;
}

.empty-sessions h3 {
  margin: 0 0 8px;
  font-size: 16px;
  color: var(--apple-text-primary);
}

.empty-sessions p {
  margin: 0;
  font-size: 13px;
}
</style>

