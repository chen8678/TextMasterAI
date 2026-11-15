<template>
  <div class="studio-page">
    <header class="titlebar">
      <div class="title-left">Text Master AI · PRO Studio</div>
      <div class="title-right">
        <el-select v-model="mode" size="small" class="mode-select">
          <el-option label="小说模式" value="novel" />
          <el-option label="论文模式" value="paper" />
          <el-option label="合同模式" value="contract" />
        </el-select>
        <el-button size="small" @click="saveDraft">保存</el-button>
        <el-button size="small" type="primary" @click="router.push('/chat')">返回问答</el-button>
      </div>
    </header>

    <div class="ide-shell" :style="shellStyle">
      <aside class="activity-bar">
        <div class="act active">文</div>
        <div class="act">知</div>
        <div class="act">AI</div>
      </aside>

      <aside v-show="!explorerCollapsed" class="explorer">
        <div class="explorer-head">EXPLORER</div>
        <div class="explorer-section">
          <div class="section-title">
            草稿（{{ drafts.length }}）
            <el-button text size="small" @click="createNewDraft">新建</el-button>
          </div>
          <div class="draft-list">
            <button
              v-for="item in drafts"
              :key="item.id"
              class="draft-item"
              :class="{ active: item.id === currentDraftId }"
              @click="loadDraft(item.id)"
            >
              <span class="draft-item-title">{{ item.title || '未命名草稿' }}</span>
              <span class="draft-delete" @click.stop="removeDraft(item.id)">删除</span>
            </button>
            <div v-if="drafts.length === 0" class="muted">暂无草稿</div>
          </div>
        </div>
        <div class="explorer-section">
          <div class="section-title">知识库</div>
          <el-select
            v-model="selectedKbId"
            filterable
            placeholder="选择知识库"
          >
            <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.title" :value="kb.id" />
          </el-select>
        </div>
      </aside>
      <button class="explorer-toggle" @click="explorerCollapsed = !explorerCollapsed">
        {{ explorerCollapsed ? '>' : '<' }}
      </button>

      <section class="editor-pane">
        <div class="editor-tabs">
          <div class="tab-list">
            <button
              v-for="item in drafts.slice(0, 6)"
              :key="`tab-${item.id}`"
              class="tab"
              :class="{ active: item.id === currentDraftId }"
              @click="loadDraft(item.id)"
            >
              {{ item.title || 'untitled.md' }}
            </button>
          </div>
          <div class="tab-meta">{{ saveStatus }}</div>
        </div>
        <div class="editor-toolbar">
          <el-input v-model="draftTitle" placeholder="输入草稿标题" class="draft-title" />
          <el-dropdown
            trigger="click"
            :disabled="!currentDraftId"
            @visible-change="onRevisionDropdown"
          >
            <el-button size="small" plain :disabled="!currentDraftId">历史版本</el-button>
            <template #dropdown>
              <el-dropdown-menu class="revision-menu">
                <el-dropdown-item v-if="draftRevisions.length === 0" disabled>
                  暂无历史（需先多次保存产生快照）
                </el-dropdown-item>
                <el-dropdown-item
                  v-for="r in draftRevisions"
                  :key="r.revision_index"
                  @click="confirmRestoreRevision(r)"
                >
                  v{{ r.revision_index }} · {{ formatRevTime(r.created_at) }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <span class="muted">自动保存：{{ autosaveLabel }}</span>
        </div>
        <el-input
          ref="draftEditorRef"
          v-model="draftContent"
          type="textarea"
          :autosize="{ minRows: 24, maxRows: 30 }"
          class="editor-like"
          placeholder="在这里开始写作..."
        />
      </section>

      <div class="right-resizer" @mousedown="startResize" />
      <aside class="assistant-pane">
        <section class="assistant-card">
          <div class="card-head">
            <div class="chat-header-left">
              <el-button-group>
                <el-button size="small" :type="currentMode === 'chat' ? 'primary' : 'default'" @click="currentMode = 'chat'">Chat</el-button>
                <el-button size="small" :type="currentMode === 'agent' ? 'primary' : 'default'" @click="currentMode = 'agent'">Agent</el-button>
              </el-button-group>
              <el-select v-model="selectedModel" size="small" class="chat-model-select">
                <el-option label="deepseek-chat" value="deepseek-chat" />
                <el-option label="deepseek-reasoner" value="deepseek-reasoner" />
                <el-option label="qwen-turbo" value="qwen-turbo" />
              </el-select>
            </div>
            <div class="chat-header-right">
              <el-button text size="small" @click="showHistory = !showHistory">{{ showHistory ? '隐藏历史' : '历史' }}</el-button>
              <span class="muted">{{ modeLabel }} · {{ modeAgentId }}</span>
            </div>
          </div>
          <div v-if="showHistory" class="history-panel">
            <div
              v-for="s in studioSessions"
              :key="s.id"
              class="history-item"
              :class="{ active: s.id === studioSessionId }"
              @click="switchStudioSession(s.id)"
            >
              <span class="history-title">{{ s.title || '未命名会话' }}</span>
              <span class="history-time">{{ formatTime(s.last_activity || s.created_at || '') }}</span>
              <div class="history-actions">
                <el-button text size="small" @click.stop="duplicateStudioSession(s.id)">复制</el-button>
                <el-button text size="small" type="danger" @click.stop="deleteStudioSession(s.id)">删除</el-button>
              </div>
            </div>
            <div v-if="studioSessions.length === 0" class="muted">暂无历史会话</div>
          </div>
          <div class="studio-answer">
            <div v-if="studioMessages.length === 0" class="muted">暂无对话，输入问题后按 Enter 发送</div>
            <div
              v-for="msg in studioMessages"
              :key="msg.id"
              class="chat-item"
              :class="msg.role === 'user' ? 'chat-item-user' : 'chat-item-assistant'"
            >
              <div class="chat-role">{{ msg.role === 'user' ? '你' : 'AI' }}</div>
              <div v-if="msg.role === 'assistant' && msg.evolutionPath" class="msg-evo">
                {{ renderEvolutionPath(msg.evolutionPath) }}
              </div>
              <div v-if="msg.refs?.length" class="msg-refs">
                <span v-for="(r, i) in msg.refs" :key="`${msg.id}-ref-${i}`" class="msg-ref-chip">
                  {{ renderRefLabel(r) }}
                </span>
              </div>
              <div class="chat-content markdown-body" v-html="renderMarkdown(msg.content)"></div>
              <div
                v-if="msg.role === 'assistant' && extractCodeBlocks(msg.content).length"
                class="code-actions"
              >
                <el-button
                  v-for="(code, idx) in extractCodeBlocks(msg.content)"
                  :key="`${msg.id}-code-${idx}`"
                  size="small"
                  @click="copyCode(code)"
                >
                  复制代码 {{ idx + 1 }}
                </el-button>
                <el-button
                  v-for="(code, idx) in extractCodeBlocks(msg.content)"
                  :key="`${msg.id}-apply-${idx}`"
                  size="small"
                  type="primary"
                  plain
                  @click="applyToEditor(code)"
                >
                  应用到编辑区 {{ idx + 1 }}
                </el-button>
              </div>
            </div>
          </div>
          <el-input
            v-model="studioQuestion"
            type="textarea"
            :autosize="{ minRows: 4, maxRows: 7 }"
            :placeholder="`向 AI 提问（${modeLabel}）`"
            @input="onStudioInput"
            @keydown.enter.exact.prevent="askStudio"
            @keydown.enter.shift.stop
          />
          <div v-if="mentionOpen" class="mention-panel">
            <button
              v-for="item in mentionCandidates"
              :key="item.key"
              class="mention-item"
              @click="selectMention(item)"
            >
              <span class="mention-type">{{ item.type === 'draft' ? '@草稿' : '@知识库' }}</span>
              <span class="mention-label">{{ item.label }}</span>
            </button>
            <div v-if="mentionCandidates.length === 0" class="muted">未匹配到可引用内容</div>
          </div>
          <div v-if="selectedRefs.length" class="selected-refs">
            <span
              v-for="r in selectedRefs"
              :key="r.key"
              class="ref-chip"
            >
              {{ r.type === 'draft' ? '草稿' : '知识库' }}: {{ r.label }}
              <button class="chip-remove" @click="removeRef(r.key)">×</button>
            </span>
          </div>
          <div class="row">
            <el-button type="primary" :loading="asking" @click="askStudio">发送</el-button>
            <el-button @click="newStudioSession">新会话</el-button>
          </div>
        </section>
      </aside>
    </div>

    <footer class="status-bar">
      <span v-if="!isOnline" class="offline-banner">离线 · 编辑内容已暂存本机浏览器</span>
      <span>MODE: {{ modeLabel }}</span>
      <span>AGENT: {{ modeAgentId }}</span>
      <span>KB: {{ selectedKbId || '-' }}</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { ElInput } from 'element-plus'
import { marked } from 'marked'
import api from '@/utils/api'

type KB = { id: string; title: string }
type DraftItem = {
  id: string
  title: string
  content: string
  mode: 'novel' | 'paper' | 'contract'
  updatedAt: string
}

type DraftRevisionRow = {
  revision_index: number
  title: string
  mode: string
  created_at: string
  content_preview: string
}

const router = useRouter()
const route = useRoute()
const mode = ref<'novel' | 'paper' | 'contract'>('novel')
const draftTitle = ref('')
const draftContent = ref('')
const draftEditorRef = ref<InstanceType<typeof ElInput> | null>(null)
const saveStatus = ref('未保存')
const currentDraftId = ref('')
const drafts = ref<DraftItem[]>([])
const draftRevisions = ref<DraftRevisionRow[]>([])
const autosaveLabel = ref('开启')
/** 相对服务端草稿是否有未同步的本地编辑（P3-T03 合并提示用） */
const dirty = ref(false)
const suppressDirty = ref(false)
let autosaveTimer: ReturnType<typeof setTimeout> | null = null
/** 任意来源的保存互斥；避免与重试打架 */
let persistInFlight = false
let persistQueued = false
const MAX_SAVE_RETRIES = 4
const SAVE_RETRY_DELAYS_MS = [600, 1200, 2500, 4000]

const isOnline = ref(typeof navigator !== 'undefined' ? navigator.onLine : true)

const TAB_INSTANCE_ID = `${Date.now()}-${Math.random().toString(36).slice(2, 11)}`
let studioBroadcast: BroadcastChannel | null = null
const explorerCollapsed = ref(false)
const rightPaneWidth = ref(360)
let resizing = false

const studioQuestion = ref('')
const asking = ref(false)
const studioSessionId = ref('')
type RefItem = { type: 'draft' | 'kb'; id: string; label: string }
type StudioMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  refs?: RefItem[]
  evolutionPath?: string
}
type StudioSession = { id: string; title?: string; created_at?: string; last_activity?: string }
type MentionItem = { key: string; type: 'draft' | 'kb'; label: string; value: string }
const studioMessages = ref<StudioMessage[]>([])
const studioSessions = ref<StudioSession[]>([])
const showHistory = ref(false)
const currentMode = ref<'chat' | 'agent'>('chat')
const selectedModel = ref('deepseek-chat')
const mentionOpen = ref(false)
const mentionCandidates = ref<MentionItem[]>([])
const selectedRefs = ref<MentionItem[]>([])

