<template>
  <div class="studio-placeholder">
    <header class="bar">
      <el-button text @click="router.push('/chat')">
        <el-icon><ArrowLeft /></el-icon>
        返回问答
      </el-button>
      <h1>文字工作室</h1>
      <span />
    </header>
    <main class="card">
      <h2>Text Master AI · 私人文字工作台</h2>
      <p class="lead">
        多窗口协同写作、知识库联动与沙盒自进化为后续能力，首发以免费问答与知识库为主。
      </p>
      <p class="hint">当前为免费版。工作室完整能力尚未对公众开放。</p>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const router = useRouter()
const authStore = useAuthStore()

onMounted(async () => {
  if (!authStore.user?.is_pro) return
  try {
    await api.get('/chat/studio/bootstrap/')
  } catch {
    ElMessage.warning('工作室服务暂不可用，请稍后重试。')
  }
})
</script>

<style scoped>
.studio-placeholder {
  min-height: 100vh;
  background: var(--apple-background);
  padding: 24px;
}
.bar {
  max-width: 720px;
  margin: 0 auto 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.bar h1 {
  font-size: 1.1rem;
  font-weight: 600;
}
.card {
  max-width: 720px;
  margin: 0 auto;
  padding: 32px;
  border-radius: var(--apple-card-radius);
  border: 1px solid var(--apple-border);
  background: var(--apple-surface);
}
.lead {
  margin-top: 16px;
  color: var(--apple-text-secondary);
  line-height: 1.7;
}
.hint {
  margin-top: 20px;
  padding: 12px 16px;
  border-radius: 12px;
  background: rgba(255, 90, 95, 0.08);
  color: var(--text-200);
}
.hint.ok {
  background: rgba(0, 166, 153, 0.1);
}
</style>
