<template>
  <div class="main-shell" :class="{ 'main-shell--narrow': isNarrow }">
    <aside v-show="!isNarrow" class="shell-aside">
      <div class="shell-brand" @click="router.push('/')">
        <BrandMark :size="40" circular :padded="false" />
        <div class="shell-brand-text">
          <span class="shell-title">Text Master AI</span>
          <span class="shell-sub">文字工作台</span>
        </div>
      </div>
      <el-menu
        :default-active="activeMenu"
        class="shell-menu"
        router
        @select="onMenuSelect"
      >
        <el-menu-item v-for="item in visibleNavItems" :key="item.path" :index="item.path">
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
      <div class="shell-footer">
        <template v-if="authStore.isAuthenticated">
          <span class="shell-user">{{ authStore.user?.username }}</span>
          <el-button text type="primary" size="small" @click="logout">退出</el-button>
        </template>
        <template v-else>
          <el-button text type="primary" size="small" @click="router.push('/login')">登录</el-button>
          <el-button text size="small" @click="router.push('/register')">注册</el-button>
        </template>
      </div>
    </aside>

    <div v-show="isNarrow" class="shell-mobile-bar">
      <el-button text class="shell-menu-btn" aria-label="打开导航" @click="drawerVisible = true">
        <el-icon :size="22"><Menu /></el-icon>
      </el-button>
      <span class="shell-mobile-title" @click="router.push('/')">Text Master AI</span>
      <span class="shell-mobile-spacer" />
    </div>

    <el-drawer
      v-model="drawerVisible"
      direction="ltr"
      size="min(280px, 86vw)"
      class="shell-drawer"
      title="导航"
      :with-header="true"
      append-to-body
    >
      <el-menu
        :default-active="activeMenu"
        class="shell-menu shell-menu--drawer"
        router
        @select="onDrawerSelect"
      >
        <el-menu-item v-for="item in visibleNavItems" :key="'d-' + item.path" :index="item.path">
          <span>{{ item.label }}</span>
        </el-menu-item>
      </el-menu>
      <div class="shell-drawer-footer">
        <template v-if="authStore.isAuthenticated">
          <span class="shell-user">{{ authStore.user?.username }}</span>
          <el-button text type="primary" size="small" @click="logoutAndClose">退出</el-button>
        </template>
        <template v-else>
          <el-button text type="primary" size="small" @click="goLoginClose">登录</el-button>
          <el-button text size="small" @click="goRegisterClose">注册</el-button>
        </template>
      </div>
    </el-drawer>

    <div class="shell-body">
      <router-view />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Menu } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import BrandMark from '@/components/BrandMark.vue'
import {
  ENABLE_BIM,
  ENABLE_CET,
  ENABLE_ENGLISH_LEARNING,
  ENABLE_PRO_STUDIO,
  ENABLE_SELF_EVOLUTION,
} from '@/config/featureFlags'
import { menuExtras } from '@/adapters/menuExtras'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const drawerVisible = ref(false)
const isNarrow = ref(false)
let mq: MediaQueryList | null = null

const activeMenu = computed(() => route.path)

