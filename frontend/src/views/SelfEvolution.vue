<template>
  <div class="evo-page">
    <PageScaffold>
      <template #header>
        <PageHeader class="evo-header">
          <div class="header-main">
            <el-button text @click="router.back()">
              <el-icon><ArrowLeft /></el-icon>
              返回
            </el-button>
            <h1>自进化管理</h1>
            <p class="sub">Skill 草案与 Agent 配置提案（需管理员）</p>
          </div>
          <template #actions>
            <el-button plain @click="router.push('/admin/evolution-history')">查看进化时间线</el-button>
          </template>
        </PageHeader>
      </template>
      <el-alert v-if="!isStaff" type="warning" title="无权限" description="请使用管理员账号登录。" show-icon />
      <template v-else>
      <div class="overview-stats">
        <el-tag type="info">Skill 草案：{{ skillItems.length }}</el-tag>
        <el-tag type="warning">Agent 提案：{{ agentItems.length }}</el-tag>
        <el-tag type="success">总览记录：{{ overviewItems.length }}</el-tag>
      </div>
      <el-tabs v-model="activeTab" class="evo-tabs">
        <el-tab-pane label="Skill 进化草案" name="skill">
          <EvolutionFilterBar>
              <el-select
                v-model="skillId"
                filterable
                clearable
                placeholder="选择 Skill"
                style="width: 320px"
              >
                <el-option
                  v-for="s in skillMetaList"
                  :key="s.id"
                  :label="`${s.name} (${s.id})`"
                  :value="s.id"
                />
              </el-select>
              <el-select v-model="skillProvenanceFilter" placeholder="来源筛选" style="width: 200px" clearable>
                <el-option label="全部来源" value="all" />
                <el-option label="仅 skill_creator_trial" value="skill_creator_trial" />
                <el-option label="仅 sandbox" value="sandbox" />
              </el-select>
              <el-button type="primary" :loading="skillLoading" @click="loadSkillStaging">加载草案</el-button>
          </EvolutionFilterBar>
          <el-table v-loading="skillLoading" :data="filteredSkillItems" stripe class="panel-table">
            <el-table-column type="expand">
              <template #default="{ row }">
                <pre class="md-preview md-preview--inline">{{ row.draft_markdown || '（无）' }}</pre>
              </template>
            </el-table-column>
            <el-table-column prop="id" label="草案 ID" width="280" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <StatusBadge :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column prop="provenance" label="来源" width="120" />
            <el-table-column prop="created_by" label="创建人" width="120" />
            <el-table-column prop="reviewed_by" label="审核人" width="120" />
            <el-table-column prop="created_at" label="时间" width="180" />
            <el-table-column prop="reviewed_at" label="审核时间" width="180" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'pending'"
                  type="success"
                  size="small"
                  :loading="applySkillId === row.id"
                  @click="applySkill(row.id)"
                >
                  合并
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="Agent 配置提案" name="agent">
          <p v-if="currentAgentGovernance" class="gov-hint">
            当前 Agent 治理：<strong>{{ currentAgentGovernance }}</strong>
            <span v-if="currentAgentGovernance === 'gated'">（应用提案需超级管理员）</span>
            <span v-if="currentAgentGovernance === 'auto'">（满足置信度与增量条件时可能自动合并 skills）</span>
          </p>
          <EvolutionFilterBar>
              <el-select v-model="agentId" placeholder="选择 Agent" style="max-width: 280px" filterable @change="onAgentChange">
                <el-option v-for="a in agentList" :key="a.id" :label="`${a.name} (${a.id})`" :value="a.id" />
              </el-select>
              <el-button type="primary" :loading="agentLoading" @click="loadAgentProposals">加载提案</el-button>
          </EvolutionFilterBar>
          <el-table v-loading="agentLoading" :data="agentItems" stripe class="panel-table">
            <el-table-column type="expand">
              <template #default="{ row }">
                <pre class="md-preview md-preview--inline">{{ JSON.stringify(row.payload, null, 2) }}</pre>
              </template>
            </el-table-column>
            <el-table-column prop="id" label="提案 ID" width="280" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <StatusBadge :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column prop="provenance" label="来源" width="120" />
            <el-table-column prop="created_by" label="创建人" width="120" />
            <el-table-column prop="reviewed_by" label="审核人" width="120" />
            <el-table-column prop="created_at" label="时间" width="180" />
            <el-table-column prop="reviewed_at" label="审核时间" width="180" />
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'pending'"
                  type="success"
                  size="small"
                  :loading="busyProposal === row.id"
                  @click="applyAgent(row.id)"
                >
                  应用
                </el-button>
                <el-button
                  v-if="row.status === 'pending'"
                  type="danger"
                  size="small"
                  plain
                  :loading="busyProposal === row.id + 'r'"
                  @click="rejectAgent(row.id)"
                >
                  拒绝
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="审批总览" name="overview">
          <EvolutionFilterBar>
              <el-select v-model="overviewStatus" placeholder="状态筛选" style="width: 200px">
                <el-option label="全部状态" value="" />
                <el-option label="pending" value="pending" />
                <el-option label="applied" value="applied" />
                <el-option label="approved" value="approved" />
                <el-option label="rejected" value="rejected" />
              </el-select>
              <el-input-number v-model="overviewLimit" :min="20" :max="300" :step="20" />
              <el-button type="primary" :loading="overviewLoading" @click="loadOverview">刷新总览</el-button>
          </EvolutionFilterBar>
          <el-table v-loading="overviewLoading" :data="overviewItems" stripe class="panel-table">
            <el-table-column prop="kind" label="类型" width="90" />
            <el-table-column prop="target" label="对象" min-width="220" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <StatusBadge :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column prop="provenance" label="来源" width="140" />
            <el-table-column prop="created_by" label="创建人" width="120" />
            <el-table-column prop="reviewed_by" label="审核人" width="120" />
            <el-table-column prop="created_at" label="创建时间" width="180" />
            <el-table-column prop="reviewed_at" label="审核时间" width="180" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
      </template>
    </PageScaffold>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'
