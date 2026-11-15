<template>
  <div class="page-scaffold">
    <header v-if="$slots.header" class="page-scaffold__header">
      <slot name="header" />
    </header>
    <section v-if="$slots.toolbar" class="page-scaffold__toolbar">
      <slot name="toolbar" />
    </section>
    <main class="page-scaffold__content">
      <slot />
    </main>
    <footer v-if="$slots.feedback" class="page-scaffold__feedback">
      <slot name="feedback" />
    </footer>
  </div>
</template>

<style scoped>
.page-scaffold {
  display: flex;
  flex-direction: column;
  gap: 14px;
  width: 100%;
}

.page-scaffold__header,
.page-scaffold__toolbar,
.page-scaffold__feedback {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}

.page-scaffold__content {
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
}
</style>
