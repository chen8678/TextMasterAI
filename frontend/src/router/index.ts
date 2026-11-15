import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  ENABLE_BIM,
  ENABLE_CET,
  ENABLE_ENGLISH_LEARNING,
  ENABLE_PRO_STUDIO,
  ENABLE_SELF_EVOLUTION,
} from '@/config/featureFlags'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/Login.vue'),
      meta: { requiresAuth: false, title: '登录' }
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('@/views/Register.vue'),
      meta: { title: '注册' }
    },
    {
      path: '/',
      component: () => import('@/layouts/MainShell.vue'),
      children: [
        {
          path: '',
          name: 'home',
          component: () => import('@/views/Home.vue'),
          meta: { requiresAuth: false, title: '首页' }
        },
        {
          path: 'about',
          name: 'about',
          component: () => import('@/views/AboutProduct.vue'),
          meta: { requiresAuth: false, title: '关于' }
        },
        {
          path: 'chat',
          name: 'agent-chat',
          component: () => import('@/views/AgentChat.vue'),
          meta: { requiresAuth: true, title: '智能问答' }
        },
        {
          path: 'english-learning',
          name: 'english-learning-wizard',
          component: () => import('@/views/EnglishLearningWizard.vue'),
          meta: { requiresAuth: true, featureFlag: 'english_learning', title: '英语学习定制' }
        },
        {
          path: 'knowledge',
          name: 'knowledge',
          component: () => import('@/views/KnowledgeBase.vue'),
          meta: { requiresAuth: true, title: '知识库' }
        },
        {
          path: 'cet',
          name: 'cet-dashboard',
          component: () => import('@/views/CETDashboard.vue'),
          meta: { requiresAuth: true, featureFlag: 'cet', title: '四级学习中心' }
        },
        {
          path: 'cet/vocabulary',
          name: 'cet-vocabulary',
          component: () => import('@/views/CETVocabulary.vue'),
          meta: { requiresAuth: true, featureFlag: 'cet', title: '词汇学习' }
        },
        {
          path: 'cet/listening',
          name: 'cet-listening',
          component: () => import('@/views/CETListening.vue'),
          meta: { requiresAuth: true, featureFlag: 'cet', title: '听力训练' }
        },
        {
          path: 'cet/practice',
          name: 'cet-practice',
          component: () => import('@/views/CETPractice.vue'),
          meta: { requiresAuth: true, featureFlag: 'cet', title: '专项练习' }
        },
        {
          path: 'cet/writing',
          name: 'cet-writing',
          component: () => import('@/views/CETWriting.vue'),
          meta: { requiresAuth: true, featureFlag: 'cet', title: '写作批改' }
        },
        {
          path: 'cet/mock-exam',
          name: 'cet-mock-exam',
          component: () => import('@/views/CETMockExam.vue'),
          meta: { requiresAuth: true, featureFlag: 'cet', title: '模拟考试' }
        },
        {
          path: 'cet/analysis',
          name: 'cet-analysis',
          component: () => import('@/views/CETAnalysis.vue'),
          meta: { requiresAuth: true, featureFlag: 'cet', title: '学习分析' }
        },
        {
          path: 'bim',
          name: 'bim',
          component: () => import('@/views/BIMKnowledgeQA.vue'),
          meta: { requiresAuth: true, title: 'BIM 知识库' }
        },
        {
          path: 'writing/studio',
          name: 'writing-studio',
          component: () => import('@/views/WritingStudio.vue'),
          meta: { requiresAuth: true, requiresPro: true, title: '文字工作室' }
        },
        {
          path: 'admin',
          name: 'admin',
          component: () => import('@/views/Admin.vue'),
          meta: { requiresAuth: true, requiresAdmin: true, title: '管理' }
        },
        {
          path: 'admin/self-evolution',
          name: 'self-evolution',
          component: () => import('@/views/SelfEvolution.vue'),
          meta: { requiresAuth: true, requiresAdmin: true, featureFlag: 'self_evolution', title: '自进化管理' }
        },
        {
          path: 'admin/evolution-history',
          name: 'evolution-history',
          component: () => import('@/views/EvolutionHistory.vue'),
          meta: { requiresAuth: true, requiresAdmin: true, featureFlag: 'self_evolution', title: '进化历史' }
        }
      ]
    }
  ]
})

const BRAND = 'Text Master AI'

function featureEnabled(flag: unknown): boolean {
  if (flag === 'cet') return ENABLE_CET
  if (flag === 'english_learning') return ENABLE_ENGLISH_LEARNING
  if (flag === 'self_evolution') return ENABLE_SELF_EVOLUTION
  return true
}

router.afterEach((to) => {
  const piece = to.meta.title as string | undefined
  document.title = piece ? `${piece} · ${BRAND}` : BRAND
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  authStore.loadUser()

  const needsAuth = to.matched.some((r) => r.meta.requiresAuth === true)
  if (needsAuth && !authStore.isAuthenticated) {
    next({
      path: '/login',
      query: { redirect: to.fullPath }
    })
    return
  }

  const needsAdmin = to.matched.some((r) => r.meta.requiresAdmin === true)
  const isAdmin = !!(authStore.user?.is_staff || authStore.user?.is_superuser)
  if (needsAdmin && !isAdmin) {
    next({ path: '/' })
    return
  }

  const needsPro = to.matched.some((r) => r.meta.requiresPro === true)
  const isPro = !!authStore.user?.is_pro
  if (needsPro && !isPro) {
    next({ path: '/chat' })
    return
  }

  const isStudioRoute = to.matched.some((r) => r.name === 'writing-studio')
  if (isStudioRoute && !ENABLE_PRO_STUDIO) {
    next({ path: '/chat' })
    return
  }

  const isBimRoute = to.matched.some((r) => r.name === 'bim')
  if (isBimRoute && !ENABLE_BIM) {
    next({ path: '/' })
    return
  }

  const flag = to.matched.map((r) => r.meta.featureFlag).find((f) => f != null)
  if (flag != null && !featureEnabled(flag)) {
    next({ path: '/' })
    return
  }

  next()
})

export default router