import { useAuthStore } from '@/stores/auth'
import PageScaffold from '@/components/templates/PageScaffold.vue'
import PageHeader from '@/components/templates/PageHeader.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import EvolutionFilterBar from '@/components/composite/EvolutionFilterBar.vue'

const router = useRouter()
const authStore = useAuthStore()

const isStaff = computed(() => !!(authStore.user?.is_staff || authStore.user?.is_superuser))

const activeTab = ref('skill')
const skillId = ref('')
const skillMetaList = ref<{ id: string; name: string; permission_level?: string; evolution_enabled?: boolean }[]>([])
const skillItems = ref<any[]>([])
const skillLoading = ref(false)
const applySkillId = ref('')
const skillProvenanceFilter = ref<'all' | 'skill_creator_trial' | 'sandbox'>('all')

const agentList = ref<
  { id: string; name: string; evolution_enabled?: boolean; evolution_governance?: string }[]
>([])
const agentId = ref('')
const currentAgentGovernance = ref('')
const agentItems = ref<any[]>([])
const agentLoading = ref(false)
const busyProposal = ref('')
const overviewLoading = ref(false)
const overviewStatus = ref('')
const overviewLimit = ref(120)
const overviewItems = ref<any[]>([])

function formatTime(v?: string | null): string {
  if (!v) return '-'
  try {
    return new Date(v).toLocaleString('zh-CN')
  } catch {
    return String(v)
  }
}

const onAgentChange = () => {
  const a = agentList.value.find((x) => x.id === agentId.value)
  currentAgentGovernance.value = a?.evolution_governance || ''
}

const loadSkillStaging = async () => {
  if (!skillId.value.trim()) {
    ElMessage.warning('请输入 Skill ID')
    return
  }
  skillLoading.value = true
  try {
    const { data } = await api.get(`/skills/${encodeURIComponent(skillId.value.trim())}/evolution/staging/`)
    const rows = Array.isArray(data.items) ? data.items : []
    skillItems.value = rows.map((x: any) => ({
      ...x,
      created_at: formatTime(x.created_at),
      reviewed_at: formatTime(x.reviewed_at),
      created_by: x.created_by || '-',
      reviewed_by: x.reviewed_by || '-'
    }))
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  } finally {
    skillLoading.value = false
  }
}

const applySkill = async (stagingId: string) => {
  applySkillId.value = stagingId
  try {
    await api.post(
      `/skills/${encodeURIComponent(skillId.value.trim())}/evolution/staging/${stagingId}/apply/`
    )
    ElMessage.success('已合并到 Skill.metadata')
    await loadSkillStaging()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  } finally {
    applySkillId.value = ''
  }
}

const filteredSkillItems = computed(() => {
  if (skillProvenanceFilter.value === 'all') return skillItems.value
  if (skillProvenanceFilter.value === 'sandbox') {
    return skillItems.value.filter((x) => String(x.provenance || '').includes('sandbox'))
  }
  return skillItems.value.filter((x) => String(x.provenance || '') === skillProvenanceFilter.value)
})

