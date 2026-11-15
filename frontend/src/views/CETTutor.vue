<template>
  <div class="cet-tutor">
    <el-header class="page-header">
      <el-button link @click="$router.push('/cet')">
        <AppleIcon name="arrow-left" :size="16" /> 返回学习中心
      </el-button>
      <h2>四级答疑（限轮）</h2>
      <el-tag type="info" effect="plain">
        {{ userTurnCount }} / {{ maxTurns }} 轮
      </el-tag>
    </el-header>

    <el-main class="page-main">
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="有预算的答疑：讲清考点后请去练题，而不是无限聊下去。"
        class="mb-3"
      />

      <el-card shadow="hover" class="chat-card">
        <div class="messages" ref="listRef">
          <div v-if="!messages.length" class="empty">
            可以问：某道阅读为什么错、某个词辨析、作文审题要点……
            <br />本轮最多 {{ maxTurns }} 次提问，结束后会引导你练 8 题。
          </div>
          <div
            v-for="(m, i) in messages"
            :key="i"
            class="msg"
            :class="m.role"
          >
            <div class="bubble">{{ m.text }}</div>
          </div>
        </div>

        <div v-if="sessionClosed && closer" class="closer-box">
          <p class="closer-summary">{{ closer.summary }}</p>
          <p v-if="closer.diagnosis_line" class="closer-diag">{{ closer.diagnosis_line }}</p>
          <div class="closer-actions">
            <el-button type="primary" @click="goPractice">{{ closer.cta }}</el-button>
            <el-button @click="resetSession">再开一轮（自主）</el-button>
            <el-button text type="primary" @click="$router.push('/cet')">回今日任务</el-button>
          </div>
        </div>

        <div class="composer" v-else>
          <el-input
            v-model="draft"
            type="textarea"
            :rows="3"
            :placeholder="`还剩 ${turnsRemaining} 次提问`"
            @keydown.enter.exact.prevent="send"
          />
          <div class="composer-actions">
            <span class="hint">Enter 发送 · 达上限将强制收束</span>
            <div>
              <el-button @click="forceClose" :disabled="!messages.length">结束并去练习</el-button>
              <el-button type="primary" :loading="loading" :disabled="!draft.trim()" @click="send">
                提问
              </el-button>
            </div>
          </div>
        </div>
      </el-card>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import AppleIcon from '@/components/AppleIcon.vue'

const router = useRouter()
const draft = ref('')
const loading = ref(false)
const listRef = ref<HTMLElement | null>(null)
const maxTurns = ref(6)
const userTurnCount = ref(0)
const turnsRemaining = ref(6)
const sessionClosed = ref(false)
const messages = ref<{ role: 'user' | 'assistant'; text: string }[]>([])
const closer = ref<{
  summary: string
  cta: string
  path: string
  query: Record<string, string>
  diagnosis_line?: string
} | null>(null)

async function scrollBottom() {
  await nextTick()
  const el = listRef.value
  if (el) el.scrollTop = el.scrollHeight
}

function goPractice() {
  if (!closer.value) return
  router.push({ path: closer.value.path, query: closer.value.query })
}

function resetSession() {
  userTurnCount.value = 0
  turnsRemaining.value = maxTurns.value
  sessionClosed.value = false
  closer.value = null
  messages.value = []
  draft.value = ''
}

async function forceClose() {
  // 用空预算触发服务端收束包（不增加有效问答内容）
  loading.value = true
  try {
    const res = await api.post('/cet/tutor/ask/', {
      message: '请结束本轮并给我练习建议',
      prior_user_turns: maxTurns.value,
      max_turns: maxTurns.value
    })
    const data = res.data || {}
    sessionClosed.value = true
    closer.value = data.closer || {
      summary: '本轮答疑到此结束。把刚弄清的点立刻练一遍，比继续聊更有效。',
      cta: '针对弱项练 8 题',
      path: '/cet/practice',
      query: { type: 'vocabulary', count: '8' }
    }
    turnsRemaining.value = 0
    userTurnCount.value = maxTurns.value
    messages.value.push({
      role: 'assistant',
      text: data.reply || closer.value.summary
    })
    await scrollBottom()
  } catch {
    ElMessage.error('结束会话失败')
  } finally {
    loading.value = false
  }
}

async function send() {
  const text = draft.value.trim()
  if (!text || loading.value || sessionClosed.value) return
  loading.value = true
  messages.value.push({ role: 'user', text })
  draft.value = ''
  await scrollBottom()
  try {
    const res = await api.post('/cet/tutor/ask/', {
      message: text,
      prior_user_turns: userTurnCount.value,
      max_turns: maxTurns.value
    })
    const data = res.data || {}
    userTurnCount.value = data.user_turn_count ?? userTurnCount.value + 1
    turnsRemaining.value = data.turns_remaining ?? Math.max(0, maxTurns.value - userTurnCount.value)
    maxTurns.value = data.max_turns || maxTurns.value
    messages.value.push({ role: 'assistant', text: data.reply || '（无回复）' })
    if (data.session_closed) {
      sessionClosed.value = true
      closer.value = data.closer
    }
    await scrollBottom()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '提问失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  turnsRemaining.value = maxTurns.value
})
</script>

<style scoped>
.cet-tutor { min-height: 100vh; background: #f5f5f7; }
.page-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #eee;
}
.page-header h2 { margin: 0; flex: 1; font-size: 18px; }
.page-main { padding: 24px; max-width: 840px; margin: 0 auto; }
.mb-3 { margin-bottom: 12px; }
.chat-card { border-radius: 14px; }
.messages {
  min-height: 280px;
  max-height: 48vh;
  overflow-y: auto;
  padding: 8px 4px 16px;
}
.empty { color: #6e6e73; font-size: 14px; line-height: 1.6; padding: 24px 8px; }
.msg { display: flex; margin-bottom: 10px; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble {
  max-width: 85%;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.55;
  white-space: pre-wrap;
}
.msg.user .bubble { background: #0a84ff; color: #fff; }
.msg.assistant .bubble { background: #f0f0f2; color: #1d1d1f; }
.composer-actions {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.hint { font-size: 12px; color: #6e6e73; }
.closer-box {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eee;
}
.closer-summary { margin: 0 0 6px; font-size: 14px; color: #1d1d1f; }
.closer-diag { margin: 0 0 12px; font-size: 13px; color: #0a84ff; }
.closer-actions { display: flex; flex-wrap: wrap; gap: 8px; }
</style>
