<template>
  <el-tag :type="tagType" size="small" effect="light" round>{{ label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    status?: string
  }>(),
  {
    status: ''
  }
)

const normalized = computed(() => String(props.status || '').trim().toLowerCase())

const tagType = computed<'success' | 'warning' | 'danger' | 'info' | 'primary'>(() => {
  if (normalized.value === 'approved') return 'success'
  if (normalized.value === 'applied') return 'primary'
  if (normalized.value === 'rejected') return 'danger'
  if (normalized.value === 'pending') return 'warning'
  return 'info'
})

const label = computed(() => {
  const map: Record<string, string> = {
    pending: '待处理',
    approved: '已批准',
    rejected: '已拒绝',
    applied: '已应用'
  }
  return map[normalized.value] || (props.status || '-')
})
</script>
