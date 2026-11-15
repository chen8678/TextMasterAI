<template>
  <div class="cet-writing">
    <el-header class="page-header">
      <el-button link @click="$router.push('/cet')">
        <AppleIcon name="arrow-left" :size="16" /> 返回学习中心
      </el-button>
      <h2>四级写作 / 翻译批改</h2>
    </el-header>
    <el-main class="page-main">
      <el-row :gutter="20">
        <el-col :span="10">
          <el-card shadow="hover">
            <template #header>选择题目</template>
            <el-select v-model="selectedQuestionId" placeholder="选择题型后加载题目" class="w-full" filterable>
              <el-option
                v-for="q in writingQuestions"
                :key="q.id"
                :label="`${q.question_type} - Q${q.question_number}`"
                :value="q.id"
              />
            </el-select>
            <div v-if="selectedQuestion" class="q-preview mt-2">
              <p class="q-content">{{ selectedQuestion.content }}</p>
            </div>
          </el-card>
        </el-col>
        <el-col :span="14">
          <el-card shadow="hover">
            <template #header>您的作文/翻译</template>
            <el-input v-model="content" type="textarea" :rows="12" placeholder="在此输入您的作文或翻译内容..." />
            <div class="mt-2">
              <el-button type="primary" :loading="loading" :disabled="!selectedQuestionId || !content.trim()" @click="submitGrade">
                提交批改
              </el-button>
            </div>
          </el-card>
          <el-card v-if="gradeResult" shadow="hover" class="mt-4">
            <template #header>批改结果</template>
            <div class="grade-result">
              <p class="total-score">总分：{{ gradeResult.total_score ?? '—' }}</p>
              <p v-if="gradeResult.evidence_line" class="evidence">{{ gradeResult.evidence_line }}</p>
              <div v-if="gradeResult.scores && Object.keys(gradeResult.scores).length" class="scores">
                <p v-for="(v, k) in gradeResult.scores" :key="k">{{ k }}：{{ v ?? '—' }}</p>
              </div>
              <p v-if="gradeResult.feedback" class="feedback">{{ gradeResult.feedback }}</p>
              <ul v-if="gradeResult.suggestions?.length">
                <li v-for="(s, i) in gradeResult.suggestions" :key="i">{{ s }}</li>
              </ul>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import AppleIcon from '@/components/AppleIcon.vue'

const writingQuestions = ref<any[]>([])
const selectedQuestionId = ref<number | null>(null)
const content = ref('')
const loading = ref(false)
const gradeResult = ref<any>(null)

const selectedQuestion = computed(() =>
  writingQuestions.value.find((q) => q.id === selectedQuestionId.value)
)

async function loadQuestions() {
  try {
    const res = await api.get('/cet/questions/', { params: { question_type: 'writing', limit: 50 } })
    writingQuestions.value = res.data || []
    if (writingQuestions.value.length && !selectedQuestionId.value) {
      selectedQuestionId.value = writingQuestions.value[0].id
    }
  } catch {
    ElMessage.error('加载题目失败')
  }
}

watch(selectedQuestionId, () => { gradeResult.value = null })

async function submitGrade() {
  if (!selectedQuestionId.value || !content.value.trim()) return
  loading.value = true
  gradeResult.value = null
  try {
    const res = await api.post('/cet/writing/grade/', {
      question_id: selectedQuestionId.value,
      content: content.value.trim()
    })
    gradeResult.value = res.data
    ElMessage.success('批改完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '批改失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadQuestions)
</script>

<style scoped>
.cet-writing { min-height: 100vh; background: #f5f5f7; }
.page-header { display: flex; align-items: center; gap: 16px; padding: 16px 24px; background: #fff; border-bottom: 1px solid #eee; }
.page-main { padding: 24px; }
.w-full { width: 100%; }
.mt-2 { margin-top: 8px; }
.mt-4 { margin-top: 16px; }
.q-content { font-size: 14px; line-height: 1.6; white-space: pre-wrap; }
.grade-result .total-score { font-weight: 600; font-size: 16px; }
.grade-result .evidence {
  margin: 8px 0;
  padding: 8px 10px;
  font-size: 13px;
  line-height: 1.5;
  color: #4b4b4b;
  background: #f5f5f7;
  border-radius: 8px;
}
.grade-result .scores p { margin: 4px 0; }
.grade-result .feedback { margin-top: 8px; line-height: 1.6; }
</style>
