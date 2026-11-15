<template>
  <div class="cet-dashboard">
    <el-header class="dashboard-header">
      <div class="header-left">
        <div class="logo-pill">
          <AppleIcon name="reading" :size="22" />
        </div>
        <div class="title-block">
          <h1>大学英语四级学习中心</h1>
          <p>能力雷达 · 弱项诊断 · 词汇/听力/练习/写作/模考闭环</p>
        </div>
      </div>
      <div class="header-right">
        <el-tag type="success" effect="plain">CET-4</el-tag>
        <el-button link type="primary" @click="$router.push('/knowledge')">知识库</el-button>
      </div>
    </el-header>

    <el-main class="dashboard-main">
      <el-card class="mission-card panel-card" shadow="hover" v-loading="snapLoading">
        <div class="mission-body">
          <div class="mission-copy">
            <p class="mission-eyebrow">今日 12 分钟 · 最小有效任务</p>
            <h2>{{ todayMission.title }}</h2>
            <p class="mission-diagnosis" @click="startMission">
              {{ todayMission.diagnosis_line || diagnosis.line }}
            </p>
            <div v-if="(todayMission.basis_tags || diagnosis.basis_tags || []).length" class="basis-tags">
              <el-tag
                v-for="tag in (todayMission.basis_tags || diagnosis.basis_tags)"
                :key="tag"
                size="small"
                effect="plain"
                class="basis-tag"
                @click="startMission"
              >
                {{ tag }}
              </el-tag>
            </div>
            <p class="mission-why">{{ todayMission.why }}</p>
            <p v-if="review.suggested_review_note" class="review-note">
              {{ review.suggested_review_note }}
              <span v-if="review.suggested_review_date" class="review-date">
                （{{ review.suggested_review_date }}）
              </span>
            </p>
          </div>
          <div class="mission-actions">
            <el-button type="primary" size="large" @click="startMission">
              {{ todayMission.cta }}
            </el-button>
            <el-button size="large" @click="swapMission">换一个</el-button>
            <el-button
              v-if="weakPractice.cta"
              size="large"
              plain
              @click="goWeakPractice"
            >
              {{ weakPractice.cta }}
            </el-button>
            <el-button text type="primary" @click="$router.push('/cet/tutor')">
              限轮答疑
            </el-button>
            <el-button text type="primary" @click="showAllPaths = !showAllPaths">
              {{ showAllPaths ? '收起自选' : '我自己选' }}
            </el-button>
          </div>
        </div>
        <div v-if="showAllPaths" class="actions mission-paths">
          <el-button type="primary" plain @click="$router.push('/cet/practice')">专项练习</el-button>
          <el-button plain @click="$router.push('/cet/vocabulary')">词汇学习</el-button>
          <el-button plain @click="$router.push('/cet/listening')">听力训练</el-button>
          <el-button plain @click="$router.push('/cet/writing')">写作批改</el-button>
          <el-button plain @click="$router.push('/cet/mock-exam')">模拟考试</el-button>
          <el-button plain @click="$router.push('/cet/analysis')">学习分析</el-button>
          <el-button plain @click="$router.push('/cet/tutor')">四级答疑（限轮）</el-button>
        </div>
      </el-card>

      <el-row :gutter="20">
        <el-col :span="10">
          <el-card class="panel-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <span>能力雷达图</span>
                <el-button text size="small" @click="loadSnapshot">
                  刷新
                </el-button>
              </div>
            </template>
            <div class="radar-wrapper" v-loading="snapLoading">
              <RadarChart :data="radarData" title="相对自己的能力快照" :max-value="100" />
            </div>
            <p class="radar-hint">数字对比的是「你自己的历史」，不是排行榜。</p>
          </el-card>
        </el-col>
        <el-col :span="14">
          <el-card class="panel-card" shadow="hover">
            <template #header>
              <div class="card-header">
                <span>弱项燃料（错题在帮你定位）</span>
                <el-button text size="small" @click="loadSnapshot">
                  刷新
                </el-button>
              </div>
            </template>
            <div class="weak-section" v-loading="snapLoading">
              <div class="weak-points">
                <h3>知识点弱项</h3>
                <div v-if="weakPoints.weak_knowledge_points.length === 0" class="empty-tip">
                  还没有错题燃料。先完成今日任务，我们再一起找弱项。
                </div>
                <el-tag
                  v-for="kp in weakPoints.weak_knowledge_points"
                  :key="kp"
                  type="warning"
                  class="weak-tag"
                >
                  {{ kp }}
                </el-tag>
              </div>
              <div class="weak-types">
                <h3>题型弱项</h3>
                <div v-if="Object.keys(weakPoints.weak_question_types).length === 0" class="empty-tip">
                  暂无题型统计——这不代表你弱，只代表样本还不够。
                </div>
                <div
                  v-for="(count, qtype) in weakPoints.weak_question_types"
                  :key="qtype"
                  class="type-row"
                >
                  <span class="type-label">{{ typeLabel(qtype) }}</span>
                  <el-progress :percentage="Math.min(100, count * 10)" :show-text="false" />
                  <span class="type-count">{{ count }} 次错误</span>
                </div>
              </div>
              <div class="review-stats" v-if="review.wrong_due_count || review.vocab_due_count">
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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import RadarChart from '@/components/RadarChart.vue'
import AppleIcon from '@/components/AppleIcon.vue'

