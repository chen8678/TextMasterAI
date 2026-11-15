<template>
  <div
    class="brand-mark"
    :class="{ 'brand-mark--flat': !padded, 'brand-mark--circle': circular }"
    :style="{
      width: `${size}px`,
      height: `${size}px`,
      borderRadius: circular ? `${size}px` : `${Math.round(size * 0.35)}px`
    }"
  >
    <img :src="logo" alt="Text Master AI Logo" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    size?: number
    padded?: boolean
    circular?: boolean
  }>(),
  {
    size: 56,
    padded: true,
    circular: false
  }
)

const padded = computed(() => props.padded)
const circular = computed(() => props.circular)
const size = computed(() => props.size)
// 直接使用 public 目录下的品牌 Logo
// 请确保已将 14566667-1476-4086-8722-4cf1b9b3bda1.jpg 复制/重命名为 frontend/public/logo-zq.png
const logo = '/logo-zq.png'
</script>

<style scoped>
.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px;
  border-radius: 999px;
  background: #fff;
  border: 1px solid rgba(0, 0, 0, 0.08);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(18px);
}

.brand-mark--flat {
  padding: 0;
  background: transparent;
  border: none;
  box-shadow: none;
  backdrop-filter: none;
}

.brand-mark img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: inherit;
}

.brand-mark--circle {
  border-radius: 999px !important;
}
</style>

