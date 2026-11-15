<template>
  <PageToolbar class="admin-action-bar">
    <div class="admin-action-bar__controls">
      <slot />
    </div>
  </PageToolbar>
</template>

<script setup lang="ts">
import PageToolbar from '@/components/templates/PageToolbar.vue'
</script>

<style scoped>
.admin-action-bar {
  padding: 0;
}

.admin-action-bar__controls {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}
</style>
