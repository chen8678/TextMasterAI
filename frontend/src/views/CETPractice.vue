<template>
  <div class="cet-practice">
    <el-header class="practice-header">
      <div class="header-left">
        <AppleIcon name="list.bullet.rectangle" :size="22" />
        <div class="title-block">
          <h2>专项练习</h2>
          <p>四级题型训练：作答后提交，写入弱项与能力雷达</p>
        </div>
      </div>
      <div class="header-right">
        <el-tag size="small" type="success">大学英语四级</el-tag>
      </div>
    </el-header>

    <el-main class="practice-main">
      <el-row :gutter="20">
        <el-col :span="8">
          <el-card class="config-card" shadow="hover">
            <template #header>
              <span>练习配置</span>
            </template>
            <el-form label-width="80px" label-position="top">
              <el-form-item label="题型">
                <el-select v-model="questionType" placeholder="选择题型">
                  <el-option v-for="item in questionTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="难度（1-5，可选）">
                <el-slider v-model="difficulty" :min="1" :max="5" :show-tooltip="true" :marks="{1:'1',3:'3',5:'5'}" />
              </el-form-item>
              <el-form-item label="题目数量">
                <el-input-number v-model="count" :min="5" :max="30" />
              </el-form-item>
              <div class="form-actions">
                <el-button type="primary" :loading="loading" @click="generatePractice">
                  生成练习
                </el-button>
                <el-button @click="reset">重置</el-button>
              </div>
              <div class="weak-hint" v-if="Object.keys(weakPoints.weak_question_types).length">
                <p class="hint-title">根据当前弱项推荐：</p>
                <el-tag
                  v-for="(c, qtype) in weakPoints.weak_question_types"
                  :key="qtype"
                  class="weak-tag"
                  type="warning"
                  @click="questionType = String(qtype)"
                >
                  {{ typeLabel(String(qtype)) }} · 错{{ c }}次
                </el-tag>
              </div>
            </el-form>
          </el-card>
        </el-col>
        <el-col :span="16">
          <el-card class="questions-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <span>练习题目</span>
                <span class="sub-text">共 {{ questions.length }} 题</span>
              </div>
            </template>
            <div v-if="questions.length === 0" class="empty-state">
              <el-empty description="尚未生成练习。请在左侧配置条件后点击【生成练习】。" />
            </div>
            <template v-else>
              <el-scrollbar height="420px">
                <div
                  v-for="(q, index) in questions"
                  :key="q.id || index"
                  class="question-item"
                >
                  <div class="q-header">
                    <span class="q-index">第 {{ index + 1 }} 题 · {{ typeLabel(q.question_type) }}</span>
                    <el-tag size="small" effect="plain">难度 {{ q.difficulty }}</el-tag>
                  </div>
                  <p class="q-content">{{ q.content }}</p>
                  <div v-if="Array.isArray(q.options) && q.options.length" class="q-options">
                    <el-radio-group v-model="answers[String(q.id)]">
                      <el-radio
                        v-for="(opt, idx) in q.options"
                        :key="idx"
                        :label="String.fromCharCode(65 + idx)"
                        class="opt-radio"
                      >
                        {{ String.fromCharCode(65 + idx) }}. {{ opt }}
                      </el-radio>
                    </el-radio-group>
                  </div>
                  <el-input
                    v-else
                    v-model="answers[String(q.id)]"
                    type="textarea"
                    :rows="2"
                    placeholder="请输入你的答案"
                  />
                  <div v-if="resultMap[String(q.id)]" class="q-result">
                    <el-tag :type="resultMap[String(q.id)].is_correct ? 'success' : 'danger'" size="small">
                      {{ resultMap[String(q.id)].is_correct ? '正确' : '错误' }}
                    </el-tag>
                    <span v-if="resultMap[String(q.id)].correct_answer" class="ans">
                      参考答案：{{ resultMap[String(q.id)].correct_answer }}
                    </span>
                    <p v-if="resultMap[String(q.id)].explanation" class="exp">
                      {{ resultMap[String(q.id)].explanation }}
                    </p>
                  </div>
                  <el-divider />
                </div>
              </el-scrollbar>
              <div class="submit-bar">
                <el-button
                  type="primary"
                  :loading="submitLoading"
                  :disabled="!!submitResult"
                  @click="submitPractice"
                >
                  提交练习
                </el-button>
                <span v-if="submitResult" class="score-line">
                  正确 {{ submitResult.correct }} / {{ submitResult.total }}
                  （正确率 {{ Math.round((submitResult.accuracy || 0) * 100) }}%）
                </span>
              </div>
              <el-card v-if="submitResult" class="feedback-card" shadow="never">
                <h3>本轮三反馈</h3>
                <ol class="feedback-list">
                  <li>
                    <strong>结果：</strong>{{ feedbackSummary.scoreLine }}
                  </li>
                  <li>
                    <strong>为什么：</strong>{{ feedbackSummary.whyLine }}
                  </li>
                  <li>
                    <strong>可见变化：</strong>{{ feedbackSummary.changeLine }}
                  </li>
                </ol>
                <ul v-if="radarHighlights.length" class="radar-delta-list">
                  <li v-for="h in radarHighlights" :key="h.dimension">
                    <span>{{ h.label }}</span>
                    <span :class="h.delta >= 0 ? 'up' : 'down'">
                      {{ h.delta >= 0 ? '+' : '' }}{{ h.delta_percent_points }} 分点
                    </span>
                    <span class="muted">
                      {{ Math.round((h.before || 0) * 100) }}% → {{ Math.round((h.after || 0) * 100) }}%
                    </span>
                  </li>
                </ul>
                <p class="feedback-tone">{{ feedbackSummary.tone }}</p>
                <div class="feedback-actions">
                  <el-button type="primary" @click="$router.push('/cet/analysis')">去看雷达与弱项</el-button>
                  <el-button @click="$router.push('/cet')">回今日任务</el-button>
                  <el-button text type="primary" @click="reset">再选一组（自主）</el-button>
                </div>
              </el-card>
            </template>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import AppleIcon from '@/components/AppleIcon.vue'