const fetchAgents = async () => {
  try {
    const { data } = await api.get('/chat/agents/')
    agentList.value = Array.isArray(data) ? data : []
    if (!agentId.value && agentList.value.length) {
      agentId.value = agentList.value[0].id
    }
    onAgentChange()
  } catch {
    agentList.value = []
  }
}

const fetchSkillMeta = async () => {
  try {
    const { data } = await api.get('/skills/meta/list/')
    skillMetaList.value = data.items || []
    if (!skillId.value && skillMetaList.value.length) {
      skillId.value = skillMetaList.value[0].id
    }
  } catch {
    skillMetaList.value = []
  }
}

const loadAgentProposals = async () => {
  if (!agentId.value) {
    ElMessage.warning('请选择 Agent')
    return
  }
  agentLoading.value = true
  try {
    const { data } = await api.get(`/agents/${encodeURIComponent(agentId.value)}/evolution/proposals/`)
    const rows = Array.isArray(data.items) ? data.items : []
    agentItems.value = rows.map((x: any) => ({
      ...x,
      created_at: formatTime(x.created_at),
      reviewed_at: formatTime(x.reviewed_at),
      created_by: x.created_by || '-',
      reviewed_by: x.reviewed_by || '-'
    }))
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载失败')
  } finally {
    agentLoading.value = false
  }
}

const loadOverview = async () => {
  overviewLoading.value = true
  try {
    const params = {
      limit: overviewLimit.value,
      ...(overviewStatus.value ? { status: overviewStatus.value } : {})
    }
    const [skillsRes, agentsRes] = await Promise.all([
      api.get('/skills/evolution/staging/overview/', { params }),
      api.get('/agents/evolution/proposals/overview/', { params })
    ])
    const skillRows = Array.isArray(skillsRes.data?.items) ? skillsRes.data.items : []
    const agentRows = Array.isArray(agentsRes.data?.items) ? agentsRes.data.items : []
    overviewItems.value = [
      ...skillRows.map((x: any) => ({
        kind: 'Skill',
        target: `${x.skill_name || x.skill_id} (${x.skill_id})`,
        status: x.status,
        provenance: x.provenance,
        created_by: x.created_by || '-',
        reviewed_by: x.reviewed_by || '-',
        created_at: formatTime(x.created_at),
        reviewed_at: formatTime(x.reviewed_at)
      })),
      ...agentRows.map((x: any) => ({
        kind: 'Agent',
        target: `${x.agent_name || x.agent_id} (${x.agent_id})`,
        status: x.status,
        provenance: x.provenance,
        created_by: x.created_by || '-',
        reviewed_by: x.reviewed_by || '-',
        created_at: formatTime(x.created_at),
        reviewed_at: formatTime(x.reviewed_at)
      }))
    ].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '加载审批总览失败')
    overviewItems.value = []
  } finally {
    overviewLoading.value = false
  }
}

const applyAgent = async (proposalId: string) => {
  busyProposal.value = proposalId
  try {
    await api.post(`/agents/${encodeURIComponent(agentId.value)}/evolution/proposals/${proposalId}/apply/`)
    ElMessage.success('已应用 suggested_skills')
    await loadAgentProposals()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  } finally {
    busyProposal.value = ''
  }
}

const rejectAgent = async (proposalId: string) => {
  busyProposal.value = proposalId + 'r'
  try {
    await api.post(`/agents/${encodeURIComponent(agentId.value)}/evolution/proposals/${proposalId}/reject/`)
    ElMessage.success('已拒绝')
    await loadAgentProposals()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.error || '操作失败')
  } finally {
    busyProposal.value = ''
  }
}

onMounted(() => {
  fetchAgents()
  fetchSkillMeta()
  loadOverview()
})
</script>

<style scoped>
.evo-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}
.evo-header h1 {
  margin: 8px 0 4px;
  font-size: 1.5rem;
}
.evo-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.header-main {
  min-width: 0;
}
.sub {
  color: var(--el-text-color-secondary);
  margin: 0 0 16px;
}
.panel-table {
  border: 1px solid var(--apple-border);
  border-radius: 10px;
  overflow: hidden;
}
.overview-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.md-preview {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  max-height: 360px;
  overflow: auto;
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 8px;
}
.evo-tabs {
  margin-top: 8px;
}
.gov-hint {
  font-size: 13px;
  color: var(--el-text-color-regular);
  margin: 0 0 12px;
}
.md-preview--inline {
  max-height: 240px;
  margin: 0;
}
</style>
