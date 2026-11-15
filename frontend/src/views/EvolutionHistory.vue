<template>
  <div class="history-page">
    <PageScaffold>
      <template #header>
        <PageHeader class="history-header">
          <div>
            <h1>进化历史时间线</h1>
            <p class="sub">按 Skill 域与状态查看最近进化记录（管理员）</p>
          </div>
          <template #actions>
            <el-button plain @click="router.push('/admin/self-evolution')">返回自进化管理</el-button>
          </template>
        </PageHeader>
      </template>

      <template #toolbar v-if="isStaff">
        <EvolutionFilterBar>
            <el-select v-model="filters.domain" clearable filterable placeholder="筛选 evolution_domain" style="width: 220px">
              <el-option label="全部领域" value="" />
              <el-option v-for="d in domainOptions" :key="d" :label="d" :value="d" />
            </el-select>
            <el-select v-model="filters.skillId" clearable filterable placeholder="筛选 Skill" style="width: 320px">
              <el-option label="全部 Skill" value="" />
              <el-option
                v-for="s in skillMetaList"
                :key="s.id"
                :label="`${s.name} (${s.id})`"
                :value="s.id"
              />
            </el-select>
            <el-input-number v-model="filters.limit" :min="50" :max="1000" :step="50" />
            <el-button type="primary" :loading="loading" @click="loadHistory">刷新</el-button>
        </EvolutionFilterBar>
      </template>

      <template v-if="isStaff">
        <div class="stats">
          <el-tag type="info">记录数：{{ rows.length }}</el-tag>
          <el-tag type="success">领域数：{{ domainOptions.length }}</el-tag>
          <el-tag type="warning">Top Skill 维度：{{ topSkillCount }}</el-tag>
        </div>

        <div ref="chartRef" class="timeline-chart" />

        <el-table v-loading="loading" :data="rows" stripe class="panel-table">
          <el-table-column prop="created_at_display" label="时间" width="190" />
          <el-table-column prop="skill_name" label="Skill" width="220" />
          <el-table-column prop="domain" label="Domain" width="160" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">
              <StatusBadge :status="row.status" />
            </template>
          </el-table-column>
          <el-table-column prop="provenance" label="来源" min-width="160" />
        </el-table>
      </template>
      <el-alert
        v-else
        type="warning"
        title="无权限"
        description="请使用管理员账号访问该页面。"
        show-icon
      />
    </PageScaffold>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api from '@/utils/api'
import { useAuthStore } from '@/stores/auth'
import PageScaffold from '@/components/templates/PageScaffold.vue'
import PageHeader from '@/components/templates/PageHeader.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import EvolutionFilterBar from '@/components/composite/EvolutionFilterBar.vue'

type SkillMetaItem = {
  id: string
  name: string
  evolution_domain?: string
}

type TimelineRow = {
  id: string
  skill_id: string
  skill_name: string
  domain: string
  status: 'pending' | 'approved' | 'rejected' | 'applied' | string
  provenance: string
  created_at: string
  created_at_display?: string
  reviewed_at?: string | null
}

const router = useRouter()
const authStore = useAuthStore()
const isStaff = computed(() => !!(authStore.user?.is_staff || authStore.user?.is_superuser))

const loading = ref(false)
const rows = ref<TimelineRow[]>([])
const skillMetaList = ref<SkillMetaItem[]>([])
const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const filters = ref({
  domain: '',
  skillId: '',
  limit: 300
})

const domainOptions = computed(() => {
  const set = new Set<string>()
  skillMetaList.value.forEach((s) => {
    const d = String(s.evolution_domain || '').trim()
    if (d) set.add(d)
  })
  rows.value.forEach((r) => {
    if (r.domain) set.add(r.domain)
  })
  return [...set].sort()
})
const topSkillCount = computed(() => {
  const uniq = new Set(rows.value.map((r) => `${r.skill_name} (${r.skill_id})`))
  return Math.min(uniq.size, 40)
})

function formatTime(v: string) {
  if (!v) return ''
  try {
    return new Date(v).toLocaleString('zh-CN')
  } catch {
    return v
  }
}

function statusColor(status: string): string {
  if (status === 'applied') return '#16a34a'
  if (status === 'approved') return '#2563eb'
  if (status === 'rejected') return '#ef4444'
  return '#f59e0b'
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const ySkills = [...new Set(rows.value.map((r) => `${r.skill_name} (${r.skill_id})`))].slice(0, 40)
  const points = rows.value
    .filter((r) => ySkills.includes(`${r.skill_name} (${r.skill_id})`))
    .map((r) => ({
      value: [r.created_at, `${r.skill_name} (${r.skill_id})`, r.status, r.domain, r.provenance],
      itemStyle: { color: statusColor(r.status) }
    }))
  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: (p: any) => {
        const [t, skill, status, domain, provenance] = p.value || []
        return `${formatTime(String(t || ''))}<br/>${skill}<br/>状态: ${status}<br/>域: ${domain}<br/>来源: ${provenance || '-'}`
      }
    },
    grid: { left: 220, right: 24, top: 30, bottom: 36 },
    xAxis: { type: 'time' },
    yAxis: {
      type: 'category',
      data: ySkills
    },
    series: [
      {
        type: 'scatter',
        symbolSize: 10,
        data: points
      }
    ]
  })
}

async function fetchSkillMeta() {
  try {
    const { data } = await api.get('/skills/meta/list/')
    skillMetaList.value = Array.isArray(data?.items) ? data.items : []
  } catch {
    skillMetaList.value = []
  }
}

async function loadHistory() {
  if (!isStaff.value) return
  loading.value = true
  try {
    const params: Record<string, string | number> = { limit: filters.value.limit }
    if (filters.value.domain) params.domain = filters.value.domain
    if (filters.value.skillId) params.skill_id = filters.value.skillId
    const { data } = await api.get('/skills/evolution/history/', { params })
    rows.value = (Array.isArray(data?.items) ? data.items : []).map((x: TimelineRow) => ({
      ...x,
      created_at_display: formatTime(x.created_at)
    }))
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载进化历史失败')
    rows.value = []
  } finally {
    loading.value = false
    await nextTick()
    renderChart()
  }
}

function handleResize() {
  chart?.resize()
}

watch(
  () => rows.value.length,
  async () => {
    await nextTick()
    renderChart()
  }
)

onMounted(async () => {
  await fetchSkillMeta()
  await loadHistory()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.history-page { max-width: 1200px; margin: 0 auto; padding: 24px; }
.history-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 12px; }
.history-header h1 { margin: 0 0 4px; font-size: 24px; }
.sub { margin: 0; color: var(--apple-text-secondary); }
.stats { display: flex; gap: 8px; margin-bottom: 12px; }
.timeline-chart { height: 420px; border: 1px solid var(--apple-border); border-radius: 10px; margin-bottom: 14px; background: #fff; }
.panel-table {
  border: 1px solid var(--apple-border);
  border-radius: 10px;
  overflow: hidden;
}
</style>