const route = useRoute()
const questionType = ref<string>('vocabulary')
const difficulty = ref<number>(3)
const count = ref<number>(10)
const loading = ref(false)
const submitLoading = ref(false)

const questionTypeOptions = [
  { label: '听力', value: 'listening' },
  { label: '阅读', value: 'reading' },
  { label: '翻译', value: 'translation' },
  { label: '写作', value: 'writing' },
  { label: '词汇', value: 'vocabulary' },
  { label: '语法', value: 'grammar' }
]

const questions = ref<any[]>([])
const answers = reactive<Record<string, string>>({})
const resultMap = reactive<Record<string, any>>({})
const submitResult = ref<any>(null)
const weakPoints = ref<{
  weak_knowledge_points: string[]
  weak_question_types: Record<string, number>
}>({
  weak_knowledge_points: [],
  weak_question_types: {}
})

function typeLabel(qtype: string): string {
  const map: Record<string, string> = {
    listening: '听力',
    reading: '阅读',
    translation: '翻译',
    writing: '写作',
    vocabulary: '词汇',
    grammar: '语法'
  }
  return map[qtype] || qtype
}

const radarHighlights = computed(() => submitResult.value?.radar_delta?.highlights || [])

const feedbackSummary = computed(() => {
  const r = submitResult.value
  if (!r) {
    return { scoreLine: '', whyLine: '', changeLine: '', tone: '' }
  }
  const acc = Math.round((r.accuracy || 0) * 100)
  const wrong = (r.details || []).find((d: any) => !d.is_correct && d.explanation)
  const weakTypes = Object.keys(r.weak_points?.weak_question_types || {})
  const radarSummary = r.radar_delta?.summary || ''
  return {
    scoreLine: `答对 ${r.correct}/${r.total}，正确率 ${acc}%。`,
    whyLine: wrong?.explanation
      ? `先看这道错题：${wrong.explanation}`
      : (acc >= 80 ? '这一轮大多正确——巩固即可，不必加量硬刷。' : '错题里藏着下一步该练什么；翻上看解析即可。'),
    changeLine: radarSummary
      || (weakTypes.length
        ? `弱项已更新，当前更突出：${weakTypes.map((t) => typeLabel(t)).join('、')}。`
        : '样本还少，再完成一两轮后弱项会更清晰。'),
    tone: acc < 50
      ? '这一轮在帮你定位，不是在给你下判决。'
      : '有效练习已经完成：复盘比再空刷 50 题更重要。'
  }
})

async function loadWeakPoints() {
  try {
    const res = await api.get('/cet/weak-points/')
    const data = res.data || {}
    weakPoints.value = {
      weak_knowledge_points: data.weak_knowledge_points || [],
      weak_question_types: data.weak_question_types || {}
    }
  } catch {
    // ignore
  }
}