const knowledgeBases = ref<KB[]>([])
const selectedKbId = ref('')

const DRAFT_KEY = 'text-master:studio:draft:v1'
const DRAFT_LIST_KEY = 'text-master:studio:drafts:v1'

const modeLabel = computed(() => {
  if (mode.value === 'paper') return '论文'
  if (mode.value === 'contract') return '合同'
  return '小说'
})
const modeAgentId = computed(() => {
  // Studio 模式与后端 Agent 的固定映射，前后端都依赖这组值。
  if (mode.value === 'paper') return 'paper_kb'
  if (mode.value === 'contract') return 'law_kb'
  return 'novel_kb'
})
const shellStyle = computed(() => {
  const right = Math.max(280, Math.min(620, rightPaneWidth.value))
  return {
    gridTemplateColumns: explorerCollapsed.value
      ? `48px 16px 1fr 6px ${right}px`
      : `48px 240px 16px 1fr 6px ${right}px`
  }
})
const STUDIO_SESSION_KEY = 'text-master:studio:chat-session:v1'
const STUDIO_SYNC_CHANNEL = 'text-master-studio-sync-v1'

function backupDraftLocal() {
  try {
    localStorage.setItem(
      DRAFT_KEY,
      JSON.stringify({
        id: currentDraftId.value,
        title: draftTitle.value,
        content: draftContent.value,
        mode: mode.value,
        savedAt: new Date().toISOString()
      })
    )
  } catch {
    // quota / 隐私模式等
  }
}

