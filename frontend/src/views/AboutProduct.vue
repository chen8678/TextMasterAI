<template>
  <div class="about-page">
    <header class="bar">
      <el-button text @click="router.push('/')">返回首页</el-button>
      <h1>关于 Text Master AI</h1>
      <span />
    </header>
    <main class="card">
      <h2>专注大学英语四级备考</h2>
      <p>
        Text Master AI 当前落地重点是<strong>大学英语四级</strong>：词汇、听力、阅读、写作与模考分析，配合备考资料知识库与智能答疑，形成可跟练的复习闭环。
      </p>
      <p>
        首发不展开通用文字工作室、多模态生成等能力；后续登录将支持手机验证码与微信扫码等方式，以降低学生使用门槛。
      </p>
      <p class="muted">四级学习中心入口：登录后访问「四级备考」。</p>
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<style scoped>
.about-page {
  min-height: 100vh;
  background: var(--apple-background);
  padding: 24px;
}
.bar {
  max-width: 640px;
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
  max-width: 640px;
  margin: 0 auto;
  padding: 28px;
  border-radius: var(--apple-card-radius);
  border: 1px solid var(--apple-border);
  background: var(--apple-surface);
  line-height: 1.75;
}
.card h2 {
  margin-bottom: 16px;
  font-size: 1.25rem;
}
.card p {
  margin-bottom: 12px;
  color: var(--text-100);
}
.muted {
  font-size: 0.9rem;
  color: var(--text-200);
}
</style>
