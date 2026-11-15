<template>
  <section class="page-section-card">
    <slot />
  </section>
</template>

<style scoped>
.page-section-card {
  border: 1px solid var(--apple-border);
  border-radius: 16px;
  background: var(--apple-surface);
  padding: 20px;
}
</style>