function broadcastDraftSavedRemote(draftId: string) {
  if (!studioBroadcast || !draftId) return
  try {
    studioBroadcast.postMessage({
      type: 'draft-saved',
      draftId,
      sourceTab: TAB_INSTANCE_ID
    })
  } catch {
    /* noop */
  }
}

function broadcastStudioSessionsChanged() {
  if (!studioBroadcast) return
  try {
    studioBroadcast.postMessage({
      type: 'studio-sessions-changed',
      sourceTab: TAB_INSTANCE_ID
    })
  } catch {
    /* noop */
  }
}

function initStudioBroadcast() {
  if (typeof BroadcastChannel === 'undefined') return
  try {
    studioBroadcast = new BroadcastChannel(STUDIO_SYNC_CHANNEL)
    studioBroadcast.onmessage = (ev) => {
      const msg = ev.data as { type?: string; draftId?: string; sourceTab?: string } | null
      if (!msg || typeof msg !== 'object') return
      if (msg.sourceTab === TAB_INSTANCE_ID) return

      if (msg.type === 'studio-sessions-changed') {
        void loadStudioSessions()
        return
      }
      if (msg.type !== 'draft-saved' || !msg.draftId) return

      void fetchDrafts().then(async () => {
        if (msg.draftId !== currentDraftId.value) return
        if (!dirty.value) {
          suppressDirty.value = true
          try {
            await loadDraft(msg.draftId!)
            saveStatus.value = '已从其他标签页同步'
          } finally {
            await nextTick()
            suppressDirty.value = false
          }
        } else {
          ElMessage.warning({
            message: '其他标签页已保存当前草稿，请在关闭前核对内容避免覆盖',
            duration: 4500
          })
        }
      })
    }
  } catch {
    studioBroadcast = null
  }
}

function setOnlineFlag() {
  isOnline.value = navigator.onLine
}

function restoreDraft() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) return
    suppressDirty.value = true
    const parsed = JSON.parse(raw)
    const rawId = String(parsed.id || '')
    // 仅保留服务端 UUID 草稿 id；旧版本地 d-xxx id 会导致 PUT 404 并中断初始化。
    currentDraftId.value = /^[0-9a-f-]{36}$/i.test(rawId) ? rawId : ''
    draftTitle.value = parsed.title || ''
    draftContent.value = parsed.content || ''
    mode.value = parsed.mode || 'novel'
    saveStatus.value = '已恢复本地草稿'
    dirty.value = false
  } catch {
    saveStatus.value = '草稿恢复失败'
  } finally {
    void nextTick(() => {
      suppressDirty.value = false
    })
  }
}

