<template>
  <div class="login-container">
    <div class="background-decoration">
      <div class="floating-shape shape-1"></div>
      <div class="floating-shape shape-2"></div>
      <div class="floating-shape shape-3"></div>
      <div class="floating-shape shape-4"></div>
      <div class="floating-shape shape-5"></div>
    </div>

    <div class="login-content">
      <div class="unified-login-module">
        <div class="brand-section">
          <div class="brand-logo">
            <div class="logo-icon">
              <BrandMark :size="92" />
            </div>
            <h1 class="brand-title">Text Master AI</h1>
            <p class="brand-subtitle">大学英语四级备考 · 词汇听力阅读写作与模考闭环</p>
          </div>
          <div class="brand-features">
            <div class="feature-item">
              <AppleIcon name="document" :size="22" :stroke-width="1.75" />
              <span>四级题型专项训练</span>
            </div>
            <div class="feature-item">
              <AppleIcon name="doc-text" :size="22" :stroke-width="1.75" />
              <span>备考资料知识库</span>
            </div>
            <div class="feature-item">
              <AppleIcon name="sparkles" :size="22" :stroke-width="1.75" />
              <span>智能答疑与学情分析</span>
            </div>
          </div>
        </div>

        <!-- 传统账密登录暂下线；路由 /login 保留。以下为后续登录方式占位，尚未接通。 -->
        <div class="form-section">
          <el-card class="login-card">
            <div class="card-header">
              <h2>选择登录方式</h2>
              <p>传统账号密码已暂停；以下入口即将开放</p>
            </div>

            <div class="auth-slots">
              <div class="auth-slot auth-slot--phone" aria-disabled="true">
                <div class="slot-icon">
                  <AppleIcon name="person" :size="22" />
                </div>
                <div class="slot-body">
                  <h3>手机号验证码登录</h3>
                  <p>一键获取验证码，快速进入四级学习中心</p>
                </div>
                <el-tag size="small" type="info" effect="plain">即将开放</el-tag>
              </div>

              <div class="auth-slot auth-slot--wechat" aria-disabled="true">
                <div class="slot-icon slot-icon--wechat">
                  <AppleIcon name="chat" :size="22" />
                </div>
                <div class="slot-body">
                  <h3>微信扫码登录</h3>
                  <p>使用微信扫描二维码完成授权登录</p>
                </div>
                <el-tag size="small" type="info" effect="plain">即将开放</el-tag>
              </div>

              <div class="qr-placeholder" role="img" aria-label="微信扫码登录预留区域">
                <div class="qr-box">
                  <span class="qr-mark">QR</span>
                </div>
                <p class="qr-hint">扫码登录窗口预留 · 尚未接通微信开放平台</p>
              </div>
            </div>

            <div class="dev-bypass" v-if="showDevBypass">
              <el-button
                type="warning"
                plain
                class="bypass-button"
                :loading="bypassLoading"
                @click="enterWithoutLogin"
              >
                临时免登录进入（本地测试）
              </el-button>
              <p class="bypass-hint">仅开发调试：自动使用演示账号拿 token，正式登录接通后删除</p>
            </div>

            <div class="form-footer">
              <span class="register-text">需要先逛逛产品？</span>
              <el-button type="text" class="register-button" @click="goHome">
                返回首页
              </el-button>
            </div>
          </el-card>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import AppleIcon from '@/components/AppleIcon.vue'
import BrandMark from '@/components/BrandMark.vue'
import { useAuthStore } from '@/stores/auth'

/** 固定演示账号：仅本地临时免登录 */
const DEMO_USER = {
  username: 'cet_demo',
  email: 'cet_demo@example.com',
  password: 'CetDemo!Pass9',
  password_confirm: 'CetDemo!Pass9',
}

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const bypassLoading = ref(false)
const showDevBypass = import.meta.env.DEV

function safeRedirectAfterLogin(): string {
  const raw = route.query.redirect
  if (typeof raw !== 'string' || !raw.startsWith('/') || raw.startsWith('//')) {
    return '/cet'
  }
  return raw
}

const goHome = () => {
  router.push('/')
}

