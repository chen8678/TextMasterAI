<template>
  <div class="cet-mock-exam">
    <el-header class="page-header">
      <el-button link @click="$router.push('/cet')">
        <AppleIcon name="arrow-left" :size="16" /> 返回学习中心
      </el-button>
      <h2>四级模拟考试</h2>
    </el-header>
    <el-main class="page-main">
      <!-- 创建考试 -->
      <el-card v-if="!mockExamId" shadow="hover">
        <template #header>四级模拟考试</template>
        <p class="hint">模考是能力快照：用来决定明天练什么。组卷含听力/阅读/词汇/语法/翻译/写作。</p>
        <el-button type="primary" :loading="createLoading" @click="createExam">
          开始四级模考
        </el-button>
      </el-card>

      <!-- 答题区 -->
      <template v-else>
        <div class="exam-toolbar">
          <span>共 {{ questions.length }} 题</span>
          <el-button type="primary" :loading="submitLoading" @click="submitExam">提交试卷</el-button>
        </div>
        <el-scrollbar height="520px">
          <div v-for="(q, i) in questions" :key="q.id" class="question-block">
            <p class="q-title">{{ i + 1 }}. {{ q.content }}</p>
            <ul v-if="q.options?.length" class="q-options">
              <li v-for="(opt, j) in q.options" :key="j">
                <el-radio v-model="answers[String(q.id)]" :label="String.fromCharCode(65 + j)">
                  {{ String.fromCharCode(65 + j) }}. {{ opt }}
                </el-radio>
              </li>
            </ul>
            <el-input v-else v-model="answers[String(q.id)]" type="textarea" :rows="2" placeholder="请输入答案" />
          </div>
        </el-scrollbar>
      </template>

      <!-- 提交结果 -->
      <el-card v-if="examResult" shadow="hover" class="mt-4">
        <template #header>能力快照（考完才是学习开始）</template>
        <p class="snapshot-lead">{{ snapshotTone }}</p>
        <p><strong>总分：{{ examResult.total_score }}</strong></p>
        <p>正确：{{ examResult.total_correct }} / {{ examResult.total_questions }}</p>
        <div v-if="examResult.section_scores">
          <p>各题型得分：</p>
          <ul>
            <li v-for="(v, k) in examResult.section_scores" :key="k">{{ typeLabel(String(k)) }}：{{ v }}</li>
          </ul>
        </div>
        <div v-if="examResult.radar_delta" class="radar-delta-box">
          <p><strong>相对考前的能力变化</strong></p>
          <p class="next-hint">{{ examResult.radar_delta.summary }}</p>
          <ul v-if="examResult.radar_delta.highlights?.length">
            <li v-for="h in examResult.radar_delta.highlights" :key="h.dimension">
              {{ h.label }}：
              <span :class="h.delta >= 0 ? 'up' : 'down'">
                {{ h.delta >= 0 ? '+' : '' }}{{ h.delta_percent_points }} 分点
              </span>
              （{{ Math.round((h.before || 0) * 100) }}% → {{ Math.round((h.after || 0) * 100) }}%）
            </li>
          </ul>
        </div>
        <p class="next-hint">下一步最小动作：先针对最弱题型练 8 题，再决定要不要立刻二刷整卷。</p>
        <div class="result-actions">
          <el-button type="primary" @click="goWeakPractice">针对弱项练一波</el-button>
          <el-button @click="$router.push('/cet/analysis')">看雷达复盘</el-button>
          <el-button text type="primary" @click="resetExam">再考一次</el-button>
        </div>
      </el-card>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import AppleIcon from '@/components/AppleIcon.vue'

const router = useRouter()

const createLoading = ref(false)
const submitLoading = ref(false)
const mockExamId = ref<number | null>(null)
const questions = ref<any[]>([])
const answers = reactive<Record<string, string>>({})
const examResult = ref<any>(null)

function typeLabel(k: string): string {
  const m: Record<string, string> = { listening: '听力', reading: '阅读', translation: '翻译', writing: '写作', vocabulary: '词汇', grammar: '语法' }
  return m[k] || k
}

const weakestType = computed(() => {
  const scores = examResult.value?.section_scores || {}
  const entries = Object.entries(scores) as [string, number][]
  if (!entries.length) return 'vocabulary'
  entries.sort((a, b) => Number(a[1]) - Number(b[1]))
  return entries[0][0]
})

const snapshotTone = computed(() => {
  const score = Number(examResult.value?.total_score ?? 0)
  if (score < 50) {
    return '这张快照在帮你定位，不是判决书。最有价值的是分项里最低的那一块。'
  }
  if (score < 75) {
    return '中段水平很常见：保持节奏，用弱项专项把分差补回来。'
  }
  return '快照不错。下一步用短练习巩固最弱项，避免「整卷再刷」的无效疲劳。'
})

function goWeakPractice() {
  router.push({ path: '/cet/practice', query: { type: weakestType.value, count: '8' } })
}

async function createExam() {
  createLoading.value = true
  mockExamId.value = null
  questions.value = []
  examResult.value = null
  Object.keys(answers).forEach((k) => delete answers[k])
  try {
    const res = await api.post('/cet/exam/create-mock/', { exam_type: 'cet4' })
    mockExamId.value = res.data.mock_exam_id
    questions.value = res.data.questions || []
    questions.value.forEach((q) => { answers[String(q.id)] = '' })
    ElMessage.success(`考试开始，共 ${questions.value.length} 题`)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '创建失败')
  } finally {
    createLoading.value = false
  }
}

async function submitExam() {
  if (!mockExamId.value) return
  submitLoading.value = true
  try {
    const res = await api.post(`/cet/exam/${mockExamId.value}/submit/`, { answers: { ...answers } })
    examResult.value = res.data
    ElMessage.success('提交成功')
    mockExamId.value = null
    questions.value = []
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '提交失败')
  } finally {
    submitLoading.value = false
  }
}

function resetExam() {
  examResult.value = null
}
</script>

<style scoped>
.cet-mock-exam { min-height: 100vh; background: #f5f5f7; }
.page-header { display: flex; align-items: center; gap: 16px; padding: 16px 24px; background: #fff; border-bottom: 1px solid #eee; }
.page-main { padding: 24px; }
.hint { font-size: 13px; color: #666; margin: 0 0 12px; }
.mt-4 { margin-top: 16px; }
.exam-toolbar { display: flex; justify-content: space-between; margin-bottom: 12px; }
.question-block { margin-bottom: 20px; padding: 12px; background: #fff; border-radius: 8px; }
.q-title { font-weight: 500; margin-bottom: 8px; }
.q-options { list-style: none; padding-left: 0; }
.snapshot-lead { font-size: 14px; color: #4b4b4b; line-height: 1.6; }
.next-hint { font-size: 13px; color: #6e6e73; margin-top: 8px; }
.result-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.radar-delta-box { margin-top: 12px; padding-top: 8px; border-top: 1px solid #eee; }
.radar-delta-box .up { color: #067d62; font-weight: 600; }
.radar-delta-box .down { color: #b42318; font-weight: 600; }
</style>
