<template>
  <div class="cet-listening">
    <el-header class="page-header">
      <el-button link @click="$router.push('/cet')">
        <AppleIcon name="arrow-left" :size="16" /> 返回学习中心
      </el-button>
      <h2>四级听力训练</h2>
    </el-header>
    <el-main class="page-main">
      <el-card shadow="hover">
        <template #header>听力原文</template>
        <el-input v-model="transcript" type="textarea" :rows="8" placeholder="粘贴听力原文（中英文均可），点击【生成训练】获取摘要、关键词与练习题" />
        <div class="mt-2">
          <el-button type="primary" :loading="loading" :disabled="!transcript.trim()" @click="processTranscript">
            生成训练
          </el-button>
        </div>
      </el-card>
      <el-row v-if="result" :gutter="20" class="mt-4">
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>摘要</template>
            <p>{{ result.summary || '—' }}</p>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>关键词</template>
            <el-tag v-for="kw in (result.keywords || [])" :key="kw" class="mr-1 mb-1">{{ kw }}</el-tag>
          </el-card>
        </el-col>
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>练习题（{{ (result.questions || []).length }} 道）</template>
            <div v-for="(q, i) in (result.questions || [])" :key="i" class="q-item">
              <p><strong>{{ i + 1 }}. {{ q.question }}</strong></p>
              <p v-if="q.answer">答案：{{ q.answer }}</p>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import AppleIcon from '@/components/AppleIcon.vue'

const transcript = ref('')
const loading = ref(false)
const result = ref<any>(null)

async function processTranscript() {
  if (!transcript.value.trim()) return
  loading.value = true
  result.value = null
  try {
    const res = await api.post('/cet/listening/process/', { transcript: transcript.value.trim() })
    result.value = res.data
    ElMessage.success('处理完成')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.error || '处理失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {})
</script>

<style scoped>
.cet-listening { min-height: 100vh; background: #f5f5f7; }
.page-header { display: flex; align-items: center; gap: 16px; padding: 16px 24px; background: #fff; border-bottom: 1px solid #eee; }
.page-main { padding: 24px; }
.mt-2 { margin-top: 8px; }
.mt-4 { margin-top: 16px; }
.mr-1 { margin-right: 4px; }
.mb-1 { margin-bottom: 4px; }
.q-item { margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #eee; }
</style>