async function fetchDrafts() {
  const res = await api.get('/chat/studio/drafts/')
  const arr = Array.isArray(res.data) ? res.data : []
  drafts.value = arr.map((d: any) => ({
    id: String(d.id),
    title: d.title || '',
    content: d.content || '',
    mode: (d.mode || 'novel') as 'novel' | 'paper' | 'contract',
    updatedAt: d.updated_at || new Date().toISOString()
  }))
}

async function onRevisionDropdown(visible: boolean) {
  if (!visible || !currentDraftId.value) return
  try {
    const res = await api.get(`/chat/studio/drafts/${currentDraftId.value}/revisions/`)
    draftRevisions.value = Array.isArray(res.data) ? res.data : []
  } catch {
    draftRevisions.value = []
  }
}

function formatRevTime(iso: string) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  } catch {
    return iso
  }
}

async function confirmRestoreRevision(r: DraftRevisionRow) {
  try {
    await ElMessageBox.confirm(
      `将正文恢复为保存「v${r.revision_index}」时的快照（当前内容会先记入历史）。是否继续？`,
      '恢复历史版本',
      { type: 'warning', confirmButtonText: '恢复', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  if (!currentDraftId.value) return
  try {
    const res = await api.post(
      `/chat/studio/drafts/${currentDraftId.value}/revisions/${r.revision_index}/restore/`
    )
    const d = res.data
    draftTitle.value = d.title || ''
    draftContent.value = d.content || ''
    mode.value = (d.mode || 'novel') as 'novel' | 'paper' | 'contract'
    saveStatus.value = `已恢复到 v${r.revision_index}`
    await fetchDrafts()
    ElMessage.success('已恢复历史版本')
  } catch {
    ElMessage.error('恢复失败')
  }
}

function buildSnapshot(): DraftItem {
  return {
    id: currentDraftId.value || `d-${Date.now()}`,
    title: draftTitle.value,
    content: draftContent.value,
    mode: mode.value,
    updatedAt: new Date().toISOString()
  }
}

async function persistDraft(silent = false) {
  backupDraftLocal()
  if (!navigator.onLine) {
    saveStatus.value = '离线暂存（待联网后自动同步）'
    autosaveLabel.value = '离线'
    if (!silent) ElMessage.warning('当前离线，草稿已暂存到浏览器本地')
    return
  }
  if (persistInFlight) {
    persistQueued = true
    return
  }

  persistInFlight = true
  try {
    const snapshot = buildSnapshot()
    let lastErr: unknown = null
    for (let attempt = 0; attempt < MAX_SAVE_RETRIES; attempt += 1) {
      try {
        if (!currentDraftId.value) {
          // 首次保存：后端创建草稿并回填真实 id。
          const created = await api.post('/chat/studio/drafts/', {
            title: snapshot.title,
            content: snapshot.content,
            mode: snapshot.mode,
            path: `/drafts/${snapshot.title || 'untitled'}.md`
          })
          currentDraftId.value = String(created.data?.id || '')
        } else {
          try {
            await api.put(`/chat/studio/drafts/${currentDraftId.value}/`, {
              title: snapshot.title,
              content: snapshot.content,
              mode: snapshot.mode
            })
          } catch {
            // 兼容旧本地草稿 id 或已被删除的草稿：自动回退为新建。
            const created = await api.post('/chat/studio/drafts/', {
              title: snapshot.title,
              content: snapshot.content,
              mode: snapshot.mode,
              path: `/drafts/${snapshot.title || 'untitled'}.md`
            })
            currentDraftId.value = String(created.data?.id || '')
          }
        }
        await fetchDrafts()
        if (currentDraftId.value) broadcastDraftSavedRemote(currentDraftId.value)
        saveStatus.value = `已保存 ${new Date().toLocaleTimeString()}`
        autosaveLabel.value = '开启'
        dirty.value = false
        if (!silent) ElMessage.success('草稿已同步到云端')
        return
      } catch (err) {
        lastErr = err
        const delayMs = SAVE_RETRY_DELAYS_MS[Math.min(attempt, SAVE_RETRY_DELAYS_MS.length - 1)]
        autosaveLabel.value = `重试 ${attempt + 1}/${MAX_SAVE_RETRIES}`
        await new Promise((resolve) => setTimeout(resolve, delayMs))
      }
    }
    throw lastErr
  } catch {
    autosaveLabel.value = '失败（本地已保留）'
    saveStatus.value = '保存失败：已在本地暂存，稍后自动重试'
    if (!silent) ElMessage.warning('云端保存失败，草稿已保留在本地')
  } finally {
    persistInFlight = false
    if (persistQueued) {
      persistQueued = false
      void persistDraft(true)
    }
  }
}

async function saveDraft() {
  await persistDraft(false)
}

async function loadDraft(id: string) {
  const res = await api.get(`/chat/studio/drafts/${id}/`)
  const target = {
    id: String(res.data.id),
    title: res.data.title || '',
    content: res.data.content || '',
    mode: (res.data.mode || 'novel') as 'novel' | 'paper' | 'contract'
  }
  if (!target) return
  suppressDirty.value = true
  currentDraftId.value = target.id
  draftTitle.value = target.title
  draftContent.value = target.content
  mode.value = target.mode
  saveStatus.value = '已加载草稿'
  dirty.value = false
  backupDraftLocal()
  await nextTick()
  suppressDirty.value = false
}

function createNewDraft() {
  suppressDirty.value = true
  currentDraftId.value = ''
  draftTitle.value = ''
  draftContent.value = ''
  mode.value = 'novel'
  saveStatus.value = '新草稿'
  dirty.value = false
  backupDraftLocal()
  void nextTick(() => {
    suppressDirty.value = false
  })
}

async function removeDraft(id: string) {
  await api.delete(`/chat/studio/drafts/${id}/`)
  await fetchDrafts()
  if (currentDraftId.value === id) createNewDraft()
}

function startResize() {
  resizing = true
}

function onMouseMove(e: MouseEvent) {
  if (!resizing) return
  const w = window.innerWidth - e.clientX
  rightPaneWidth.value = Math.max(280, Math.min(620, w))
}

function stopResize() {
  resizing = false
}

async function loadKnowledgeBases() {
  const res = await api.get('/knowledge/knowledge-bases/')
  const arr = Array.isArray(res.data) ? res.data : res.data?.results || []
  knowledgeBases.value = arr.map((x: any) => ({ id: String(x.id), title: x.title }))
  if (knowledgeBases.value.length && !selectedKbId.value) {
    selectedKbId.value = knowledgeBases.value[0].id
  }
}

async function askStudio() {
  const q = studioQuestion.value.trim()
  if (!q) {
    ElMessage.info('请输入问题')
    return
  }
  if (!selectedKbId.value) {
    ElMessage.warning('请先选择知识库')
    return
  }
  asking.value = true
  const refsSnapshot: RefItem[] = selectedRefs.value.map((x) => ({
    type: x.type,
    id: x.value,
    label: x.label
  }))
  const userMsg: StudioMessage = { id: `u-${Date.now()}`, role: 'user', content: q, refs: refsSnapshot }
  studioMessages.value.push(userMsg)
  studioQuestion.value = ''
  try {
    // references 会透传到后端并参与编排（检索参数 + question hint）。
    const payload: Record<string, any> = {
      question: q,
      knowledge_base_id: selectedKbId.value,
      agent_id: currentMode.value === 'agent' ? modeAgentId.value : 'qa',
      use_agent: true,
      mode: mode.value,
      model: selectedModel.value,
      references: selectedRefs.value.map((x) => ({ type: x.type, id: x.value, label: x.label }))
    }
    if (studioSessionId.value) payload.session_id = studioSessionId.value
    const assistantId = `a-${Date.now()}`
    studioMessages.value.push({ id: assistantId, role: 'assistant', content: '', refs: refsSnapshot })
    const tryStream = async () => {
      const token = localStorage.getItem('access_token') || localStorage.getItem('access')
      const res = await fetch('/api/v1/chat/ask/stream/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify(payload)
      })
      if (!res.ok || !res.body) throw new Error('stream_not_available')
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        // SSE 以空行分块；保留尾部残片，避免 JSON 被截断导致解析失败。
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
              const msg = studioMessages.value.find((m) => m.id === assistantId)
              if (msg) msg.content += delta
            } catch {}
          }
          if (event === 'end' && data) {
            // 兜底：若未收到增量 chunk，用 end 事件里的 answer 回填完整答案。
            try {
              const parsed = JSON.parse(data)
              const msg = studioMessages.value.find((m) => m.id === assistantId)
              if (msg) msg.evolutionPath = String(parsed.evolution_path || '')
              if (msg && !msg.content) msg.content = String(parsed.answer || '')
            } catch {}
          }
        }
      }
    }
    try {
      await tryStream()
    } catch {
      // 流式不可用时自动降级到普通问答接口，保持用户链路可用。
      const res = await api.post('/chat/ask/', payload)
      const answer = res.data?.answer || '未返回答案'
      const msg = studioMessages.value.find((m) => m.id === assistantId)
      if (msg) {
        msg.content = answer
        msg.evolutionPath = String(res.data?.evolution_path || '')
      }
      if (res.data?.session_id) {
        studioSessionId.value = String(res.data.session_id)
        localStorage.setItem(STUDIO_SESSION_KEY, studioSessionId.value)
      }
    }
    await loadStudioSessions()
    selectedRefs.value = []
  } catch {
    ElMessage.error('工作室问答失败，请稍后重试')
      studioMessages.value.push({ id: `a-${Date.now()}`, role: 'assistant', content: '请求失败，请稍后重试。', refs: refsSnapshot })
  } finally {
    asking.value = false
  }
}

