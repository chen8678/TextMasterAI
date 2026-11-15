<template>
  <div class="home-page">
    <main class="page-main">
      <section class="hero-card">
        <div class="hero-left">
          <p class="eyebrow">Text Master AI</p>
          <h1>专注大学英语四级备考</h1>
          <p class="hero-subtitle">
            覆盖词汇、听力、阅读、写作与模考分析，配合备考资料知识库与智能答疑，帮你把四级复习走成一条可跟练的闭环。
          </p>
          <div class="hero-feature-list">
            <div class="hero-feature-card">
              <div class="feature-head">
                <AppleIcon name="document" :size="20" />
                <div>
                  <h3>四级备考</h3>
                  <p>词汇精练、听力阅读写作与模考，按四级题型推进</p>
                </div>
              </div>
              <el-button type="primary" size="large" class="wide-button" @click="goToCet">
                进入四级学习中心
              </el-button>
            </div>
            <div class="hero-feature-card">
              <div class="feature-head">
                <AppleIcon name="chat" :size="20" />
                <div>
                  <h3>备考问答</h3>
                  <p>围绕四级知识点与个人资料库提问，即时答疑与讲解</p>
                </div>
              </div>
              <el-button size="large" class="outline-button wide-button" @click="goToChat">
                进入智能问答
              </el-button>
            </div>
          </div>
        </div>
        <div class="hero-right">
          <div class="hero-graphic">
            <span class="graphic-glow graphic-glow--primary"></span>
            <span class="graphic-glow graphic-glow--secondary"></span>
            <svg class="hero-svg" viewBox="0 0 240 160" role="presentation" aria-hidden="true">
              <defs>
                <linearGradient id="heroGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stop-color="#FF5A5F" />
                  <stop offset="50%" stop-color="#5ac8fa" />
                  <stop offset="100%" stop-color="#a5b4fc" />
                </linearGradient>
                <filter id="heroShadow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="rgba(10,132,255,0.25)" />
                </filter>
              </defs>
              <path
                class="hero-arc"
                d="M10 120 C40 20, 200 20, 230 120"
                stroke="url(#heroGradient)"
                fill="none"
                stroke-width="8"
                stroke-linecap="round"
                filter="url(#heroShadow)"
              />
              <circle class="hero-node hero-node--one" cx="50" cy="60" r="6" />
              <circle class="hero-node hero-node--two" cx="190" cy="70" r="6" />
              <circle class="hero-node hero-node--three" cx="120" cy="110" r="5" />
            </svg>
            <div class="graphic-card graphic-card--primary">
              <p>词汇 · 听说读写</p>
              <span>按四级题型拆练，逐步补齐薄弱项</span>
            </div>
            <div class="graphic-card graphic-card--secondary">
              <p>模考 · 学情分析</p>
              <span>模拟测验后复盘得分与复习建议</span>
            </div>
          </div>
        </div>
      </section>

    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppleIcon from '@/components/AppleIcon.vue'

const router = useRouter()

const goToCet = () => {
  router.push('/cet')
}

const goToChat = () => {
  router.push('/chat')
}

onMounted(() => {})
</script>

<style scoped>
.home-page {
  min-height: 100vh;
  background: var(--bg-100);
  padding: 32px 48px 80px;
  color: var(--apple-text-primary);
}

.page-main {
  max-width: 960px;
  margin: 0 auto;
}

.hero-card,
.function-panel,
.industry-panel,
.stats-panel {
  background: var(--bg-200);
  border-radius: var(--apple-radius-xl);
  padding: var(--apple-space-xl);
  border: 1px solid var(--apple-border);
}

.hero-card {
  padding: 28px 28px 24px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 24px;
  align-items: center;
}

.hero-left {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 16px;
}

.hero-left h1 {
  font-size: var(--apple-font-size-h1);
  margin: 12px 0;
  line-height: 1.15;
}

.hero-subtitle {
  font-size: var(--apple-font-size-body-lg);
  color: var(--apple-text-secondary);
  margin: 0;
  line-height: 1.5;
}

.hero-feature-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin: 20px 0 0;
}

.hero-feature-card {
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: var(--apple-radius-lg);
  padding: 18px 20px;
  background: var(--bg-200);
  display: flex;
  flex-direction: column;
  gap: 16px;
  box-shadow: none;
}

.feature-head {
  display: flex;
  gap: 12px;
  align-items: center;
}

