<template>
  <div class="page-toolbar">
    <div class="page-toolbar__main">
      <slot />
    </div>
    <div v-if="$slots.extra" class="page-toolbar__extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<style scoped>
.page-toolbar {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.page-toolbar__main {
  min-width: 0;
}

.page-toolbar__extra {
  color: var(--apple-text-secondary);
  font-size: 13px;
}
</style>
