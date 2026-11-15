<template>
  <div id="app">
    <router-view />
  </div>
</template>

<script setup lang="ts">
// Application shell only renders router-view
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

#app {
  font-family: var(--apple-font-family);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--apple-text-primary);
  line-height: 1.6;
  background: var(--apple-background);
  min-height: 100vh;
}

body {
  margin: 0;
  background: var(--apple-background);
  color: var(--apple-text-primary);
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.25);
  border-radius: 3px;
}

.ghost-btn {
  border-radius: var(--apple-pill-radius) !important;
  border: 1px solid var(--bg-300) !important;
  background: var(--bg-200) !important;
  color: var(--text-100) !important;
  padding: 0 18px !important;
  display: inline-flex !important;
  align-items: center;
  gap: 6px;
}

.ghost-btn:hover {
  background: var(--bg-300) !important;
}

.el-card {
  border-radius: var(--apple-card-radius) !important;
  border: 1px solid var(--apple-border) !important;
  background: var(--apple-surface) !important;
  box-shadow: none !important;
  transition: border-color 0.2s ease, transform 0.2s ease !important;
}

.el-card:hover {
  border-color: var(--primary-100) !important;
  transform: translateY(-2px);
}

.el-divider {
  border-top-color: var(--apple-border) !important;
}

.el-button {
  border-radius: var(--apple-pill-radius) !important;
  font-weight: 500 !important;
  border: 1px solid transparent !important;
  box-shadow: none !important;
  padding: 10px 20px !important;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease !important;
}

.el-button--primary {
  background: var(--apple-brand-blue) !important;
  border-color: var(--apple-brand-blue) !important;
  color: #fff !important;
}

.el-button--primary:hover {
  background: var(--apple-brand-blue-hover) !important;
  border-color: var(--apple-brand-blue-hover) !important;
}

.el-button--success {
  background: var(--apple-success) !important;
  border-color: var(--apple-success) !important;
  color: #fff !important;
}

.el-button--warning {
  background: var(--apple-warning) !important;
  border-color: var(--apple-warning) !important;
  color: var(--apple-text-primary) !important;
}

.el-button--danger {
  background: var(--apple-danger) !important;
  border-color: var(--apple-danger) !important;
  color: #fff !important;
}

.el-button--info,
.el-button--default {
  background: transparent !important;
  border-color: var(--apple-border) !important;
  color: var(--apple-text-primary) !important;
}

.el-button--info:hover,
.el-button--default:hover {
  border-color: var(--apple-brand-blue) !important;
  color: var(--apple-brand-blue) !important;
}

.el-button--text,
.el-button.is-text {
  background: transparent !important;
  border: none !important;
  color: var(--apple-brand-blue) !important;
  padding: 8px 12px !important;
}

.el-button--text:hover,
.el-button.is-text:hover {
  background: rgba(255, 90, 95, 0.12) !important;
}

.el-input__wrapper,
.el-select .el-input__wrapper,
.el-textarea__inner {
  border-radius: var(--apple-control-radius) !important;
  border: 1px solid var(--apple-border) !important;
  background: var(--apple-surface) !important;
  box-shadow: none !important;
}

/* EP 2.4+ Select 下拉挂在 body，与顶栏浅色背景上选项文字对比度 */
.el-select-dropdown__item {
  color: var(--apple-text-primary) !important;
}

.el-input__wrapper.is-focus,
.el-select .el-input.is-focus .el-input__wrapper,
.el-textarea__inner:focus {
  border-color: var(--primary-100) !important;
  box-shadow: 0 0 0 3px rgba(255, 90, 95, 0.15) !important;
}

.el-tag {
  border-radius: var(--apple-pill-radius) !important;
  border: 1px solid var(--apple-border) !important;
  background: transparent !important;
  color: var(--apple-text-secondary) !important;
}

.el-dialog {
  border-radius: 28px !important;
  padding: 12px 0 24px !important;
}

.el-dialog__header {
  padding: 24px 32px 12px !important;
  border-bottom: 1px solid var(--apple-border);
}

.el-dialog__body {
  padding: 20px 32px !important;
}

.el-dialog__footer {
  padding: 0 32px 24px !important;
  border-top: 1px solid var(--apple-border);
}

.el-table,
.el-table__header-wrapper,
.el-table__body-wrapper {
  background: transparent !important;
}

.el-table th,
.el-table td {
  border-bottom: 1px solid var(--apple-border) !important;
}

.el-table--border {
  border: 1px solid var(--apple-border) !important;
}

.el-message,
.el-notification {
  border-radius: 18px !important;
  border: 1px solid var(--apple-border) !important;
  box-shadow: none !important;
}

.el-empty {
  padding: 32px 16px !important;
}

@media (max-width: 768px) {
  .header-content {
    padding: 0 1rem !important;
  }

  .header-controls {
    flex-direction: column;
    gap: 0.5rem;
    align-items: flex-end;
  }

  .control-group {
    min-width: 120px;
  }
}
</style>

