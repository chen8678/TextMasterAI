<template>
  <div class="page skills-page">
    <header class="page-header apple-card">
      <div class="header-left">
        <div class="logo-pill">
          <AppleIcon name="sparkles" :size="20" />
        </div>
        <div>
          <h1>能力说明</h1>
          <p>系统内置多种文件处理、知识检索和自动生成能力，由后端预先编排，用户开箱即用。</p>
        </div>
      </div>
    </header>

    <main class="page-main">
      <section class="apple-card">
        <h2 class="sub-title">我们帮你做的事情</h2>
        <ul class="capability-list">
          <li>读取并解析本地或上传的文档，整理为可检索的知识片段。</li>
          <li>在私有知识库上执行增强检索，给出带有出处的回答。</li>
          <li>根据对话与文档自动生成摘要、会议纪要和报告草稿。</li>
        </ul>
        <p class="muted">所有底层能力均由后台安全托管，页面仅作能力说明，无需人工配置。</p>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import AppleIcon from '@/components/AppleIcon.vue'
</script>

<style scoped>
.page {
  min-height: 100vh;
  background: var(--bg-100);
  padding: 24px 40px 40px;
  box-sizing: border-box;
}

.apple-card {
  background: var(--bg-200);
  border-radius: var(--apple-radius-lg);
  border: 1px solid var(--apple-border);
  padding: var(--apple-space-lg);
}

.page-header {
  margin: 0 auto var(--apple-space-lg);
  max-width: 960px;
}

.header-left {
  display: flex;
  gap: 12px;
  align-items: center;
}

.logo-pill {
  width: 40px;
  height: 40px;
  border-radius: var(--apple-radius-md);
  background: rgba(255, 90, 95, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--primary-100);
}

.header-left h1 {
  margin: 0;
  font-size: var(--apple-font-size-h2);
}

.header-left p {
  margin: 4px 0 0;
  color: var(--apple-text-secondary);
  font-size: var(--apple-font-size-caption);
}

.page-main {
  max-width: 760px;
  margin: 0 auto;
}

.sub-title {
  margin: 0 0 12px;
  font-size: var(--apple-font-size-h3);
}

.capability-list {
  margin: 0 0 12px;
  padding-left: 20px;
  line-height: 1.6;
}

.muted {
  font-size: var(--apple-font-size-caption);
  color: var(--apple-text-secondary);
}
</style>

