<template>
  <div class="cet-analysis">
    <el-header class="page-header">
      <el-button link @click="$router.push('/cet')">
        <AppleIcon name="arrow-left" :size="16" /> 返回学习中心
      </el-button>
      <h2>四级学习分析</h2>
    </el-header>
    <el-main class="page-main">
      <el-card class="action-card" shadow="never" v-loading="loading">
        <p class="diagnosis">{{ diagnosis.line }}</p>
        <p v-if="review.suggested_review_note" class="review-note">
          {{ review.suggested_review_note }}
          <span v-if="review.suggested_review_date">（{{ review.suggested_review_date }}）</span>
        </p>
        <div class="actions">
          <el-button type="primary" @click="goWeakPractice">
            {{ weakPractice.cta || '针对弱项练 8 题' }}
          </el-button>
          <el-button @click="$router.push('/cet/vocabulary')">去词汇复习</el-button>
          <el-button text type="primary" @click="$router.push('/cet')">回今日任务</el-button>
        </div>
      </el-card>
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header>能力雷达图</template>
            <div class="radar-box" v-loading="loading">
              <RadarChart :data="radarData" title="听说读写与词汇语法" :max-value="100" />
            </div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header>弱项分析</template>
            <div v-loading="loading">
              <p><strong>知识点弱项</strong></p>
              <el-tag v-for="kp in weakPoints.weak_knowledge_points" :key="kp" type="warning" class="mr-1 mb-1">{{ kp }}</el-tag>
              <p v-if="!weakPoints.weak_knowledge_points?.length" class="empty">暂无</p>
              <p class="mt-2"><strong>题型弱项</strong></p>
              <div v-for="(cnt, t) in (weakPoints.weak_question_types || {})" :key="t" class="type-row">
                {{ typeLabel(t) }}：错 {{ cnt }} 次
              </div>
              <p v-if="!Object.keys(weakPoints.weak_question_types || {}).length" class="empty">暂无</p>
              <div class="due-row" v-if="review.wrong_due_count || review.vocab_due_count">
                <span v-if="review.wrong_due_count">到期错题 {{ review.wrong_due_count }}</span>
                <span v-if="review.vocab_due_count">到期词汇 {{ review.vocab_due_count }}</span>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import AppleIcon from '@/components/AppleIcon.vue'
import RadarChart from '@/components/RadarChart.vue'

const router = useRouter()
const loading = ref(false)
const radarData = ref<{ name: string; value: number }[]>([
  { name: '听力', value: 0 },
  { name: '阅读', value: 0 },
  { name: '翻译', value: 0 },
  { name: '写作', value: 0 },
  { name: '词汇', value: 0 },
  { name: '语法', value: 0 }
])
const weakPoints = ref<{ weak_knowledge_points: string[]; weak_question_types: Record<string, number> }>({
  weak_knowledge_points: [],
  weak_question_types: {}
})
const diagnosis = ref({ line: '诊断依据：加载中…' })
const review = ref({
  wrong_due_count: 0,
  vocab_due_count: 0,
  suggested_review_date: '',
  suggested_review_note: ''
})
const weakPractice = ref<{ cta: string; path: string; query: Record<string, string> }>({
  cta: '针对弱项练 8 题',
  path: '/cet/practice',
  query: { type: 'vocabulary', count: '8' }
})

function typeLabel(t: string): string {
  const m: Record<string, string> = { listening: '听力', reading: '阅读', translation: '翻译', writing: '写作', vocabulary: '词汇', grammar: '语法' }
  return m[t] || t
}

function goWeakPractice() {
  router.push({ path: weakPractice.value.path, query: weakPractice.value.query })
}

async function load() {
  loading.value = true
  try {
    const res = await api.get('/cet/analysis/learner-snapshot/')
    const data = res.data || {}
    const d = data.radar || {}
    radarData.value = [
      { name: '听力', value: Math.round((d.listening || 0) * 100) },
      { name: '阅读', value: Math.round((d.reading || 0) * 100) },
      { name: '翻译', value: Math.round((d.translation || 0) * 100) },
      { name: '写作', value: Math.round((d.writing || 0) * 100) },
      { name: '词汇', value: Math.round((d.vocabulary || 0) * 100) },
      { name: '语法', value: Math.round((d.grammar || 0) * 100) }
    ]
    weakPoints.value = {
      weak_knowledge_points: data.weak_points?.weak_knowledge_points || [],
      weak_question_types: data.weak_points?.weak_question_types || {}
    }
    diagnosis.value = { line: data.diagnosis?.line || '诊断依据：暂无数据' }
    review.value = {
      wrong_due_count: data.review?.wrong_due_count || 0,
      vocab_due_count: data.review?.vocab_due_count || 0,
      suggested_review_date: data.review?.suggested_review_date || '',
      suggested_review_note: data.review?.suggested_review_note || ''
    }
    weakPractice.value = {
      cta: data.weak_practice?.cta || '针对弱项练 8 题',
      path: data.weak_practice?.path || '/cet/practice',
      query: data.weak_practice?.query || { type: 'vocabulary', count: '8' }
    }
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.cet-analysis { min-height: 100vh; background: #f5f5f7; }
.page-header { display: flex; align-items: center; gap: 16px; padding: 16px 24px; background: #fff; border-bottom: 1px solid #eee; }
.page-main { padding: 24px; }
.action-card { margin-bottom: 16px; border-radius: 12px; }
.diagnosis { margin: 0 0 8px; font-size: 14px; color: #0a84ff; line-height: 1.5; }
.review-note { margin: 0 0 12px; font-size: 13px; color: #6e6e73; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; }
.radar-box { height: 360px; }
.mr-1 { margin-right: 4px; }
.mb-1 { margin-bottom: 4px; }
.mt-2 { margin-top: 8px; }
.type-row { margin: 4px 0; }
.due-row { margin-top: 12px; display: flex; gap: 12px; font-size: 12px; color: #6e6e73; }
.empty { color: #999; font-size: 13px; }
</style>