const router = useRouter()
const snapLoading = ref(false)
const showAllPaths = ref(false)
const missionIndex = ref(0)

type Mission = {
  title: string
  why: string
  cta: string
  path: string
  query?: Record<string, string>
  diagnosis_line?: string
  basis_tags?: string[]
  kind?: string
}

const radarData = ref<{ name: string; value: number }[]>([
  { name: '听力', value: 0 },
  { name: '阅读', value: 0 },
  { name: '翻译', value: 0 },
  { name: '写作', value: 0 },
  { name: '词汇', value: 0 },
  { name: '语法', value: 0 }
])

const weakPoints = ref<{
  weak_knowledge_points: string[]
  weak_question_types: Record<string, number>
}>({
  weak_knowledge_points: [],
  weak_question_types: {}
})

const diagnosis = ref<{
  line: string
  basis_tags: string[]
  primary_type?: string | null
}>({
  line: '诊断依据：加载中…',
  basis_tags: []
})

const review = ref<{
  wrong_due_count: number
  vocab_due_count: number
  suggested_review_date: string
  suggested_review_note: string
}>({
  wrong_due_count: 0,
  vocab_due_count: 0,
  suggested_review_date: '',
  suggested_review_note: ''
})

const missions = ref<Mission[]>([])
const weakPractice = ref<{ cta: string; path: string; query: Record<string, string> }>({
  cta: '',
  path: '/cet/practice',
  query: { type: 'vocabulary', count: '8' }
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

const fallbackMissions: Mission[] = [
  {
    title: '热身：做 8 道四级词汇题',
    why: '还没有错题燃料。先用一小段提取练习热身，我们再一起找弱项。',
    diagnosis_line: '诊断依据：暂无错题样本——先用词汇热身定位。',
    basis_tags: ['样本不足'],
    cta: '开始词汇热身',
    path: '/cet/practice',
    query: { type: 'vocabulary', count: '8' }
  }
]

const todayMission = computed(() => {
  const pool = missions.value.length ? missions.value : fallbackMissions
  const m = pool[missionIndex.value % pool.length]
  return {
    ...m,
    basis_tags: m.basis_tags || diagnosis.value.basis_tags,
    diagnosis_line: m.diagnosis_line || diagnosis.value.line
  }
})

function startMission() {
  const m = todayMission.value
  router.push({ path: m.path, query: m.query })
}

function goWeakPractice() {
  router.push({ path: weakPractice.value.path, query: weakPractice.value.query })
}

function swapMission() {
  missionIndex.value += 1
}

async function loadSnapshot() {
  snapLoading.value = true
  try {
    const res = await api.get('/cet/analysis/learner-snapshot/')
    const data = res.data || {}
    const radar = data.radar || {}
    radarData.value = [
      { name: '听力', value: Math.round((radar.listening || 0) * 100) },
      { name: '阅读', value: Math.round((radar.reading || 0) * 100) },
      { name: '翻译', value: Math.round((radar.translation || 0) * 100) },
      { name: '写作', value: Math.round((radar.writing || 0) * 100) },
      { name: '词汇', value: Math.round((radar.vocabulary || 0) * 100) },
      { name: '语法', value: Math.round((radar.grammar || 0) * 100) }
    ]
    weakPoints.value = {
      weak_knowledge_points: data.weak_points?.weak_knowledge_points || [],
      weak_question_types: data.weak_points?.weak_question_types || {}
    }
    diagnosis.value = {
      line: data.diagnosis?.line || '诊断依据：暂无数据',
      basis_tags: data.diagnosis?.basis_tags || [],
      primary_type: data.diagnosis?.primary_type
    }
    review.value = {
      wrong_due_count: data.review?.wrong_due_count || 0,
      vocab_due_count: data.review?.vocab_due_count || 0,
      suggested_review_date: data.review?.suggested_review_date || '',
      suggested_review_note: data.review?.suggested_review_note || ''
    }
    const tags = data.diagnosis?.basis_tags || []
    missions.value = (data.today_missions || []).map((m: Mission) => ({
      ...m,
      basis_tags: tags,
      diagnosis_line: m.diagnosis_line || data.diagnosis?.line
    }))
    weakPractice.value = {
      cta: data.weak_practice?.cta || '',
      path: data.weak_practice?.path || '/cet/practice',
      query: data.weak_practice?.query || { type: 'vocabulary', count: '8' }
    }
    missionIndex.value = 0
  } catch {
    ElMessage.error('加载今日学习状态失败')
  } finally {
    snapLoading.value = false
  }
}

onMounted(loadSnapshot)
</script>

<style scoped>
.cet-dashboard {
  min-height: 100vh;
  background: radial-gradient(circle at top, #f5f7ff 0, #f9fafb 60%, #f5f5f7 100%);
}

.dashboard-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 32px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(12px);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.logo-pill {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0a84ff, #30d158);
  color: #fff;
}

.title-block h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.title-block p {
  margin: 2px 0 0;
  font-size: 13px;
  color: #6e6e73;
}

.dashboard-main {
  padding: 24px 32px 32px;
}

.mission-card {
  margin-bottom: 20px;
}

.mission-body {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
}

.mission-eyebrow {
  margin: 0 0 6px;
  font-size: 12px;
  color: #6e6e73;
}

.mission-copy h2 {
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.35;
}

.mission-diagnosis {
  margin: 0 0 8px;
  max-width: 560px;
  font-size: 13px;
  line-height: 1.5;
  color: #0a84ff;
  cursor: pointer;
}

.basis-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.basis-tag {
  cursor: pointer;
}

.mission-why {
  margin: 0;
  max-width: 560px;
  font-size: 14px;
  line-height: 1.6;
  color: #4b4b4b;
}

.review-note {
  margin: 8px 0 0;
  max-width: 560px;
  font-size: 12px;
  line-height: 1.5;
  color: #6e6e73;
}

.review-date {
  color: #1d1d1f;
}

.mission-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.mission-paths {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.radar-hint {
  margin: 8px 4px 0;
  font-size: 12px;
  color: #6e6e73;
}

.panel-card {
  border-radius: 18px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.radar-wrapper {
  height: 360px;
}

.weak-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.weak-points,
.weak-types {
  padding-bottom: 4px;
}

.weak-tag {
  margin: 4px 4px 0 0;
}

.type-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.type-label {
  min-width: 56px;
  font-size: 13px;
  color: #1d1d1f;
}

.type-count {
  font-size: 12px;
  color: #6e6e73;
}

.review-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: #6e6e73;
}

.empty-tip {
  font-size: 13px;
  color: #a1a1a6;
}

.actions {
  display: flex;
  gap: 12px;
  margin-top: 4px;
}
</style>
