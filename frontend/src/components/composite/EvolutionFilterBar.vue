<template>
  <PageToolbar class="evolution-filter-bar">
    <div class="evolution-filter-bar__controls">
      <slot />
    </div>
    <template v-if="$slots.meta" #extra>
      <slot name="meta" />
    </template>
  </PageToolbar>
</template>

<script setup lang="ts">
import PageToolbar from '@/components/templates/PageToolbar.vue'
</script>

<style scoped>
.evolution-filter-bar {
  border: 1px solid var(--apple-border);
  border-radius: 10px;
  background: #fff;
  padding: 12px;
}

.evolution-filter-bar__controls {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