function buildMentionPool(): MentionItem[] {
  const fromDrafts: MentionItem[] = drafts.value.map((d) => ({
    key: `draft:${d.id}`,
    type: 'draft',
    label: d.title || '未命名草稿',
    value: d.id
  }))
  const fromKb: MentionItem[] = knowledgeBases.value.map((k) => ({
    key: `kb:${k.id}`,
    type: 'kb',
    label: k.title || '未命名知识库',
    value: k.id
  }))
  return [...fromDrafts, ...fromKb]
}

function onStudioInput(val: string) {
  const text = String(val || '')
  const m = /@([^\s@]*)$/.exec(text)
  if (!m) {
    mentionOpen.value = false
    mentionCandidates.value = []
    return
  }
  const kw = (m[1] || '').trim().toLowerCase()
  const pool = buildMentionPool()
  // mention 只做轻量前端筛选；最终合法性以后端 normalize_references 为准。
  mentionCandidates.value = pool
    .filter((x) => !kw || x.label.toLowerCase().includes(kw))
    .slice(0, 8)
  mentionOpen.value = true
}

function selectMention(item: MentionItem) {
  if (!selectedRefs.value.find((x) => x.key === item.key)) {
    selectedRefs.value.push(item)
  }
  studioQuestion.value = studioQuestion.value.replace(/@([^\s@]*)$/, '').trimEnd() + ' '
  mentionOpen.value = false
  mentionCandidates.value = []
}