.feature-head h3 {
  margin: 0;
  font-size: 16px;
}

.feature-head p {
  margin: 2px 0 0;
  color: var(--apple-text-secondary);
  font-size: var(--apple-font-size-caption);
}

.eyebrow {
  font-size: var(--apple-font-size-caption);
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: #8e8e93;
}

.description {
  color: var(--text-200);
  line-height: 1.6;
}

.hero-actions {
  margin-top: 24px;
  display: flex;
  gap: 16px;
}

.outline-button {
  border: 1px solid var(--primary-100);
  color: var(--primary-100);
}

.outline-button:hover {
  border-color: var(--primary-200);
  color: var(--primary-200);
}

.wide-button {
  width: 100%;
}

.stats-panel {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(10, 10, 15, 0.06);
  box-shadow: 0 24px 60px rgba(15, 15, 15, 0.08);
}

.stats-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
}

.stats-card-grid {
  margin-top: 20px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.stats-card {
  border: 1px solid rgba(10, 10, 15, 0.06);
  border-radius: 20px;
  padding: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.85), rgba(245, 245, 247, 0.9));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.4);
}

.stats-card-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.stat-icon-pill {
  width: 32px;
  height: 32px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.stat-icon-pill.tone-blue {
  background: rgba(10, 132, 255, 0.12);
  color: var(--primary-100);
}

.stat-icon-pill.tone-green {
  background: rgba(48, 209, 88, 0.12);
  color: #30d158;
}

.stat-icon-pill.tone-orange {
  background: rgba(255, 159, 10, 0.12);
  color: #ff9f0a;
}

.stat-icon-pill.tone-purple {
  background: rgba(191, 90, 242, 0.12);
  color: #bf5af2;
}

.stats-card strong {
  font-size: 26px;
  margin: 0;
  display: block;
}

.stats-card p {
  margin: 4px 0 0;
  color: var(--text-200);
  font-size: 13px;
}

.ghost-button {
  border: 1px solid rgba(10, 10, 15, 0.08);
  color: var(--text-100);
}

.ghost-button:hover {
  border-color: var(--primary-100);
  color: var(--primary-100);
}

.hero-right {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}

.hero-watermark {
  position: absolute;
  top: -18px;
  right: -18px;
  opacity: 0.35;
  transform: rotate(-8deg);
  pointer-events: none;
}

.hero-graphic {
  position: relative;
  width: 100%;
  max-width: 360px;
  border-radius: 28px;
  padding: 32px 28px 36px;
  border: 1px solid rgba(255, 255, 255, 0.6);
  background: rgba(255, 255, 255, 0.85);
  box-shadow: 0 25px 55px rgba(15, 15, 15, 0.12), inset 0 0 0 1px rgba(255, 255, 255, 0.4);
  overflow: hidden;
  backdrop-filter: blur(18px);
  animation: glassPulse 9s ease-in-out infinite;
}

.hero-graphic::after {
  content: '';
  position: absolute;
  inset: 8px;
  border-radius: 24px;
  border: 1px solid rgba(10, 132, 255, 0.08);
  pointer-events: none;
}

.graphic-glow {
  position: absolute;
  width: 220px;
  height: 220px;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.4;
  animation: glowDrift 16s ease-in-out infinite;
}

.graphic-glow--primary {
  top: -40px;
  right: -60px;
  background: radial-gradient(circle, rgba(10, 132, 255, 0.35), transparent 60%);
}

.graphic-glow--secondary {
  bottom: -80px;
  left: -40px;
  background: radial-gradient(circle, rgba(191, 90, 242, 0.3), transparent 65%);
  animation-delay: -6s;
}

.hero-svg {
  position: relative;
  width: 100%;
  height: 180px;
  margin-bottom: 20px;
  z-index: 1;
}

.hero-arc {
  stroke-dasharray: 520;
  stroke-dashoffset: 520;
  animation: arcDraw 8s ease-in-out infinite;
}

.hero-node {
  stroke: rgba(255, 255, 255, 0.65);
  stroke-width: 2;
  filter: drop-shadow(0 8px 18px rgba(10, 10, 10, 0.18));
}

.hero-node--one {
  fill: var(--primary-100);
  animation: nodePulse 6s ease-in-out infinite;
}

.hero-node--two {
  fill: #a5b4fc;
  animation: nodePulse 7s ease-in-out infinite;
}

.hero-node--three {
  fill: #34c759;
  animation: nodePulse 5s ease-in-out infinite;
}

.graphic-card {
  position: relative;
  background: rgba(245, 245, 247, 0.92);
  border-radius: 18px;
  padding: 18px 20px;
  margin-bottom: 14px;
  box-shadow: 0 10px 24px rgba(15, 15, 15, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(16px);
  animation: floatCard 7s ease-in-out infinite;
}

.graphic-card--secondary {
  animation-delay: -3s;
}

.graphic-card p {
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--text-100);
}

.graphic-card span {
  color: var(--text-200);
  font-size: 14px;
}

@keyframes arcDraw {
  0% {
    stroke-dashoffset: 520;
  }
  35% {
    stroke-dashoffset: 0;
  }
  65% {
    stroke-dashoffset: 0;
  }
  100% {
    stroke-dashoffset: -520;
  }
}

@keyframes nodePulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.25);
    opacity: 0.75;
  }
}