const enterWithoutLogin = async () => {
  bypassLoading.value = true
  try {
    try {
      await authStore.login({
        username: DEMO_USER.username,
        password: DEMO_USER.password,
      })
    } catch {
      await authStore.register({
        username: DEMO_USER.username,
        email: DEMO_USER.email,
        password: DEMO_USER.password,
        password_confirm: DEMO_USER.password_confirm,
      })
    }
    ElMessage.success('已用演示账号进入')
    router.push(safeRedirectAfterLogin())
  } catch {
    ElMessage.error('临时免登录失败：请确认后端已启动且允许本地注册')
  } finally {
    bypassLoading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  background: linear-gradient(135deg, #f6f9ff 0%, #eef3ff 35%, #ffffff 100%);
  position: relative;
  overflow: hidden;
  color: var(--apple-text-primary);
  font-family: 'SF Pro Display', 'Helvetica Neue', sans-serif;
}

.background-decoration {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.floating-shape {
  position: absolute;
  border-radius: 50%;
  background: rgba(10, 132, 255, 0.08);
  animation: float 6s ease-in-out infinite;
  filter: blur(25px);
}

.shape-1 { width: 260px; height: 260px; top: 8%; left: 12%; }
.shape-2 { width: 200px; height: 200px; top: 60%; right: 15%; animation-delay: 1s; background: rgba(191, 90, 242, 0.12); }
.shape-3 { width: 170px; height: 170px; bottom: 18%; left: 22%; animation-delay: 2s; background: rgba(255, 149, 0, 0.1); }
.shape-4 { width: 190px; height: 190px; top: 18%; right: 22%; animation-delay: .5s; }
.shape-5 { width: 130px; height: 130px; bottom: 30%; right: 8%; animation-delay: 1.5s; background: rgba(48, 209, 88, 0.1); }

@keyframes float {
  0%, 100% { transform: translate3d(0, 0, 0) scale(1); }
  50% { transform: translate3d(0, -30px, 0) scale(1.08); }
}

.login-content {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  position: relative;
  z-index: 1;
  padding: 24px;
}

.unified-login-module {
  width: 100%;
  max-width: 1080px;
  min-height: 600px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 32px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(25px);
  box-shadow: 0 35px 75px rgba(15, 23, 42, 0.12);
  display: flex;
  overflow: hidden;
}

.brand-section {
  flex: 1;
  padding: 56px 44px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  position: relative;
}

.brand-logo {
  position: relative;
  z-index: 1;
  margin-bottom: 48px;
}

.logo-icon {
  width: 92px;
  height: 92px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.logo-icon :deep(.brand-mark) {
  width: 100%;
  height: 100%;
}

.brand-title {
  font-size: 34px;
  font-weight: 700;
  margin: 0 0 16px;
  letter-spacing: 0.02em;
  color: var(--apple-text-primary);
}

.brand-subtitle {
  margin: 0;
  font-size: 18px;
  color: var(--apple-text-secondary);
  line-height: 1.6;
}

.brand-features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 18px;
  width: 100%;
  position: relative;
  z-index: 1;
}

.feature-item {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255, 255, 255, 0.95);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--apple-text-primary);
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.feature-item:hover {
  transform: translateY(-3px);
  border-color: rgba(10, 132, 255, 0.4);
}

.feature-item :deep(.apple-icon) {
  flex-shrink: 0;
  color: var(--primary-100, #ff5a5f);
  filter: drop-shadow(0 1px 2px rgba(255, 90, 95, 0.2));
}

.form-section {
  flex: 1;
  padding: 56px 44px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: rgba(255, 255, 255, 0.06);
}

.login-card {
  width: 100%;
  max-width: 420px;
  padding: 32px;
  border-radius: 28px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: #ffffff;
  box-shadow: 0 30px 60px rgba(15, 23, 42, 0.1);
}

.card-header {
  text-align: center;
  margin-bottom: 28px;
}

.card-header h2 {
  margin: 0 0 8px;
  font-size: 28px;
  font-weight: 600;
  color: var(--apple-text-primary);
}

.card-header p {
  margin: 0;
  color: var(--apple-text-secondary);
  font-size: 16px;
}

.auth-slots {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.auth-slot {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px dashed rgba(15, 23, 42, 0.18);
  background: rgba(246, 248, 255, 0.85);
  opacity: 0.92;
  cursor: not-allowed;
  user-select: none;
}

.slot-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(10, 132, 255, 0.1);
  color: #0a84ff;
  flex-shrink: 0;
}

.slot-icon--wechat {
  background: rgba(7, 193, 96, 0.12);
  color: #07c160;
}

.slot-body {
  flex: 1;
  min-width: 0;
  text-align: left;
}

.slot-body h3 {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--apple-text-primary);
}

.slot-body p {
  margin: 0;
  font-size: 13px;
  line-height: 1.45;
  color: var(--apple-text-secondary);
}

.qr-placeholder {
  margin-top: 4px;
  padding: 20px 16px;
  border-radius: 18px;
  border: 1px dashed rgba(15, 23, 42, 0.16);
  background: #fafbff;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.qr-box {
  width: 148px;
  height: 148px;
  border-radius: 12px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.06) 1px, transparent 1px) 0 0 / 12px 12px,
    linear-gradient(rgba(15, 23, 42, 0.06) 1px, transparent 1px) 0 0 / 12px 12px,
    #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}

.qr-mark {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: rgba(15, 23, 42, 0.35);
}

.qr-hint {
  margin: 0;
  font-size: 12px;
  color: var(--apple-text-secondary);
  text-align: center;
}

.dev-bypass {
  margin-top: 22px;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 8px;
}

.bypass-button {
  width: 100%;
  height: 44px;
  border-radius: 999px;
  font-weight: 600;
}

.bypass-hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.4;
  color: var(--apple-text-secondary);
  text-align: center;
}

.form-footer {
  margin-top: 28px;
  padding-top: 20px;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
  text-align: center;
}

.register-text {
  color: var(--apple-text-secondary);
  margin-right: 6px;
}

.register-button {
  color: var(--apple-brand-blue);
  font-weight: 600;
  border-radius: 999px;
  padding: 6px 18px;
}

.register-button:hover {
  background: rgba(10, 132, 255, 0.12);
}

@media (max-width: 900px) {
  .unified-login-module {
    flex-direction: column;
    max-width: 100%;
  }

  .brand-section,
  .form-section {
    padding: 40px 28px;
  }

  .login-content {
    padding: 16px;
  }
}
</style>