const navItems = computed(() => {
  const base = [
  { path: '/', label: '首页', show: true },
  { path: '/chat', label: '智能问答', show: authStore.isAuthenticated },
  {
    path: '/cet',
    label: '四级备考',
    show: !!(ENABLE_CET && authStore.isAuthenticated)
  },
  { path: '/bim', label: 'BIM', show: !!(ENABLE_BIM && authStore.isAuthenticated) },
  {
    path: '/english-learning',
    label: '英语学习',
    show: !!(ENABLE_ENGLISH_LEARNING && authStore.isAuthenticated)
  },
  { path: '/knowledge', label: '知识库', show: authStore.isAuthenticated },
  { path: '/about', label: '关于产品', show: true },
  {
    path: '/writing/studio',
    label: '文字工作室',
    // 前端特性开关关闭时，即使是 PRO 账号也不展示入口。
    show: !!(ENABLE_PRO_STUDIO && authStore.isAuthenticated && authStore.user?.is_pro)
  },
  {
    path: '/admin',
    label: '系统管理',
    show: !!(
      authStore.isAuthenticated &&
      (authStore.user?.is_staff || authStore.user?.is_superuser)
    )
  },
  {
    path: '/admin/self-evolution',
    label: '自进化管理',
    show: !!(
      ENABLE_SELF_EVOLUTION &&
      authStore.isAuthenticated &&
      (authStore.user?.is_staff || authStore.user?.is_superuser)
    )
  },
  {
    path: '/admin/evolution-history',
    label: '进化历史',
    show: !!(
      ENABLE_SELF_EVOLUTION &&
      authStore.isAuthenticated &&
      (authStore.user?.is_staff || authStore.user?.is_superuser)
    )
  }
  ]
  const extras = menuExtras.map((item) => {
    const staff = !!(authStore.user?.is_staff || authStore.user?.is_superuser)
    let show = true
    if (item.requiresAuth) show = show && authStore.isAuthenticated
    if (item.adminOnly) show = show && authStore.isAuthenticated && staff
    if (item.proOnly) show = show && !!(authStore.isAuthenticated && authStore.user?.is_pro)
    return { path: item.path, label: item.label, show }
  })
  return [...base, ...extras]
})

const visibleNavItems = computed(() => navItems.value.filter((i) => i.show))

const syncNarrow = () => {
  if (mq) isNarrow.value = mq.matches
}

onMounted(() => {
  mq = window.matchMedia('(max-width: 900px)')
  syncNarrow()
  mq.addEventListener('change', syncNarrow)
})

onUnmounted(() => {
  if (mq) mq.removeEventListener('change', syncNarrow)
})

const onMenuSelect = (index: string) => {
  if (index === route.path) return
}

const onDrawerSelect = () => {
  drawerVisible.value = false
}

const logout = () => {
  authStore.logout()
  router.push('/login')
}

const logoutAndClose = () => {
  drawerVisible.value = false
  logout()
}

const goLoginClose = () => {
  drawerVisible.value = false
  router.push('/login')
}

const goRegisterClose = () => {
  drawerVisible.value = false
  router.push('/register')
}
</script>

<style scoped>
.main-shell {
  display: flex;
  flex-direction: row;
  min-height: 100vh;
  background: var(--apple-background);
}
.main-shell--narrow {
  flex-direction: column;
}
.main-shell--narrow .shell-body {
  flex: 1;
  min-height: 0;
}
.shell-aside {
  width: 220px;
  flex-shrink: 0;
  border-right: 1px solid var(--apple-border);
  background: var(--apple-surface);
  display: flex;
  flex-direction: column;
  padding: 16px 0 12px;
}
.shell-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px 16px;
  cursor: pointer;
}
.shell-brand-text {
  display: flex;
  flex-direction: column;
  line-height: 1.2;
}
.shell-title {
  font-weight: 600;
  font-size: 0.95rem;
}
.shell-sub {
  font-size: 0.75rem;
  color: var(--apple-text-secondary);
}
.shell-menu {
  flex: 1;
  border-right: none;
  background: transparent;
}
.shell-menu--drawer {
  flex: none;
}
.shell-menu :deep(.el-menu-item) {
  border-radius: 10px;
  margin: 2px 8px;
}
.shell-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--apple-border);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.shell-user {
  font-size: 0.85rem;
  color: var(--apple-text-secondary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.shell-body {
  flex: 1;
  min-width: 0;
}
.shell-mobile-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--apple-border);
  background: var(--apple-surface);
  flex-shrink: 0;
}
.shell-menu-btn {
  padding: 4px 8px !important;
}
.shell-mobile-title {
  font-weight: 600;
  font-size: 0.95rem;
  cursor: pointer;
}
.shell-mobile-spacer {
  flex: 1;
}
.shell-drawer-footer {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--apple-border);
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
</style>

<style>
/* drawer 挂在 body 上，非 scoped */
.shell-drawer .el-drawer__body {
  padding: 12px 8px 24px;
  display: flex;
  flex-direction: column;
}
</style>