function removeRef(key: string) {
  selectedRefs.value = selectedRefs.value.filter((x) => x.key !== key)
}

function renderMarkdown(text: string): string {
  return marked.parse(text || '') as string
}

function renderRefLabel(r: RefItem): string {
  return `${r.type === 'draft' ? '草稿' : '知识库'}: ${r.label || r.id}`
}

function renderEvolutionPath(path: string): string {
  return path === 'pro_sandbox' ? '本次进化链路：PRO 沙盒' : '本次进化链路：标准自进化'
}

function extractCodeBlocks(text: string): string[] {
  const src = String(text || '')
  const out: string[] = []
  const re = /```[a-zA-Z0-9_-]*\n([\s\S]*?)```/g
  let m: RegExpExecArray | null
  while ((m = re.exec(src)) !== null) {
    const body = (m[1] || '').trim()
    if (body) out.push(body)
  }
  return out
}

async function copyCode(code: string) {
  try {
    await navigator.clipboard.writeText(code)
    ElMessage.success('代码已复制')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

function applyToEditor(code: string) {
  const editorEl = draftEditorRef.value?.textarea
  const insertText = `${code}\n`
  if (!editorEl) {
    // textarea 未就绪时退化为尾部追加，保证功能不丢失。
    draftContent.value = `${draftContent.value}\n\n${code}`.trim()
    ElMessage.success('已应用到编辑区')
    return
  }
  const start = editorEl.selectionStart ?? draftContent.value.length
  const end = editorEl.selectionEnd ?? start
  const src = draftContent.value || ''
  draftContent.value = `${src.slice(0, start)}${insertText}${src.slice(end)}`
  // 恢复光标到插入文本之后
  requestAnimationFrame(() => {
    const p = start + insertText.length
    editorEl.focus()
    editorEl.setSelectionRange(p, p)
  })
  ElMessage.success('已应用到编辑区')
}

async function restoreStudioSession() {
  const sid = localStorage.getItem(STUDIO_SESSION_KEY) || ''
  if (!sid) return
  try {
    const res = await api.get(`/chat/sessions/${sid}/`)
    const msgs = Array.isArray(res.data?.messages) ? res.data.messages : []
    studioSessionId.value = sid
    studioMessages.value = msgs
      .filter((m: any) => m.message_type === 'user' || m.message_type === 'assistant')
      .map((m: any, i: number) => ({
        id: String(m.id || `${m.message_type}-${i}`),
        role: m.message_type === 'user' ? 'user' : 'assistant',
        content: m.message_type === 'user' ? (m.question || '') : (m.answer || '')
      }))
  } catch {
    studioSessionId.value = ''
    localStorage.removeItem(STUDIO_SESSION_KEY)
  }
}

function newStudioSession() {
  studioSessionId.value = ''
  studioMessages.value = []
  localStorage.removeItem(STUDIO_SESSION_KEY)
  broadcastStudioSessionsChanged()
}

async function loadStudioSessions() {
  try {
    const res = await api.get('/chat/sessions/')
    studioSessions.value = Array.isArray(res.data) ? res.data : []
  } catch {
    studioSessions.value = []
  }
}

async function switchStudioSession(id: string) {
  try {
    const res = await api.get(`/chat/sessions/${id}/`)
    const msgs = Array.isArray(res.data?.messages) ? res.data.messages : []
    studioSessionId.value = id
    localStorage.setItem(STUDIO_SESSION_KEY, id)
    studioMessages.value = msgs
      .filter((m: any) => m.message_type === 'user' || m.message_type === 'assistant')
      .map((m: any, i: number) => ({
        id: String(m.id || `${m.message_type}-${i}`),
        role: m.message_type === 'user' ? 'user' : 'assistant',
        content: m.message_type === 'user' ? (m.question || '') : (m.answer || '')
      }))
    broadcastStudioSessionsChanged()
  } catch {
    ElMessage.warning('加载历史会话失败')
  }
}

async function duplicateStudioSession(id: string) {
  try {
    const res = await api.post(`/chat/sessions/${id}/duplicate/`)
    await loadStudioSessions()
    broadcastStudioSessionsChanged()
    const sid = String(res.data?.session_id || '')
    if (sid) await switchStudioSession(sid)
  } catch {
    ElMessage.warning('复制会话失败')
  }
}

async function deleteStudioSession(id: string) {
  try {
    await api.delete(`/chat/sessions/${id}/delete/`)
    if (studioSessionId.value === id) newStudioSession()
    await loadStudioSessions()
    broadcastStudioSessionsChanged()
  } catch {
    ElMessage.warning('删除会话失败')
  }
}

onMounted(async () => {
  initStudioBroadcast()
  window.addEventListener('online', setOnlineFlag)
  window.addEventListener('offline', setOnlineFlag)
  setOnlineFlag()
  try {
    await api.get('/chat/studio/bootstrap/')
  } catch {
    ElMessage.warning('当前账号无 PRO 权限，已返回问答页')
    router.replace('/chat')
    return
  }
  const qMode = String(route.query.mode || '').toLowerCase()
  if (qMode === 'novel' || qMode === 'paper' || qMode === 'contract') {
    mode.value = qMode
  }
  await fetchDrafts()
  if (drafts.value[0]) {
    await loadDraft(drafts.value[0].id)
  } else {
    // 兼容旧版 localStorage 草稿：首次进入时导入一份到服务端
    const old = localStorage.getItem(DRAFT_KEY) || localStorage.getItem(DRAFT_LIST_KEY)
    if (old) {
      restoreDraft()
      await persistDraft(true)
      await fetchDrafts()
      if (drafts.value[0]) await loadDraft(drafts.value[0].id)
    } else {
      createNewDraft()
    }
  }
  await loadKnowledgeBases()
  await restoreStudioSession()
  await loadStudioSessions()
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', stopResize)
})

watch([draftTitle, draftContent, mode], () => {
  if (suppressDirty.value) return
  saveStatus.value = '编辑中（未保存）'
  dirty.value = true
  backupDraftLocal()
  if (autosaveTimer) clearTimeout(autosaveTimer)
  autosaveLabel.value = navigator.onLine ? '3 秒后保存' : '离线'
  // 统一走防抖自动保存，避免每次键入都触发后端写入。
  autosaveTimer = setTimeout(() => {
    void persistDraft(true)
  }, 3000)
})

watch(mode, (m) => {
  router.replace({
    query: {
      ...route.query,
      mode: m
    }
  })
})

onUnmounted(() => {
  if (autosaveTimer) clearTimeout(autosaveTimer)
  studioBroadcast?.close()
  studioBroadcast = null
  window.removeEventListener('online', setOnlineFlag)
  window.removeEventListener('offline', setOnlineFlag)
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', stopResize)
})
</script>

<style scoped>
.studio-page { height: 100vh; overflow: hidden; background: var(--apple-background); color: var(--apple-text-primary); display: flex; flex-direction: column; }
.titlebar { height: 44px; display: flex; align-items: center; justify-content: space-between; padding: 0 12px; background: var(--apple-surface); border-bottom: 1px solid var(--apple-border); }
.title-left { font-size: 13px; font-weight: 600; }
.title-right { display: flex; gap: 8px; align-items: center; }
.mode-select { width: 140px; }
.ide-shell { flex: 1; display: grid; grid-template-columns: 48px 240px 16px 1fr 6px 360px; min-height: 0; overflow: hidden; }
.activity-bar { background: #f2f4f7; border-right: 1px solid var(--apple-border); display: flex; flex-direction: column; align-items: center; padding-top: 10px; gap: 10px; }
.act { width: 28px; height: 28px; display: grid; place-items: center; border-radius: 6px; background: #e8edf3; color: #6a7280; font-size: 12px; }
.act.active { background: var(--apple-brand-blue); color: #fff; }
.explorer { background: #ffffff; border-right: 1px solid var(--apple-border); padding: 10px; overflow: auto; min-height: 0; }
.explorer-head { font-size: 11px; color: var(--apple-text-secondary); margin-bottom: 10px; letter-spacing: .08em; }
.explorer-toggle {
  background: #f7f8fa;
  border: none;
  border-right: 1px solid var(--apple-border);
  color: var(--apple-text-secondary);
  cursor: pointer;
  font-size: 11px;
}
.explorer-section { margin-bottom: 14px; }
.section-title { font-size: 12px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; color: var(--apple-text-primary); }
.draft-list { display: flex; flex-direction: column; gap: 6px; max-height: 220px; overflow: auto; }
.draft-item { text-align: left; border: 1px solid var(--apple-border); border-radius: 6px; padding: 7px; background: #fff; color: var(--apple-text-primary); display: flex; justify-content: space-between; cursor: pointer; }
.draft-item.active { border-color: var(--apple-brand-blue); background: rgba(30, 136, 229, 0.08); }
.draft-item-title { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px; }
.draft-delete { color: var(--apple-danger); font-size: 12px; }
.editor-pane { display: flex; flex-direction: column; min-width: 0; min-height: 0; background: #fff; overflow: hidden; }
.editor-tabs { height: 38px; display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 10px; background: #f7f9fc; border-bottom: 1px solid var(--apple-border); }
.tab-list { display: flex; gap: 6px; overflow: auto; }
.tab { background: #eef2f7; color: #5f6570; padding: 6px 10px; border-radius: 6px 6px 0 0; border: 1px solid var(--apple-border); border-bottom: none; font-size: 12px; cursor: pointer; white-space: nowrap; }
.tab.active { background: #fff; color: var(--apple-text-primary); border-color: #c9d4e0; }
.tab-meta { font-size: 12px; color: var(--apple-text-secondary); }
.editor-toolbar { padding: 8px 10px; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--apple-border); background: #fbfcfe; }
.draft-title { flex: 1; }
.editor-like { padding: 10px; flex: 1; min-height: 0; overflow: auto; }
.editor-like :deep(.el-textarea__inner) { background: #fff; color: #2d3748; border: 1px solid #d8e0ea; font-family: Menlo, Monaco, Consolas, "Courier New", monospace; line-height: 1.6; }
.right-resizer {
  cursor: col-resize;
  background: #edf1f6;
  border-left: 1px solid var(--apple-border);
  border-right: 1px solid var(--apple-border);
}
.assistant-pane { background: #f7f9fc; border-left: 1px solid var(--apple-border); display: grid; grid-template-rows: minmax(0, 1fr); gap: 8px; padding: 8px; min-height: 0; overflow: hidden; }
.assistant-card { background: #fff; border: 1px solid var(--apple-border); border-radius: 8px; padding: 8px; display: flex; flex-direction: column; gap: 8px; min-height: 0; overflow: hidden; }
.card-head { display: flex; justify-content: space-between; align-items: center; }
.card-head h3 { font-size: 13px; color: var(--apple-text-primary); margin: 0; }
.chat-header-left, .chat-header-right { display: flex; align-items: center; gap: 8px; }
.chat-model-select { width: 148px; }
.history-panel {
  max-height: 120px;
  overflow: auto;
  border: 1px solid var(--apple-border);
  border-radius: 6px;
  padding: 6px;
  background: #fff;
}
.history-item {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 6px 8px;
  background: #fff;
  cursor: pointer;
  margin-bottom: 6px;
}
.history-item.active {
  border-color: var(--apple-brand-blue);
  background: rgba(30, 136, 229, 0.08);
}
.history-title { display: block; font-size: 12px; color: var(--apple-text-primary); }
.history-time { display: block; font-size: 11px; color: var(--apple-text-secondary); margin-top: 2px; }
.history-actions { display: flex; gap: 4px; margin-top: 4px; }
.row { display: flex; gap: 8px; }
.mention-panel {
  border: 1px solid var(--apple-border);
  border-radius: 6px;
  background: #fff;
  max-height: 180px;
  overflow: auto;
}
.mention-item {
  width: 100%;
  text-align: left;
  padding: 7px 9px;
  border: none;
  border-bottom: 1px solid #eef2f7;
  background: #fff;
  cursor: pointer;
  display: flex;
  gap: 8px;
}
.mention-item:hover { background: #f6f9ff; }
.mention-type { font-size: 11px; color: var(--apple-text-secondary); min-width: 46px; }
.mention-label { font-size: 12px; color: var(--apple-text-primary); }
.selected-refs { display: flex; flex-wrap: wrap; gap: 6px; }
.ref-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--apple-border);
  border-radius: 999px;
  padding: 2px 8px;
  background: #f4f8ff;
  font-size: 11px;
}
.chip-remove {
  border: none;
  background: transparent;
  color: var(--apple-text-secondary);
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
}
.studio-answer { border: 1px solid var(--apple-border); border-radius: 6px; padding: 8px; background: #fff; overflow: auto; min-height: 120px; color: var(--apple-text-primary); }
.studio-answer { flex: 1; min-height: 0; }
.chat-item { border: 1px solid var(--apple-border); border-radius: 6px; padding: 6px 8px; margin-bottom: 8px; background: #fff; }
.chat-item-user { border-left: 3px solid var(--apple-brand-blue); }
.chat-item-assistant { border-left: 3px solid #7a8aa0; }
.chat-role { font-size: 11px; color: var(--apple-text-secondary); margin-bottom: 4px; }
.msg-evo {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--apple-border);
  border-radius: 999px;
  padding: 1px 7px;
  margin-bottom: 6px;
  font-size: 11px;
  color: #2563eb;
  background: #eff6ff;
}
.msg-refs { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
.msg-ref-chip {
  border: 1px solid var(--apple-border);
  border-radius: 999px;
  padding: 1px 7px;
  font-size: 11px;
  color: var(--apple-text-secondary);
  background: #f7f9fc;
}
.chat-content { font-size: 13px; line-height: 1.55; color: var(--apple-text-primary); }
.code-actions { margin-top: 8px; display: flex; flex-wrap: wrap; gap: 6px; }
.status-bar { height: 24px; background: var(--apple-brand-blue); color: #fff; display: flex; gap: 14px; align-items: center; padding: 0 10px; font-size: 11px; }
.offline-banner { color: #fff7d6; font-weight: 600; }
.muted { color: var(--apple-text-secondary); font-size: 12px; }
@media (max-width: 1400px) {
  .ide-shell { grid-template-columns: 48px 220px 16px 1fr 6px 320px; }
}
@media (max-width: 1100px) {
  .ide-shell { grid-template-columns: 1fr; }
  .activity-bar, .explorer { display: none; }
  .explorer-toggle, .right-resizer { display: none; }
  .assistant-pane { grid-template-rows: auto; }
}
</style>
