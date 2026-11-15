<template>
  <div class="admin-container">
    <el-header class="admin-header">
      <div class="header-content">
        <div class="logo">
          <h1>系统管理</h1>
        </div>
        <div class="header-actions">
          <el-button @click="goBack" type="info" size="large">
            <el-icon><ArrowLeft /></el-icon>
            返回首页
          </el-button>
          <el-dropdown @command="handleCommand">
            <el-button class="user-button">
              <el-icon><User /></el-icon>
              {{ authStore.user?.username }}
              <el-icon><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人中心</el-dropdown-item>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </el-header>

    <el-main class="admin-main">
      <PageScaffold>
        <template #toolbar>
          <AdminActionBar class="quick-actions-section">
            <div class="container">
              <div class="quick-actions">
                <el-button type="primary" @click="loadStats" :loading="loading">
                  <el-icon><Refresh /></el-icon>
                  刷新数据
                </el-button>
                <el-button type="info" @click="openDjangoAdmin">
                  <el-icon><Setting /></el-icon>
                  Django 后台
                </el-button>
              </div>
            </div>
          </AdminActionBar>
        </template>
        <PageSectionCard class="stats-section">
          <div class="container">
            <div class="section-title-row">
              <h2 class="section-title">数据概览</h2>
              <el-button v-if="authStore.user?.is_staff || authStore.user?.is_superuser" type="primary" link @click="router.push('/admin/self-evolution')">
                自进化管理（Skill / Agent）
              </el-button>
            </div>
            <p class="section-sub">数据来自 <code>GET /api/v1/system/stats/</code>（全站汇总）</p>

            <div class="stats-grid" v-loading="loading" v-if="stats">
              <div class="stat-item">
                <div class="stat-icon">
                  <el-icon size="24"><User /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-number">{{ stats.total_users ?? 0 }}</div>
                  <div class="stat-label">用户</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon">
                  <el-icon size="24"><FolderOpened /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-number">{{ stats.total_knowledge_bases ?? 0 }}</div>
                  <div class="stat-label">知识库</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon">
                  <el-icon size="24"><ChatDotRound /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-number">{{ stats.total_questions ?? 0 }}</div>
                  <div class="stat-label">问答次数</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon">
                  <el-icon size="24"><Cpu /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-number">{{ stats.agent_invocations ?? 0 }}</div>
                  <div class="stat-label">Agent 调用次数</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon">
                  <el-icon size="24"><MagicStick /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-number">{{ stats.skill_invocations ?? 0 }}</div>
                  <div class="stat-label">Skill 调用次数</div>
                </div>
              </div>
              <div class="stat-item">
                <div class="stat-icon">
                  <el-icon size="24"><Document /></el-icon>
                </div>
                <div class="stat-content">
                  <div class="stat-number">{{ stats.total_documents ?? 0 }}</div>
                  <div class="stat-label">文档总数</div>
                </div>
              </div>
            </div>
          </div>
        </PageSectionCard>
        <template #feedback>
          <el-empty v-if="!loading && !stats" description="暂无统计数据，可点击刷新重试" />
        </template>
      </PageScaffold>
    </el-main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import {
  User,
  Document,
  ChatDotRound,
  Setting,
  ArrowLeft,
  ArrowDown,
  Refresh,
  FolderOpened,
  MagicStick,
  Cpu
} from '@element-plus/icons-vue'
import api from '@/utils/api'
import PageScaffold from '@/components/templates/PageScaffold.vue'
import PageSectionCard from '@/components/templates/PageSectionCard.vue'
import AdminActionBar from '@/components/composite/AdminActionBar.vue'

interface AdminStats {
  total_users?: number
  total_knowledge_bases?: number
  total_questions?: number
  agent_invocations?: number
  skill_invocations?: number
  total_documents?: number
}

const router = useRouter()
const authStore = useAuthStore()

const loading = ref(false)
const stats = ref<AdminStats | null>(null)

const goBack = () => {
  router.push('/')
}

const loadStats = async () => {
  loading.value = true
  try {
    const { data } = await api.get<AdminStats>('/system/stats/')
    stats.value = data
  } catch (error) {
    console.error('加载统计数据失败:', error)
    ElMessage.error('加载统计数据失败')
  } finally {
    loading.value = false
  }
}

function djangoAdminBaseUrl(): string {
  const { protocol, hostname, port } = window.location
  if (port === '3009' || port === '5173') {
    return `${protocol}//${hostname}:8000`
  }
  if (port === '80' || port === '') {
    return `${protocol}//${hostname}:8000`
  }
  return `${protocol}//${hostname}:8000`
}

const openDjangoAdmin = () => {
  window.open(`${djangoAdminBaseUrl()}/admin/`, '_blank')
}

const handleCommand = (command: string) => {
  switch (command) {
    case 'profile':
      ElMessage.info('个人中心功能开发中...')
      break
    case 'logout':
      authStore.logout()
      router.push('/login')
      break
  }
}

onMounted(() => {
  loadStats()
})
</script>

<style scoped>
.admin-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
  position: relative;
  overflow: hidden;
}

.admin-container::before {
  content: '';
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 20% 80%, rgba(102, 126, 234, 0.1) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(118, 75, 162, 0.1) 0%, transparent 50%);
  pointer-events: none;
  z-index: 0;
}

.admin-header {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.1);
  padding: 0 2rem;
  height: 70px;
  display: flex;
  align-items: center;
  position: relative;
  z-index: 10;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
}

.logo h1 {
  font-size: 1.5rem;
  font-weight: 600;
  color: #2c3e50;
  margin: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.user-button {
  background: white;
  border: 1px solid #e1e5e9;
  border-radius: 10px;
  padding: 8px 16px;
  color: #2c3e50;
}

.admin-main {
  padding: 0;
  position: relative;
  z-index: 5;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 2rem;
}

.section-title-row {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 0.5rem;
}

.section-title-row .section-title {
  margin-bottom: 0;
}

.section-title {
  text-align: center;
  font-size: 2rem;
  font-weight: 700;
  color: #2c3e50;
  margin-bottom: 0.5rem;
}

.section-sub {
  text-align: center;
  color: #6c757d;
  font-size: 0.875rem;
  margin-bottom: 2rem;
}

.section-sub code {
  font-size: 0.8rem;
  background: rgba(102, 126, 234, 0.12);
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
}

.stats-section {
  padding: 3rem 2rem;
  background: white;
  margin: 2rem;
  border-radius: 16px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1.5rem;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1.25rem;
  border-radius: 14px;
  border: 1px solid #e9ecef;
  background: #fafbfc;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.stat-item:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.08);
}

.stat-icon {
  width: 48px;
  height: 48px;
  background: rgba(102, 126, 234, 0.15);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #667eea;
}

.stat-number {
  font-size: 1.75rem;
  font-weight: 700;
  color: #2c3e50;
  line-height: 1.2;
}

.stat-label {
  font-size: 0.9rem;
  color: #6c757d;
  margin-top: 0.2rem;
}

.quick-actions-section {
  padding: 2rem 2rem 3rem;
  margin: 0 2rem 2rem;
}

.quick-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .section-title {
    font-size: 1.65rem;
  }
}
</style>
