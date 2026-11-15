<template>
  <PageToolbar class="knowledge-filter-bar">
    <div class="knowledge-filter-bar__controls">
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
.knowledge-filter-bar {
  padding: 0;
}

.knowledge-filter-bar__controls {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
</style>