@keyframes floatCard {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-8px);
  }
}

@keyframes glowDrift {
  0% {
    transform: translate(-10px, -10px) scale(0.95);
  }
  50% {
    transform: translate(20px, 10px) scale(1.1);
  }
  100% {
    transform: translate(-10px, -5px) scale(0.95);
  }
}

@keyframes glassPulse {
  0%,
  100% {
    box-shadow: 0 25px 55px rgba(15, 15, 15, 0.12), inset 0 0 0 1px rgba(255, 255, 255, 0.4);
  }
  50% {
    box-shadow: 0 30px 60px rgba(15, 15, 15, 0.16), inset 0 0 0 1px rgba(10, 132, 255, 0.2);
  }
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.panel-subtitle {
  margin-top: 8px;
  color: var(--apple-text-secondary);
  font-size: var(--apple-font-size-body);
  max-width: 620px;
}

.function-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
}

.function-card {
  border: 1px solid #ededf0;
  border-radius: 20px;
  padding: 24px;
  background: var(--bg-200);
  min-height: 220px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  transition: transform 0.2s ease, border-color 0.2s ease;
}

.function-card:hover {
  transform: translateY(-6px);
  border-color: var(--primary-100);
}

.card-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgba(10, 132, 255, 0.08);
  display: inline-flex;
    align-items: center;
  justify-content: center;
}

.function-card h3 {
  margin: 0;
  font-size: 18px;
}

.function-card p {
  margin: 0;
  color: var(--text-200);
  line-height: 1.5;
}

.card-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: auto;
}

.card-tags span {
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(10, 132, 255, 0.08);
  color: var(--primary-100);
}

.function-card--primary {
  background: #f7fbff;
  border-color: rgba(10, 132, 255, 0.2);
  cursor: pointer;
}

.function-panel--extensions {
  background: var(--bg-200);
}

.extension-grid .function-card {
  background: #fff;
  border-color: #ededf0;
}

.card-icon--ghost {
  background: rgba(10, 132, 255, 0.05);
}

.card-tag {
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(10, 132, 255, 0.08);
  color: var(--primary-100);
  font-size: 12px;
  margin: 4px 0 8px;
}

.function-grid .function-card {
  cursor: pointer;
}

.industry-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
}

.industry-card {
  border: 1px solid #ededf0;
  border-radius: 20px;
  padding: 24px;
  display: flex;
    flex-direction: column;
  gap: 16px;
  cursor: pointer;
  transition: border-color 0.2s ease;
}

.industry-card:hover {
  border-color: var(--primary-200);
}

.industry-tag {
  font-size: 12px;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: #8e8e93;
  margin-bottom: 8px;
}

.industry-stats {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.stat-chip {
  border: 1px solid #e5e5ea;
  border-radius: 16px;
  padding: 10px 14px;
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 13px;
  color: var(--text-200);
}

.stat-chip strong {
  font-size: 18px;
  color: var(--text-100);
}

.stats-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f2f2f7;
}

.stat-row:last-child {
  border-bottom: none;
}

.stat-row strong {
  font-size: 20px;
}

.stats-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #8e8e93;
}

@media (max-width: 768px) {
  .home-page {
    padding: 24px 20px 60px;
  }

  .top-nav {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }

  .hero-actions {
    flex-direction: column;
  }

  .stat-row {
    grid-template-columns: 1fr;
    gap: 8px;
  }
}
</style>