async function generatePractice() {
  if (!questionType.value) {
    ElMessage.warning('请选择题型')
    return
  }
  loading.value = true
  submitResult.value = null
  Object.keys(answers).forEach((k) => delete answers[k])
  Object.keys(resultMap).forEach((k) => delete resultMap[k])
  try {
    const res = await api.post('/cet/practice/', {
      question_type: questionType.value,
      difficulty: difficulty.value,
      count: count.value,
      exam_type: 'cet4'
    })
    questions.value = res.data?.questions || []
    questions.value.forEach((q) => {
      answers[String(q.id)] = ''
    })
    weakPoints.value = {
      weak_knowledge_points: res.data?.weak_points?.weak_knowledge_points || [],
      weak_question_types: res.data?.weak_points?.weak_question_types || {}
    }
    if (!questions.value.length) {
      ElMessage.info('未找到符合条件的题目，请先执行 seed_cet4 或调整难度')
    }
  } catch {
    ElMessage.error('生成练习失败')
  } finally {
    loading.value = false
  }
}

async function submitPractice() {
  if (!questions.value.length) return
  const payload: Record<string, string> = {}
  questions.value.forEach((q) => {
    payload[String(q.id)] = answers[String(q.id)] || ''
  })
  submitLoading.value = true
  try {
    const res = await api.post('/cet/practice/submit/', { answers: payload })
    submitResult.value = res.data
    ;(res.data?.details || []).forEach((d: any) => {
      resultMap[String(d.question_id)] = d
    })
    weakPoints.value = {
      weak_knowledge_points: res.data?.weak_points?.weak_knowledge_points || [],
      weak_question_types: res.data?.weak_points?.weak_question_types || {}
    }
    ElMessage.success('练习已提交，弱项与雷达已更新')
  } catch {
    ElMessage.error('提交失败')
  } finally {
    submitLoading.value = false
  }
}

function reset() {
  questionType.value = 'vocabulary'
  difficulty.value = 3
  count.value = 10
  questions.value = []
  submitResult.value = null
  Object.keys(answers).forEach((k) => delete answers[k])
  Object.keys(resultMap).forEach((k) => delete resultMap[k])
}

onMounted(async () => {
  const qType = route.query.type
  const qCount = route.query.count
  if (typeof qType === 'string' && qType) questionType.value = qType
  if (typeof qCount === 'string' && qCount) {
    const n = parseInt(qCount, 10)
    if (!Number.isNaN(n)) count.value = Math.min(30, Math.max(5, n))
  }
  await loadWeakPoints()
  if (route.query.type) {
    generatePractice()
  }
})
</script>

<style scoped>
.cet-practice {
  min-height: 100vh;
  background: #f5f5f7;
}

.practice-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 28px;
  background: #fff;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title-block h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.title-block p {
  margin: 0;
  font-size: 12px;
  color: #6e6e73;
}

.practice-main {
  padding: 20px 28px 28px;
}

.config-card,
.questions-card {
  border-radius: 18px;
}

.form-actions {
  display: flex;
  justify-content: flex-start;
  gap: 8px;
  margin-top: 4px;
}

.weak-hint {
  margin-top: 16px;
}

.hint-title {
  font-size: 12px;
  color: #6e6e73;
  margin-bottom: 4px;
}

.weak-tag {
  margin: 2px 4px 0 0;
  cursor: pointer;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sub-text {
  font-size: 12px;
  color: #6e6e73;
}

.empty-state {
  padding: 40px 0;
}

.question-item {
  padding: 10px 4px;
}

.q-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.q-index {
  font-weight: 500;
}

.q-content {
  font-size: 14px;
  line-height: 1.6;
  margin: 4px 0 6px;
}

.q-options {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.opt-radio {
  display: block;
  margin: 4px 0;
  height: auto;
  white-space: normal;
}

.q-result {
  margin-top: 8px;
  font-size: 13px;
}

.q-result .ans {
  margin-left: 8px;
  color: #6e6e73;
}

.q-result .exp {
  margin: 6px 0 0;
  color: #4b4b4b;
}

.submit-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 12px;
}

.score-line {
  font-size: 14px;
  font-weight: 600;
}

.feedback-card {
  margin-top: 16px;
  border-radius: 14px;
  background: #f8fafc;
  border: 1px solid rgba(0, 0, 0, 0.06);
}

.feedback-card h3 {
  margin: 0 0 8px;
  font-size: 15px;
}

.feedback-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.7;
  color: #333;
}

.feedback-tone {
  margin: 10px 0 12px;
  font-size: 13px;
  color: #6e6e73;
}

.feedback-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.radar-delta-list {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
  font-size: 13px;
}

.radar-delta-list li {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 4px 0;
}

.radar-delta-list .up { color: #067d62; font-weight: 600; }
.radar-delta-list .down { color: #b42318; font-weight: 600; }
.radar-delta-list .muted { color: #6e6e73; }
</style>
