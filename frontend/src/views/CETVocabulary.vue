<template>
  <div class="cet-vocabulary">
    <el-header class="page-header">
      <el-button link @click="$router.push('/cet')">
        <AppleIcon name="arrow-left" :size="16" /> 返回学习中心
      </el-button>
      <h2>四级词汇学习</h2>
    </el-header>
    <el-main class="page-main">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card shadow="hover">
            <template #header>创建 / 导入词汇本</template>
            <p class="lead">短间隔复习比一次硬背更有效。核心词高频出现在四级阅读与听力里。</p>
            <el-input v-model="wordInput" type="textarea" :rows="6" placeholder="每行一个单词，或逗号/空格分隔（也可先一键导入）" />
            <div class="actions mt-2">
              <el-button type="primary" :loading="createLoading" @click="createNotebook">
                创建自定义词汇本
              </el-button>
              <el-button :loading="importLoading" @click="importCore">
                一键导入四级核心词
              </el-button>
            </div>
          </el-card>

          <el-card shadow="hover" class="mt-4">
            <template #header>我的词汇本</template>
            <el-select v-model="selectedNotebookId" placeholder="选择词汇本" class="w-full" @change="loadReviewPlan">
              <el-option v-for="nb in notebooks" :key="nb.id" :label="nb.name" :value="nb.id" />
            </el-select>
            <div v-if="reviewPlan" class="review-plan mt-2">
              <p>词本共 {{ reviewPlan.total_words || 0 }} 词 · 待复习 {{ reviewPlan.pending_words || reviewPlan.review_words?.length || 0 }} · 已掌握 {{ reviewPlan.mastered_words || 0 }}</p>
            </div>
          </el-card>
        </el-col>

        <el-col :span="12">
          <el-card shadow="hover">
            <template #header>复习打卡（先想再看）</template>
            <div v-if="!currentWord" class="empty">
              <el-empty description="选择词汇本后开始；断了几天也没关系，从待复习列表接着即可。" />
            </div>
            <div v-else class="review-card">
              <p class="round-hint">建议本轮 10 词左右，认识与「还不熟」都算有效学习。</p>
              <h3 class="word">{{ currentWord.vocabulary }}</h3>
              <p v-if="showMeaning" class="meaning">{{ currentWord.meaning || '（暂无释义）' }}</p>
              <p v-if="showMeaning && currentWord.example_sentence" class="example">
                {{ currentWord.example_sentence }}
              </p>
              <div class="review-actions">
                <el-button v-if="!showMeaning" @click="showMeaning = true">我想起来了？先看释义</el-button>
                <template v-else>
                  <el-button type="success" :loading="reviewLoading" @click="mark(true)">认识</el-button>
                  <el-button type="warning" :loading="reviewLoading" @click="mark(false)">还不熟 · 稍后再见</el-button>
                </template>
              </div>
              <p class="progress">进度 {{ reviewIndex + 1 }} / {{ reviewQueue.length }}</p>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import AppleIcon from '@/components/AppleIcon.vue'

const wordInput = ref('')
const createLoading = ref(false)
const importLoading = ref(false)
const reviewLoading = ref(false)
const notebooks = ref<any[]>([])
const selectedNotebookId = ref<number | null>(null)
const reviewPlan = ref<any>(null)
const reviewQueue = ref<any[]>([])
const reviewIndex = ref(0)
const showMeaning = ref(false)

const currentWord = computed(() => reviewQueue.value[reviewIndex.value] || null)

function parseWords(s: string): string[] {
  const raw = s.replace(/,/g, ' ').split(/\s+/).map((w) => w.trim()).filter(Boolean)
  return [...new Set(raw)]
}

async function createNotebook() {
  const words = parseWords(wordInput.value)
  if (!words.length) {
    ElMessage.warning('请输入至少一个单词')
    return
  }
  createLoading.value = true
  try {
    const res = await api.post('/cet/vocabulary/notebooks/', { words, exam_type: 'cet4' })
    ElMessage.success('创建成功')
    await loadNotebooks()
    selectedNotebookId.value = res.data.id
    await loadReviewPlan()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '创建失败')
  } finally {
    createLoading.value = false
  }
}

async function importCore() {
  importLoading.value = true
  try {
    const res = await api.post('/cet/vocabulary/notebooks/import-core/', { limit: 120 })
    ElMessage.success('已导入四级核心词')
    await loadNotebooks()
    selectedNotebookId.value = res.data.id
    await loadReviewPlan()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '导入失败，请先 seed_cet4')
  } finally {
    importLoading.value = false
  }
}

async function loadReviewPlan() {
  showMeaning.value = false
  reviewIndex.value = 0
  reviewQueue.value = []
  if (!selectedNotebookId.value) {
    reviewPlan.value = null
    return
  }
  try {
    const res = await api.get(`/cet/vocabulary/notebooks/${selectedNotebookId.value}/review-plan/`)
    reviewPlan.value = res.data
    reviewQueue.value = res.data?.review_words || []
  } catch {
    reviewPlan.value = null
  }
}

async function mark(remembered: boolean) {
  if (!currentWord.value?.vocabulary_id) return
  reviewLoading.value = true
  try {
    await api.post('/cet/vocabulary/review/', {
      vocabulary_id: currentWord.value.vocabulary_id,
      remembered
    })
    showMeaning.value = false
    if (reviewIndex.value < reviewQueue.value.length - 1) {
      reviewIndex.value += 1
    } else {
      ElMessage.success('本轮复习完成')
      await loadReviewPlan()
    }
  } catch {
    ElMessage.error('打卡失败')
  } finally {
    reviewLoading.value = false
  }
}

async function loadNotebooks() {
  try {
    const res = await api.get('/cet/vocabulary/notebooks/list/')
    notebooks.value = res.data || []
  } catch {
    notebooks.value = []
  }
}

onMounted(loadNotebooks)
</script>

<style scoped>
.cet-vocabulary { min-height: 100vh; background: #f5f5f7; }
.page-header { display: flex; align-items: center; gap: 16px; padding: 16px 24px; background: #fff; border-bottom: 1px solid #eee; }
.page-main { padding: 24px; }
.w-full { width: 100%; }
.mt-2 { margin-top: 8px; }
.mt-4 { margin-top: 16px; }
.lead { font-size: 13px; color: #666; line-height: 1.55; margin: 0 0 10px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; }
.review-plan { font-size: 13px; color: #666; }
.review-card { text-align: center; padding: 24px 8px; }
.round-hint { font-size: 12px; color: #6e6e73; margin: 0 0 12px; }
.word { font-size: 32px; margin: 0 0 12px; }
.meaning { font-size: 16px; color: #333; }
.example { font-size: 13px; color: #666; font-style: italic; }
.review-actions { margin-top: 20px; display: flex; justify-content: center; gap: 12px; }
.progress { margin-top: 16px; font-size: 12px; color: #999; }
.empty { padding: 24px 0; }
</style>
