<template>
  <div class="el-wizard">
    <PageScaffold>
      <template #header>
        <PageHeader>
          <div class="wiz-head">
            <h2>四级学习中心</h2>
            <p class="wiz-sub">
              专为<strong>大学英语四级</strong>：做一套题 → 看个性化反馈 → 拿到学习报告。可选上传自己的资料作补充；无需填写账户昵称等冗余信息。
            </p>
          </div>
          <template #actions>
            <el-button plain @click="router.push('/chat')">智能问答</el-button>
            <el-button plain @click="router.push('/knowledge')">知识库</el-button>
          </template>
        </PageHeader>
      </template>

      <el-card class="wiz-card" shadow="never">
        <el-alert
          v-if="!setupWizardVisible && wizardGraph?.interrupted && wizardGraph.human_action?.title"
          type="warning"
          :closable="false"
          class="hub-pause-alert"
        >
          <strong>{{ wizardGraph.human_action.title }}</strong> — {{ wizardGraph.human_action.detail }}
          <el-button type="primary" link class="hub-pause-btn" @click="openSetupWizard(wizardGraph.human_action.suggested_step ?? recommendedWizardStep)">
            继续设置
          </el-button>
        </el-alert>
        <el-alert
          v-if="!setupWizardVisible && hasWizardProgress && todayPhase !== 'tutor' && !(wizardGraph?.interrupted && wizardGraph.human_action?.title)"
          type="info"
          :closable="false"
          class="hub-pause-alert"
        >
          <strong>学习路线定制进行中</strong>
          <span v-if="hasRoadmapDraft"> — 路线草稿已保存在你的档案中，</span>
          <span v-else> — 进度已记录在档案中，</span>
          可随时继续。
          <el-button type="primary" link class="hub-pause-btn" @click="openSetupWizard(recommendedWizardStep)">
            继续定制
          </el-button>
        </el-alert>
        <el-card v-if="todayTasks.length || recallPackItems.length" class="today-card" shadow="never">
          <template #header>
            <div class="today-header-row">
              <span class="today-head">今日任务</span>
              <span v-if="todayPhase" class="today-phase">阶段：{{ todayPhase }}</span>
            </div>
          </template>
          <ul class="today-list">
            <li v-for="t in todayTasks" :key="t.id" class="today-item">
              <strong>{{ t.title }}</strong>
              <p class="hint tight-p">{{ t.detail }}</p>
              <div class="today-actions">
                <el-button
                  v-if="t.cta_step != null && t.cta_step !== ''"
                  link
                  type="primary"
                  @click="goTodayStep(t)"
                >
                  前往该步骤
                </el-button>
                <el-button v-if="t.cta_chat" link type="primary" @click="goTodayChat(t)">去智能问答</el-button>
              </div>
            </li>
          </ul>
          <div v-if="recallPackItems.length" class="recall-pack mt">
            <h4 class="recall-title">主动回忆包</h4>
            <ol class="recall-ol">
              <li v-for="p in recallPackItems" :key="p.id" class="recall-li">
                <strong>{{ p.title }}</strong>
                <p class="hint tight-p">{{ p.prompt }}</p>
              </li>
            </ol>
          </div>
          <p v-if="todayBlackboard.active_unit_id && todayPhase === 'tutor'" class="hint mt">
            当前单元：<code>{{ todayBlackboard.active_unit_id }}</code>
          </p>
          <p v-if="formattedLastDrill" class="hint mt">上次巩固：{{ formattedLastDrill }}</p>
          <el-button v-if="showDrillTouch" size="small" plain class="mt" :loading="drillLoading" @click="doDrillTouch">
            标记今日已巩固
          </el-button>
        </el-card>
        <el-collapse v-if="profile" class="prefs-collapse">
          <el-collapse-item title="更多设置 · 提醒与安静时段" name="reminders">
            <p class="hint tight-p">
              免打扰或安静时段内不展示主动回忆包与昨日/弱项推送（默认 22:00–次日 07:00）。
              <template v-if="todayQuietHoursActive">
                <strong class="warn-hint">当前处于安静时段。</strong>
              </template>
            </p>
            <div class="prefs-row">
              <span class="prefs-label">免打扰</span>
              <el-switch v-model="reminderDoNotDisturb" />
            </div>
            <div class="prefs-row">
              <span class="prefs-label">安静时段</span>
              <el-switch v-model="quietHoursEnabled" />
            </div>
            <div class="prefs-row prefs-row-times">
              <span class="prefs-label">时段</span>
              <div class="time-pair">
                <el-time-select
                  v-model="quietHoursStart"
                  start="00:00"
                  step="00:30"
                  end="23:30"
                  placeholder="开始"
                  style="width: 118px"
                />
                <span class="time-sep">至</span>
                <el-time-select
                  v-model="quietHoursEnd"
                  start="00:00"
                  step="00:30"
                  end="23:30"
                  placeholder="结束"
                  style="width: 118px"
                />
              </div>
            </div>
            <div class="prefs-row prefs-row-top">
              <span class="prefs-label">提醒强度</span>
              <el-radio-group v-model="reminderIntensity" size="small">
                <el-radio-button label="low">低</el-radio-button>
                <el-radio-button label="normal">标准</el-radio-button>
                <el-radio-button label="high">高</el-radio-button>
              </el-radio-group>
            </div>
            <el-button
              size="small"
              type="primary"
              class="mt"
              :loading="reminderPrefsSaving"
              @click="saveReminderPrefs"
            >
              保存提醒设置
            </el-button>
          </el-collapse-item>
        </el-collapse>

        <div class="wizard-hub-cta">
          <div class="hub-cta-inner">
            <div class="hub-cta-text">
              <h3>{{ hubCtaTitle }}</h3>
              <p class="hint">{{ hubCtaDesc }}</p>
            </div>
            <el-button type="primary" size="large" @click="openSetupWizard(recommendedWizardStep)">
              {{ hubCtaButtonLabel }}
            </el-button>
          </div>
          <el-progress
            v-if="wizardProgressPercent < 100 && todayPhase !== 'tutor'"
            :percentage="wizardProgressPercent"
            :stroke-width="10"
            class="hub-progress"
          />
        </div>

        <el-collapse v-if="profile && wizardDevMode" class="graph-obs-collapse">
          <el-collapse-item title="图运行时状态（Phase-C，断点续跑）" name="graph">
            <p v-if="graphObsLoading" class="hint tight-p">加载中…</p>
            <template v-else-if="graphObservability">
              <p class="hint tight-p">
                线程 ID：<code>{{ graphObservability.thread_id }}</code> · 当前节点：<strong>{{
                  graphObservability.current_node || '—'
                }}</strong>（游标 {{ graphObservability.node_cursor }}）
              </p>
              <p v-if="graphObservability.session_phase" class="hint tight-p">
                会话阶段：<code>{{ graphObservability.session_phase }}</code>
              </p>
              <p class="hint tight-p">
                与向导并行：`session_state` 更新后若已存在 checkpoint 会自动合并约定字段；档案中同时写入
                <code>graph_thread_id</code> / <code>graph_node_cursor</code> / <code>graph_current_node</code>（供对话等读取，不递增乐观锁版本）。
              </p>
              <p v-if="langgraphCheckpointTipDisplay" class="hint tight-p">
                LangGraph checkpoint 尖端：<code>{{ langgraphCheckpointTipDisplay }}</code>
              </p>
              <p v-if="langgraphPocTraceDisplay" class="hint tight-p">
                LangGraph POC 轨迹：<code>{{ langgraphPocTraceDisplay }}</code>
              </p>
              <p v-if="graphObservability?.langgraph_checkpointer" class="hint tight-p">
                Checkpointer：<code>{{ graphObservability.langgraph_checkpointer }}</code>
              </p>
              <div class="graph-obs-actions">
                <el-button size="small" plain class="mt-tight" @click="refreshGraphObservability">刷新</el-button>
                <el-button
                  size="small"
                  plain
                  class="mt-tight"
                  :loading="langgraphSyncLoading"
                  @click="doLanggraphSync"
                >
                  同步图至当前阶段
                </el-button>
                <el-button
                  size="small"
                  plain
                  class="mt-tight"
                  :loading="langgraphAdvanceLoading"
                  @click="doLanggraphAdvanceStep"
                >
                  单步推进 POC
                </el-button>
                <el-button
                  size="small"
                  plain
                  type="success"
                  class="mt-tight"
                  :disabled="!graphObservability?.current_node"
                  :loading="graphRunNodeLoading"
                  @click="doGraphRunNode"
                >
                  执行当前节点 Skill
                </el-button>
                <el-button
                  size="small"
                  plain
                  type="warning"
                  class="mt-tight"
                  :loading="graphRunChainLoading"
                  @click="doGraphRunChain"
                >
                  运行冒烟节点链
                </el-button>
                <el-button
                  size="small"
                  plain
                  class="mt-tight"
                  :loading="wizardGraphStartLoading"
                  @click="doWizardGraphStart"
                >
                  向导图 Start
                </el-button>
                <el-button
                  size="small"
                  plain
                  class="mt-tight"
                  :loading="wizardGraphResumeLoading"
                  @click="doWizardGraphResume"
                >
                  向导图 Resume
                </el-button>
                <el-button
                  size="small"
                  type="primary"
                  plain
                  class="mt-tight"
                  :loading="langgraphPocLoading"
                  @click="doLanggraphPocStep"
                >
                  运行 LangGraph POC
                </el-button>
                <el-button
                  size="small"
                  plain
                  class="mt-tight"
                  :loading="langgraphHistoryLoading"
                  @click="openLanggraphHistoryDialog"
                >
                  LangGraph 历史
                </el-button>
                <el-popconfirm
                  width="320"
                  title="将删除 LangGraph 中本账户默认 thread 的 checkpoint，并清除向导内记录的 POC 轨迹。之后「运行 POC」会从头跑一遍。"
                  confirm-button-text="重置"
                  cancel-button-text="取消"
                  @confirm="doLanggraphReset"
                >
                  <template #reference>
                    <el-button
                      size="small"
                      plain
                      type="warning"
                      class="mt-tight"
                      :loading="langgraphResetLoading"
                    >
                      重置 LangGraph 线程
                    </el-button>
                  </template>
                </el-popconfirm>
              </div>
            </template>
            <p v-else class="hint tight-p">暂无法读取图状态。</p>
          </el-collapse-item>
        </el-collapse>
      </el-card>

      <el-dialog
        v-model="setupWizardVisible"
        title="学习定制向导"
        width="min(720px, 94vw)"
        class="wiz-setup-dialog"
        :close-on-click-modal="false"
        align-center
        :before-close="onSetupWizardBeforeClose"
        @closed="onSetupWizardClosed"
      >
        <p class="wiz-dialog-intro">
          分步完成学习目标、测评与路线定稿。关闭前可「保存进度」；下次从首页「继续定制」进入，会从上次步骤恢复。
        </p>
        <div v-if="profile" class="graph-mode-bar graph-mode-bar--dialog">
          <el-switch
            v-if="wizardDevMode"
            v-model="graphWizardMode"
            active-text="图驱动向导（推荐）"
            inactive-text="经典 REST"
          />
          <el-alert
            v-if="graphWizardMode && wizardGraph"
            :type="wizardGraph.completed ? 'success' : wizardGraph.interrupted ? 'warning' : 'info'"
            :closable="false"
            class="graph-mode-alert"
          >
            <template v-if="wizardGraph.completed">
              向导图已跑完，阶段 <code>{{ wizardGraph.phase || 'tutor' }}</code>
            </template>
            <template v-else-if="wizardGraph.interrupted">
              <template v-if="wizardGraph.human_action?.title">
                <strong>{{ wizardGraph.human_action.title }}</strong> — {{ wizardGraph.human_action.detail }}
              </template>
              <template v-else>
                等待操作：下一步 <code>{{ (wizardGraph.next_nodes || []).join(' → ') || '—' }}</code>
              </template>
            </template>
            <template v-else>
              图状态：阶段 <code>{{ wizardGraph.phase || '—' }}</code>
            </template>
          </el-alert>
          <p v-if="wizardStreamProgress" class="hint graph-stream-hint">{{ wizardStreamProgress }}</p>
        </div>
        <el-steps id="wizard-steps-anchor" :active="activeStep" finish-status="success" align-center class="wiz-steps">
          <el-step title="开始" description="锁定四级" />
          <el-step title="做一套题" description="诊断测评" />
          <el-step title="互动反馈" description="评价 + 你的选择" />
          <el-step title="学习报告" description="保存路径" />
        </el-steps>

        <!-- Step 0 -->
        <section v-show="activeStep === 0" class="wiz-panel">
          <h3>四级学习路径 · 开始</h3>
          <el-alert type="success" :closable="false" class="gap-alert">
            <p class="bootstrap-sum">目标已锁定：<strong>大学英语四级（CET-4）</strong>，将使用系统预置四级词库生成诊断题与学习报告。</p>
            <p class="hint tight">无需选择学段或考试类型；有自己的讲义时可在报告步上传到知识库作补充。</p>
          </el-alert>
          <el-form label-position="top" class="wiz-form mt">
            <el-form-item label="每周可投入（分钟，可选）">
              <el-input-number v-model="weeklyMinutes" :min="30" :max="2000" :step="30" />
            </el-form-item>
          </el-form>
          <el-button type="primary" :loading="loading" @click="doBootstrapAndGoExam">
            {{ bootstrapDone ? '进入做题' : '开始四级诊断' }}
          </el-button>
          <p v-if="bootstrapDone" class="hint mt">已就绪，可直接进入做题。</p>
        </section>

        <!-- Step 1 -->
        <section v-show="activeStep === 1" class="wiz-panel">
          <template v-if="!profile">
            <h3>做一套题</h3>
            <p class="hint">请先点「开始四级诊断」。</p>
            <el-button type="primary" @click="activeStep = 0">返回开始</el-button>
          </template>
          <template v-else-if="!examItems.length">
            <h3>做一套题 · 组卷</h3>
            <el-alert type="success" :closable="false" class="gap-alert">
              <p v-if="bootstrapSummary" class="bootstrap-sum">{{ bootstrapSummary }}</p>
              <p class="hint tight">四级诊断：默认 5 题，约几分钟完成。</p>
            </el-alert>
            <el-form-item label="题量（可选）">
              <el-radio-group v-model="assessmentKind">
                <el-radio-button label="level_test">标准（5 题）</el-radio-button>
                <el-radio-button label="placement">更快（3 题）</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <div class="wiz-actions">
              <el-button @click="activeStep = 0">上一步</el-button>
              <el-button type="primary" :loading="loading" @click="doStartAssessment">
                开始做题
              </el-button>
            </div>
          </template>
          <template v-else>
          <h3>做一套题（{{ examItems.length }} 题）</h3>
          <div v-for="(q, idx) in examItems" :key="q.id" class="q-block">
            <p class="q-stem">
              <strong>{{ idx + 1 }}.</strong>
              {{ q.stem }}
            </p>
            <el-radio-group v-model="answers[q.id]" class="q-choices">
              <el-radio v-for="c in q.choices || []" :key="c" :label="c">{{ c }}</el-radio>
            </el-radio-group>
          </div>
          <div class="wiz-actions">
            <el-button @click="goBackAssessment">上一步</el-button>
            <el-button
              type="primary"
              :loading="loading"
              :disabled="!canSubmitExam"
              @click="doSubmitExam"
            >
              提交并查看反馈
            </el-button>
          </div>
          </template>
        </section>

        <!-- Step 2 -->
        <section v-show="activeStep === 2" class="wiz-panel">
          <h3>互动反馈</h3>
          <el-alert type="info" :closable="false" class="gap-alert">
            <pre class="gap-pre">{{ gapSummary || '（无摘要）' }}</pre>
          </el-alert>
          <h4 class="mt">想加强的方向</h4>
          <p class="hint">已根据薄弱项预选，可改选；也可直接采用系统建议。</p>
          <el-checkbox-group v-model="focusDimensions">
            <el-checkbox v-for="d in dimensionOptions" :key="d" :label="d">{{ dimensionLabel(d) }}</el-checkbox>
          </el-checkbox-group>
          <h4 class="mt">还想学什么（可选）</h4>
          <el-input
            v-model="learnerNote"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="例如：想专攻听力长对话、写作模板、或某本讲义里的错题…"
          />
          <div class="wiz-actions">
            <el-button @click="activeStep = 1">上一步</el-button>
            <el-button type="primary" :loading="loading" @click="doRoadmapDraft">
              生成学习报告
            </el-button>
          </div>
          <template v-if="roadmapMarkdown">
            <h4 class="mt">报告预览</h4>
            <div
              v-if="wizardStreamProgress && graphWizardMode"
              class="roadmap-preview markdown-body roadmap-stream-raw"
            >{{ roadmapMarkdown }}</div>
            <div v-else class="roadmap-preview markdown-body" v-html="renderMd(roadmapMarkdown)" />
            <el-button type="success" plain class="mt" @click="activeStep = 3">下一步：确认报告</el-button>
          </template>
        </section>

        <!-- Step 3 -->
        <section v-show="activeStep === 3" class="wiz-panel">
          <h3>学习报告</h3>
          <el-alert v-if="gapSummary" type="info" :closable="false" class="gap-alert">
            <strong>测评摘要</strong>
            <pre class="gap-pre">{{ gapSummary }}</pre>
          </el-alert>
          <p class="hint mt">可微调下方报告正文；确认后写入你的个人知识库，供后续陪练使用。</p>
          <el-input
            v-model="roadmapMarkdown"
            type="textarea"
            :rows="16"
            placeholder="学习报告 Markdown…"
            class="roadmap-ta"
          />
          <div class="wiz-row mt">
            <el-input v-model="finalizeTitle" placeholder="报告标题（默认：我的四级学习报告）" style="max-width: 360px" />
          </div>
          <p class="hint mt">
            可选：
            <el-button link type="primary" @click="router.push('/knowledge')">上传自己的资料到知识库</el-button>
            作为额外学习内容。
          </p>
          <el-collapse v-if="profile" class="revisions-collapse mt">
            <el-collapse-item title="历史报告版本（可选查看）" name="revisions">
              <div class="revisions-head">
                <el-button
                  size="small"
                  text
                  type="primary"
                  :loading="roadmapRevisionsLoading"
                  @click="loadRoadmapRevisions"
                >
                  刷新
                </el-button>
              </div>
              <p v-if="!roadmapRevisionsLoading && roadmapRevisions.length === 0" class="hint tight-p">
                尚无保存记录。
              </p>
              <el-table
                v-else-if="roadmapRevisions.length > 0"
                :data="roadmapRevisions"
                size="small"
                stripe
                class="revisions-table"
                max-height="220"
              >
                <el-table-column prop="version" label="版本" width="72" />
                <el-table-column label="时间" min-width="160">
                  <template #default="{ row }">
                    {{ formatRevTime(row.created_at) }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="148" fixed="right">
                  <template #default="{ row }">
                    <el-button link type="primary" @click="openRevisionPreview(row)">预览</el-button>
                    <el-button
                      v-if="row.document_id"
                      link
                      type="primary"
                      @click="goKnowledgeDocument(row)"
                    >
                      知识库
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-collapse-item>
          </el-collapse>
          <div class="wiz-actions">
            <el-button @click="activeStep = 2">上一步</el-button>
            <el-button plain :loading="draftSaveLoading" @click="doSaveRoadmapDraft">仅保存草稿</el-button>
            <el-button type="primary" :loading="loading" @click="doFinalize">
              保存学习报告
            </el-button>
          </div>
          <template v-if="finalizeResult">
            <el-result icon="success" title="已写入知识库" sub-title="可向量化用于检索">
              <template #extra>
                <p class="result-meta">文档 ID：{{ finalizeResult.document_id }}</p>
                <p class="result-meta">知识库 ID：{{ finalizeResult.knowledge_base_id }}</p>
                <el-button type="primary" @click="goChat">去智能问答（已预选库与主编排）</el-button>
                <el-button @click="router.push('/knowledge')">打开知识库管理</el-button>
              </template>
            </el-result>
          </template>
        </section>
        <template #footer>
          <div class="wiz-dialog-footer">
            <el-button plain :loading="progressSaveLoading" @click="saveWizardProgress(false)">
              保存进度
            </el-button>
            <el-button @click="saveWizardProgressAndClose">保存并关闭</el-button>
          </div>
        </template>
      </el-dialog>

      <el-dialog
        v-model="langgraphHistoryVisible"
        title="LangGraph 进程内 checkpoint 历史"
        width="min(720px, 94vw)"
        destroy-on-close
        class="lg-hist-dialog"
        @closed="langgraphHistoryJson = ''"
      >
        <p v-if="langgraphHistoryLoading" class="hint tight-p">加载中…</p>
        <pre v-else class="lg-hist-pre">{{ langgraphHistoryJson || '（无数据）' }}</pre>
      </el-dialog>
      <el-dialog
        v-model="revisionPreviewVisible"
        :title="revisionPreviewTitle"
        width="min(720px, 92vw)"
        destroy-on-close
        class="rev-preview-dialog"
        @closed="revisionPreview = null"
      >
        <div
          v-if="revisionPreview"
          class="roadmap-preview markdown-body rev-preview-body"
          v-html="renderMd(revisionPreview.markdown || '')"
        />
      </el-dialog>
    </PageScaffold>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import api from '@/utils/api'
import {
  DEFAULT_EXAM_GOAL,
  DEFAULT_LEVEL_TAG,
  inferAssessmentLevelFromTags,
  levelTagsPayload,
  pickPrimaryLevelTag
} from '@/constants/englishLevelTags'
import PageScaffold from '@/components/templates/PageScaffold.vue'
import PageHeader from '@/components/templates/PageHeader.vue'

marked.setOptions({ gfm: true, breaks: true })

const router = useRouter()
const route = useRoute()

/** 仅 URL `?dev=1` 时显示经典 REST 开关与图调试面板 */
const wizardDevMode = computed(() => {
  const d = route.query.dev
  return d === '1' || d === 'true'
})

type TodayTask = {
  id: string
  title: string
  detail: string
  cta_step?: number | null
  cta_chat?: boolean
  english_delegate?: string | null
}

const DEFAULT_ROADMAP_TITLE = '我的四级学习报告'

const activeStep = ref(0)
const setupWizardVisible = ref(false)
const loading = ref(false)
const draftSaveLoading = ref(false)
const progressSaveLoading = ref(false)

const levelTag = ref<string>(DEFAULT_LEVEL_TAG)
const examGoal = ref(DEFAULT_EXAM_GOAL)
const weeklyMinutes = ref(120)
const learnerNote = ref('')

/** 测评：placement=快速定级 3 题；level_test=完整测评 5 题 */
const assessmentKind = ref<'placement' | 'level_test'>('level_test')

const profile = ref<{
  id?: string | number
  default_kb_id?: string
  session_state?: Record<string, unknown>
  session_state_version?: number
} | null>(null)
const sessionStateVersion = ref(0)
const assessmentId = ref<string | null>(null)
const examItems = ref<Array<{ id: string; stem: string; choices?: string[]; dimension?: string }>>([])
const answers = ref<Record<string, string>>({})

const gapSummary = ref('')
const weakDimensions = ref<string[]>([])
const focusDimensions = ref<string[]>([])
const dimensionOptions = ['vocabulary', 'grammar', 'reading', 'listening', 'writing']

const roadmapMarkdown = ref('')
const roadmapOutlineJson = ref<Record<string, unknown>>({})
const finalizeTitle = ref(DEFAULT_ROADMAP_TITLE)
const finalizeResult = ref<{ document_id: string; knowledge_base_id: string } | null>(null)

type RoadmapRevisionRow = {
  id: string | number
  version: number
  markdown: string
  document_id: string | null
  /** 入库 Document 所属知识库；与 `default_kb_id` 可能不同（例如将来支持非默认库定稿） */
  knowledge_base_id?: string | null
  source_skill_run_id: string
  created_at: string
}

const roadmapRevisions = ref<RoadmapRevisionRow[]>([])
const roadmapRevisionsLoading = ref(false)
const revisionPreview = ref<RoadmapRevisionRow | null>(null)
const revisionPreviewVisible = ref(false)

type WizardHumanAction = {
  kind?: string
  title?: string
  detail?: string
  suggested_step?: number
  pending_node?: string
  next_node?: string
  cta_chat?: boolean
}

type WizardGraphState = {
  interrupted?: boolean
  completed?: boolean
  failed?: boolean
  next_nodes?: string[]
  pending_human_node?: string
  phase?: string
  poc_trace?: string[]
  node_data?: Record<string, unknown>
  last_error?: string
  human_action?: WizardHumanAction
}

type GraphObservabilityPayload = {
  thread_id: string
  node_cursor: number
  current_node: string | null
  wizard_nodes: string[]
  graph_state: Record<string, unknown>
  session_phase?: string | null
  langgraph_available?: boolean
  langgraph_checkpointer?: string
  langgraph_poc?: Record<string, unknown> | null
  langgraph_poc_completed?: boolean
  langgraph_poc_next?: string[]
  langgraph_checkpoint_tip?: Record<string, unknown> | null
  langgraph_sync?: Record<string, unknown>
  wizard_graph?: WizardGraphState
}

const graphObservability = ref<GraphObservabilityPayload | null>(null)
const graphObsLoading = ref(false)
const langgraphPocLoading = ref(false)
const langgraphAdvanceLoading = ref(false)
const langgraphSyncLoading = ref(false)
const langgraphResetLoading = ref(false)
const langgraphHistoryVisible = ref(false)
const langgraphHistoryLoading = ref(false)
const langgraphHistoryJson = ref('')
const graphRunNodeLoading = ref(false)
const graphRunChainLoading = ref(false)
const wizardGraphStartLoading = ref(false)
const wizardGraphResumeLoading = ref(false)
/** 主流程走 LangGraph start/resume；关闭后回退 REST */
const graphWizardMode = ref(true)

watch(
  wizardDevMode,
  (dev) => {
    if (!dev) graphWizardMode.value = true
  },
  { immediate: true }
)
const wizardGraph = ref<WizardGraphState | null>(null)
const wizardStreamProgress = ref('')

const revisionPreviewTitle = computed(() => {
  const r = revisionPreview.value
  if (!r) return '修订预览'
  return `修订预览 · v${r.version}`
})

/** Step 0 仅建档成功后为 true */
const bootstrapDone = ref(false)
const bootstrapSummary = ref('')

const todayTasks = ref<TodayTask[]>([])
const recommendedCurriculumKbId = ref('')

const recommendedWizardStep = computed(() => {
  if (todayPhase.value === 'tutor') return 3
  const st = profile.value?.session_state
  if (st && typeof st === 'object') {
    const phase = todayPhase.value || String(st.phase || 'intake')
    return stepFromSessionPhase(phase, st as Record<string, unknown>)
  }
  return activeStep.value
})

const hasRoadmapDraft = computed(() => {
  const st = profile.value?.session_state as Record<string, unknown> | undefined
  const saved = String(st?.roadmap_draft_markdown || '').trim()
  return saved.length > 0 || String(roadmapMarkdown.value || '').trim().length > 0
})

const hasWizardProgress = computed(() => {
  if (todayPhase.value === 'tutor') return false
  const st = profile.value?.session_state as Record<string, unknown> | undefined
  if (!st) return bootstrapDone.value
  if (st.bootstrap_completed) return true
  const phase = String(st.phase || todayPhase.value || 'intake').toLowerCase()
  return phase !== 'intake' || hasRoadmapDraft.value
})

const wizardProgressPercent = computed(() => {
  if (todayPhase.value === 'tutor') return 100
  return Math.min(100, Math.round(((activeStep.value + 1) / 4) * 100))
})

const hubCtaTitle = computed(() => {
  const phase = todayPhase.value || 'intake'
  if (phase === 'tutor') return '按报告继续练习'
  if (hasRoadmapDraft.value) return '确认并保存学习报告'
  if (phase === 'roadmap_review' || phase === 'roadmap') return '继续完善学习报告'
  if (bootstrapDone.value || phase === 'assessment') return '继续四级诊断'
  return '开始四级诊断'
})

const hubCtaDesc = computed(() => {
  const phase = todayPhase.value || 'intake'
  if (phase === 'tutor') return '报告已就绪：用预置四级词库与个人路径在智能问答中练习。'
  if (hasRoadmapDraft.value) return '报告草稿已保存，打开弹窗即可确认入库。'
  if (bootstrapDone.value || phase !== 'intake') return '接着做题、看反馈、生成报告。'
  return '无需选学段：直接做一套题，拿到个性化四级学习报告。'
})

const hubCtaButtonLabel = computed(() => {
  if (todayPhase.value === 'tutor') return '去智能问答'
  if (hasWizardProgress.value) return '继续'
  return '开始四级诊断'
})

function stepFromSessionPhase(phase: string, st: Record<string, unknown>): number {
  const ph = String(phase || 'intake').toLowerCase()
  if (ph === 'tutor') return 3
  if (ph === 'roadmap_review') return String(st.roadmap_draft_markdown || '').trim() ? 3 : 2
  if (ph === 'roadmap') return 2
  if (ph === 'assessment') return 1
  if (ph === 'intake') return st.bootstrap_completed ? 1 : 0
  const savedStep = Number(st.wizard_last_step)
  if (Number.isFinite(savedStep) && savedStep >= 0 && savedStep <= 3) return savedStep
  return 0
}

function restoreWizardProgressFromSessionState(st?: Record<string, unknown> | null) {
  if (!st || typeof st !== 'object') return
  if (st.bootstrap_completed) bootstrapDone.value = true
  const phase = String(st.phase || todayPhase.value || 'intake')
  activeStep.value = stepFromSessionPhase(phase, st)
  if (st.gap_summary != null && String(st.gap_summary).trim()) {
    gapSummary.value = String(st.gap_summary)
  }
  const weak = st.weak_dimensions
  if (Array.isArray(weak) && weak.length) {
    weakDimensions.value = weak.map(String)
    const picked = weakDimensions.value.filter((d) => dimensionOptions.includes(d))
    if (picked.length) focusDimensions.value = picked
  }
  const focus = st.focus_dimensions
  if (Array.isArray(focus) && focus.length) {
    focusDimensions.value = focus.map(String).filter((d) => dimensionOptions.includes(d))
  }
  const draftMd = st.roadmap_draft_markdown
  if (draftMd != null && String(draftMd).trim()) {
    roadmapMarkdown.value = String(draftMd)
  }
  const outline = st.roadmap_outline_json
  if (outline && typeof outline === 'object' && !Array.isArray(outline)) {
    roadmapOutlineJson.value = { ...(outline as Record<string, unknown>) }
  }
  const lc = st.learner_constraints
  if (lc && typeof lc === 'object' && !Array.isArray(lc)) {
    const lco = lc as Record<string, unknown>
    if (lco.exam_goal != null) examGoal.value = String(lco.exam_goal)
    if (typeof lco.weekly_minutes === 'number') weeklyMinutes.value = lco.weekly_minutes
    if (lco.learner_note != null) learnerNote.value = String(lco.learner_note)
  }
  if (st.learner_note != null && String(st.learner_note).trim()) {
    learnerNote.value = String(st.learner_note)
  }
  const lastAid = st.last_assessment_id
  if (lastAid != null && String(lastAid).trim()) {
    assessmentId.value = String(lastAid)
  }
}

function openSetupWizard(step?: number) {
  if (todayPhase.value === 'tutor') {
    void router.push({ path: '/chat', query: { agent: 'english_orchestrator', english_phase: 'tutor' } })
    return
  }
  restoreWizardProgressFromSessionState(profile.value?.session_state as Record<string, unknown> | undefined)
  const targetStep = typeof step === 'number' && Number.isFinite(step) && step >= 0 && step <= 3
    ? step
    : recommendedWizardStep.value
  activeStep.value = targetStep
  if (targetStep >= 1 && profile.value) bootstrapDone.value = true
  setupWizardVisible.value = true
}

async function saveWizardProgress(silent = false) {
  if (!profile.value) {
    if (!silent) ElMessage.warning('请先完成建档')
    return false
  }
  progressSaveLoading.value = true
  try {
    const patch: Record<string, unknown> = {
      wizard_last_step: activeStep.value,
      wizard_progress_saved_at: new Date().toISOString()
    }
    if (roadmapMarkdown.value?.trim()) {
      patch.roadmap_draft_markdown = roadmapMarkdown.value.trim()
      if (Object.keys(roadmapOutlineJson.value).length > 0) {
        patch.roadmap_outline_json = roadmapOutlineJson.value
      }
    }
    const { data } = await api.patch('/english-learning/profile/', {
      session_state: patch,
      session_state_version: sessionStateVersion.value
    })
    profile.value = data
    if (typeof data.session_state_version === 'number') {
      sessionStateVersion.value = data.session_state_version
    }
    if (roadmapMarkdown.value?.trim() && !graphWizardMode.value) {
      await api.post('/english-learning/roadmap/save-draft/', {
        roadmap_markdown: roadmapMarkdown.value,
        outline_json: Object.keys(roadmapOutlineJson.value).length > 0 ? roadmapOutlineJson.value : undefined,
        session_state_version: sessionStateVersion.value
      })
      await loadExistingProfile()
    }
    if (!silent) ElMessage.success('定制进度已保存')
    await refreshToday()
    return true
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    if (err.response?.status === 409) {
      if (!silent) ElMessage.warning('档案版本冲突，正在刷新…')
      await loadExistingProfile()
      await refreshToday()
      return false
    }
    if (!silent) ElMessage.error(err.response?.data?.detail || '保存进度失败')
    return false
  } finally {
    progressSaveLoading.value = false
  }
}

async function saveWizardProgressAndClose() {
  if (profile.value && (bootstrapDone.value || activeStep.value > 0)) {
    await saveWizardProgress(true)
  }
  setupWizardVisible.value = false
}

async function onSetupWizardBeforeClose(done: () => void) {
  if (todayPhase.value === 'tutor') {
    done()
    return
  }
  if (!profile.value || (!bootstrapDone.value && activeStep.value === 0 && !roadmapMarkdown.value?.trim())) {
    done()
    return
  }
  try {
    await ElMessageBox.confirm(
      '是否保存当前定制进度？保存后可在首页「继续定制向导」恢复。',
      '退出学习定制',
      {
        confirmButtonText: '保存并退出',
        cancelButtonText: '直接退出',
        distinguishCancelAndClose: true,
        type: 'info'
      }
    )
    await saveWizardProgress(true)
    done()
  } catch (action) {
    if (action === 'cancel') done()
  }
}

function onSetupWizardClosed() {
  void refreshToday()
}
const todayPhase = ref('')
const todayBlackboard = ref<{
  active_unit_id?: string
  last_drill_at?: string
  weak_dimensions?: string[]
}>({})
const recallPackItems = ref<Array<{ id: string; title: string; prompt: string; dimension?: string }>>([])
const drillLoading = ref(false)

const reminderDoNotDisturb = ref(false)
const reminderIntensity = ref<'low' | 'normal' | 'high'>('normal')
const quietHoursEnabled = ref(false)
const quietHoursStart = ref('22:00')
const quietHoursEnd = ref('07:00')
const reminderPrefsSaving = ref(false)
const todayQuietHoursActive = ref(false)

const showDrillTouch = computed(() => todayPhase.value === 'tutor')

const langgraphPocTraceDisplay = computed(() => {
  const gs = graphObservability.value?.graph_state
  if (!gs || typeof gs !== 'object') return ''
  const tr = gs.langgraph_poc_trace
  if (Array.isArray(tr) && tr.length) return tr.join(' → ')
  return ''
})

const langgraphCheckpointTipDisplay = computed(() => {
  const tip =
    graphObservability.value?.langgraph_checkpoint_tip ||
    graphObservability.value?.graph_state?.langgraph_checkpoint_tip
  if (!tip || typeof tip !== 'object') return ''
  try {
    return JSON.stringify(tip)
  } catch {
    return ''
  }
})

const formattedLastDrill = computed(() => {
  const s = todayBlackboard.value.last_drill_at
  if (!s || typeof s !== 'string') return ''
  try {
    return new Date(s).toLocaleString()
  } catch {
    return s
  }
})

const canSubmitExam = computed(() => {
  if (!examItems.value.length || !assessmentId.value) return false
  return examItems.value.every((q) => (answers.value[q.id] || '').length > 0)
})

function dimensionLabel(d: string) {
  const m: Record<string, string> = {
    vocabulary: '词汇',
    grammar: '语法',
    reading: '阅读',
    listening: '听力',
    writing: '写作'
  }
  return m[d] || d
}

function renderMd(text: string) {
  return marked.parse(text || '') as string
}

function formatRevTime(iso: string | undefined) {
  if (!iso || typeof iso !== 'string') return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

async function loadRoadmapRevisions() {
  if (!profile.value) return
  roadmapRevisionsLoading.value = true
  try {
    const { data } = await api.get('/english-learning/roadmap/revisions/', { params: { limit: 30 } })
    roadmapRevisions.value = Array.isArray(data) ? (data as RoadmapRevisionRow[]) : []
  } catch {
    roadmapRevisions.value = []
  } finally {
    roadmapRevisionsLoading.value = false
  }
}

function openRevisionPreview(row: RoadmapRevisionRow) {
  revisionPreview.value = row
  revisionPreviewVisible.value = true
}

function goKnowledgeDocument(row: RoadmapRevisionRow) {
  const kb = row.knowledge_base_id || profile.value?.default_kb_id
  if (!kb || !row.document_id) {
    ElMessage.warning('缺少知识库或文档 ID')
    return
  }
  router.push({
    path: '/knowledge',
    query: { kb: String(kb), document: String(row.document_id) }
  })
}

function placementChoiceFromKind(): 'quick' | 'full_test' {
  return assessmentKind.value === 'placement' ? 'quick' : 'full_test'
}

function applyNodeDataToForm(nd: Record<string, unknown>) {
  if (nd.assessment_id != null && String(nd.assessment_id)) {
    assessmentId.value = String(nd.assessment_id)
  }
  const items = nd.items
  if (Array.isArray(items) && items.length) {
    examItems.value = items as Array<{
      id: string
      stem: string
      choices?: string[]
      dimension?: string
    }>
    answers.value = {}
  }
  if (nd.gap_summary != null) {
    gapSummary.value = String(nd.gap_summary)
  }
  const weak = nd.weak_dimensions
  if (Array.isArray(weak)) {
    weakDimensions.value = weak.map(String)
    const picked = weakDimensions.value.filter((d) => dimensionOptions.includes(d))
    if (picked.length) focusDimensions.value = picked
  }
  if (nd.roadmap_markdown != null && String(nd.roadmap_markdown).trim()) {
    roadmapMarkdown.value = String(nd.roadmap_markdown)
  }
  const oj = nd.outline_json
  if (oj && typeof oj === 'object' && !Array.isArray(oj)) {
    roadmapOutlineJson.value = { ...(oj as Record<string, unknown>) }
  }
  if (nd.document_id != null && String(nd.document_id)) {
    finalizeResult.value = {
      document_id: String(nd.document_id),
      knowledge_base_id: String(nd.knowledge_base_id || profile.value?.default_kb_id || '')
    }
  }
  if (nd.revision_version != null) {
    void loadRoadmapRevisions()
  }
}

function routeStepFromWizardGraph(wg: WizardGraphState | null) {
  if (!wg) return
  if (wg.completed || wg.phase === 'tutor') {
    activeStep.value = 3
    return
  }
  const ha = wg.human_action
  if (wg.interrupted && ha?.kind === 'wait_input' && typeof ha.suggested_step === 'number' && ha.suggested_step > 0) {
    activeStep.value = ha.suggested_step
    return
  }
  const next = (wg.next_nodes || [])[0] || ''
  const pending = wg.pending_human_node || ''
  if (pending === 'placement_or_confirm' || next === 'assessment_run') {
    bootstrapDone.value = true
    activeStep.value = 1
    return
  }
  if (pending === 'assessment_run' || next === 'assessment_score') {
    activeStep.value = 1
    return
  }
  if (
    next === 'roadmap_draft_skill' ||
    next === 'roadmap_hitl' ||
    wg.phase === 'roadmap' ||
    wg.phase === 'roadmap_review'
  ) {
    activeStep.value = 2
    return
  }
  if (next === 'roadmap_finalize_skill' || pending === 'roadmap_draft_skill') {
    activeStep.value = 3
  }
}

async function syncWizardGraphResponse(data: GraphObservabilityPayload) {
  graphObservability.value = data
  wizardGraph.value = data.wizard_graph || null
  await loadExistingProfile()
  const nd = wizardGraph.value?.node_data
  if (nd && typeof nd === 'object') {
    applyNodeDataToForm(nd)
  }
  routeStepFromWizardGraph(wizardGraph.value)
}

async function postWizardStart(body: Record<string, unknown>) {
  const { data } = await api.post<GraphObservabilityPayload>(
    '/english-learning/graph/wizard/start/',
    body
  )
  return data
}

async function postWizardResume(body: Record<string, unknown>) {
  const { data } = await api.post<GraphObservabilityPayload>(
    '/english-learning/graph/wizard/resume/',
    body
  )
  return data
}

/** G3：SSE resume，返回最后一个带 wizard_graph 的事件 */
async function postWizardResumeStream(
  body: Record<string, unknown>,
  onEvent?: (ev: Record<string, unknown>) => void
): Promise<Record<string, unknown> | null> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`

  const resp = await fetch('/api/v1/english-learning/graph/wizard/resume/stream/', {
    method: 'POST',
    headers,
    body: JSON.stringify(body)
  })
  if (!resp.ok) {
    let data: Record<string, unknown> = {}
    try {
      data = (await resp.json()) as Record<string, unknown>
    } catch {
      /* ignore */
    }
    throw { response: { status: resp.status, data } }
  }
  const reader = resp.body?.getReader()
  if (!reader) return null

  const dec = new TextDecoder()
  let buf = ''
  let last: Record<string, unknown> | null = null

  const flushBlock = (block: string) => {
    const lines = block.split('\n')
    let eventType = 'message'
    const dataLines: string[] = []
    for (const line of lines) {
      if (line.startsWith('event:')) eventType = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (!dataLines.length) return
    try {
      const ev = JSON.parse(dataLines.join('\n')) as Record<string, unknown>
      ev._sse_type = eventType
      onEvent?.(ev)
      if (ev.wizard_graph || eventType === 'end' || eventType === 'interrupt') {
        last = ev
      }
    } catch {
      /* ignore malformed chunk */
    }
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    const parts = buf.split('\n\n')
    buf = parts.pop() || ''
    for (const p of parts) flushBlock(p)
  }
  if (buf.trim()) flushBlock(buf)
  return last
}

async function applyWizardStreamEnd(last: Record<string, unknown> | null) {
  const wg = (last?.wizard_graph || null) as WizardGraphState | null
  if (wg) {
    wizardGraph.value = wg
    const nd = wg.node_data
    if (nd && typeof nd === 'object') applyNodeDataToForm(nd)
    routeStepFromWizardGraph(wg)
  }
  await refreshGraphObservability()
  if (wg && graphObservability.value) {
    graphObservability.value = { ...graphObservability.value, wizard_graph: wg }
    wizardGraph.value = wg
  }
  await loadExistingProfile()
}

function onWizardStreamEvent(ev: Record<string, unknown>, fallbackLabel?: string) {
  if (ev.type === 'token') {
    const t = String(ev.text || '')
    if (t) {
      roadmapMarkdown.value += t
      wizardStreamProgress.value = fallbackLabel || '正在生成学习路线…'
    }
  } else if (ev.type === 'node_done') {
    wizardStreamProgress.value = String(ev.message || `节点 ${ev.node || ''} 完成`)
  } else if (ev.type === 'start') {
    wizardStreamProgress.value = fallbackLabel || '正在处理…'
  } else if (ev.type === 'error') {
    wizardStreamProgress.value = String(ev.error || '处理失败')
  }
}

/** G3：统一 SSE resume → 同步表单与图状态 */
async function wizardResumeViaStream(
  body: Record<string, unknown>,
  options?: { progressLabel?: string; onEvent?: (ev: Record<string, unknown>) => void }
): Promise<Record<string, unknown> | null> {
  wizardStreamProgress.value = options?.progressLabel || ''
  try {
    const last = await postWizardResumeStream(body, (ev) => {
      onWizardStreamEvent(ev, options?.progressLabel)
      options?.onEvent?.(ev)
    })
    const errMsg =
      (last?.error as string | undefined) ||
      ((last?.wizard_graph as WizardGraphState | undefined)?.last_error as string | undefined)
    if (last?.type === 'error' || last?._sse_type === 'error' || errMsg) {
      throw { response: { data: { error: errMsg || '向导流式处理失败' } } }
    }
    await applyWizardStreamEnd(last)
    return last
  } finally {
    wizardStreamProgress.value = ''
  }
}

function graphApiError(e: unknown, fallback: string) {
  const err = e as { response?: { status?: number; data?: { detail?: string; error?: string } } }
  if (err.response?.status === 503) {
    ElMessage.info(err.response?.data?.detail || '后端未安装 langgraph')
    return
  }
  ElMessage.error(err.response?.data?.detail || err.response?.data?.error || fallback)
}

async function refreshGraphObservability() {
  if (!profile.value) {
    graphObservability.value = null
    return
  }
  graphObsLoading.value = true
  try {
    const { data } = await api.get<GraphObservabilityPayload>('/english-learning/graph/status/')
    graphObservability.value = data
  } catch {
    graphObservability.value = null
  } finally {
    graphObsLoading.value = false
  }
}

async function doLanggraphSync() {
  if (!profile.value) return
  langgraphSyncLoading.value = true
  try {
    const { data } = await api.post<GraphObservabilityPayload>(
      '/english-learning/graph/langgraph-sync/',
      {}
    )
    graphObservability.value = data
    const sync = data.langgraph_sync as { advanced_steps?: number; target_cursor?: number } | undefined
    const n = sync?.advanced_steps ?? 0
    ElMessage.success(n > 0 ? `已推进 ${n} 步并与当前阶段对齐` : '图状态已与当前阶段一致')
  } catch (e: unknown) {
    const err = e as {
      response?: { status?: number; data?: { detail?: string; error?: string } }
    }
    if (err.response?.status === 503) {
      ElMessage.info(err.response?.data?.detail || '后端未安装 langgraph')
      return
    }
    ElMessage.error(err.response?.data?.detail || err.response?.data?.error || '同步失败')
  } finally {
    langgraphSyncLoading.value = false
  }
}

async function doWizardGraphStart() {
  if (!profile.value) return
  wizardGraphStartLoading.value = true
  try {
    const data = await postWizardStart({
      level_tags: levelTagsPayload(levelTag.value),
      exam_goal: examGoal.value,
      weekly_minutes: weeklyMinutes.value || 120,
      placement_choice: placementChoiceFromKind()
    })
    await syncWizardGraphResponse(data)
    const wg = wizardGraph.value
    ElMessage.success(
      wg?.interrupted
        ? `已暂停，下一步：${(wg?.next_nodes || []).join(', ') || '—'}`
        : '向导图已跑完'
    )
  } catch (e: unknown) {
    graphApiError(e, 'Start 失败')
  } finally {
    wizardGraphStartLoading.value = false
  }
}

async function doWizardGraphResume() {
  if (!profile.value) return
  wizardGraphResumeLoading.value = true
  try {
    const body: Record<string, unknown> = {
      placement_choice: placementChoiceFromKind(),
      focus_dimensions: focusDimensions.value.length
        ? [...focusDimensions.value]
        : ['grammar', 'vocabulary']
    }
    if (roadmapMarkdown.value?.trim()) {
      body.roadmap_markdown = roadmapMarkdown.value.trim()
    }
    const data = await postWizardResume(body)
    await syncWizardGraphResponse(data)
    const wg = wizardGraph.value
    ElMessage.success(`Resume：阶段 ${wg?.phase || '—'}`)
  } catch (e: unknown) {
    graphApiError(e, 'Resume 失败')
  } finally {
    wizardGraphResumeLoading.value = false
  }
}

async function doGraphRunChain() {
  if (!profile.value) return
  graphRunChainLoading.value = true
  try {
    const body: Record<string, unknown> = {
      level_tags: levelTagsPayload(levelTag.value),
      question_count: 2,
      auto_responses: true,
      focus_dimensions: focusDimensions.value.length
        ? [...focusDimensions.value]
        : ['grammar', 'vocabulary']
    }
    const { data } = await api.post<GraphObservabilityPayload & { chain?: { phase?: string } }>(
      '/english-learning/graph/run-chain/',
      body
    )
    graphObservability.value = data
    await loadExistingProfile()
    ElMessage.success(`节点链完成，阶段：${data.chain?.phase || '—'}`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string; failed_node?: string } } }
    const fn = err.response?.data?.failed_node
    ElMessage.error(
      (fn ? `[${fn}] ` : '') + (err.response?.data?.error || '节点链执行失败')
    )
  } finally {
    graphRunChainLoading.value = false
  }
}

async function doGraphRunNode() {
  const node = graphObservability.value?.current_node
  if (!profile.value || !node) {
    ElMessage.warning('请先刷新图状态以获取当前节点')
    return
  }
  graphRunNodeLoading.value = true
  try {
    const body: Record<string, unknown> = { node }
    if (node === 'assessment_score') {
      body.auto_responses = true
    }
    if (node === 'roadmap_draft_skill' && focusDimensions.value.length) {
      body.focus_dimensions = [...focusDimensions.value]
    }
    const { data } = await api.post<GraphObservabilityPayload>(
      '/english-learning/graph/run-node/',
      body
    )
    graphObservability.value = data
    await loadExistingProfile()
    ElMessage.success(`已执行节点：${node}`)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string; detail?: string } } }
    ElMessage.error(err.response?.data?.error || err.response?.data?.detail || '节点执行失败')
  } finally {
    graphRunNodeLoading.value = false
  }
}

async function doLanggraphAdvanceStep() {
  if (!profile.value) return
  langgraphAdvanceLoading.value = true
  try {
    const { data } = await api.post<GraphObservabilityPayload>(
      '/english-learning/graph/langgraph-advance/',
      {}
    )
    graphObservability.value = data
    if (data.langgraph_poc_completed) {
      ElMessage.success('LangGraph POC 已跑完全链')
    } else {
      const nxt = (data.langgraph_poc_next || [])[0]
      ElMessage.success(nxt ? `已推进至节点：${nxt}` : '已推进一步')
    }
  } catch (e: unknown) {
    const err = e as {
      response?: { status?: number; data?: { detail?: string; error?: string } }
    }
    if (err.response?.status === 503) {
      ElMessage.info(err.response?.data?.detail || '后端未安装 langgraph')
      return
    }
    ElMessage.error(err.response?.data?.detail || err.response?.data?.error || '推进失败')
  } finally {
    langgraphAdvanceLoading.value = false
  }
}

async function doLanggraphPocStep() {
  if (!profile.value) return
  langgraphPocLoading.value = true
  try {
    const { data } = await api.post<GraphObservabilityPayload>('/english-learning/graph/langgraph-poc/', {})
    graphObservability.value = data
    ElMessage.success('LangGraph POC 已执行')
  } catch (e: unknown) {
    const err = e as {
      response?: { status?: number; data?: { detail?: string; error?: string } }
    }
    if (err.response?.status === 503) {
      ElMessage.info(err.response?.data?.detail || '后端未安装 langgraph')
      return
    }
    ElMessage.error(err.response?.data?.detail || err.response?.data?.error || '执行失败')
  } finally {
    langgraphPocLoading.value = false
  }
}

async function doLanggraphReset() {
  if (!profile.value) return
  langgraphResetLoading.value = true
  try {
    const { data } = await api.post<GraphObservabilityPayload>('/english-learning/graph/langgraph-reset/', {})
    graphObservability.value = data
    ElMessage.success('LangGraph 线程已重置')
  } catch (e: unknown) {
    const err = e as {
      response?: { status?: number; data?: { detail?: string; error?: string } }
    }
    if (err.response?.status === 503) {
      ElMessage.info(err.response?.data?.detail || '后端未安装 langgraph')
      return
    }
    ElMessage.error(err.response?.data?.detail || err.response?.data?.error || '重置失败')
  } finally {
    langgraphResetLoading.value = false
  }
}

async function openLanggraphHistoryDialog() {
  langgraphHistoryVisible.value = true
  langgraphHistoryLoading.value = true
  langgraphHistoryJson.value = ''
  try {
    const { data } = await api.get('/english-learning/graph/langgraph-history/', { params: { limit: 30 } })
    langgraphHistoryJson.value = JSON.stringify(data, null, 2)
  } catch (e: unknown) {
    const err = e as {
      response?: { status?: number; data?: { detail?: string; error?: string } }
    }
    if (err.response?.status === 503) {
      langgraphHistoryJson.value = JSON.stringify(
        { error: err.response?.data?.error, detail: err.response?.data?.detail },
        null,
        2
      )
      return
    }
    langgraphHistoryJson.value = JSON.stringify(
      { error: err.response?.data?.error || 'request_failed', detail: err.response?.data?.detail },
      null,
      2
    )
  } finally {
    langgraphHistoryLoading.value = false
  }
}

async function refreshToday() {
  try {
    const { data } = await api.get('/english-learning/today/')
    todayTasks.value = (data.tasks || []) as TodayTask[]
    todayPhase.value = String(data.phase || '')
    todayBlackboard.value = data.blackboard || {}
    const pack = data.recall_pack as { pack_items?: typeof recallPackItems.value } | null
    recallPackItems.value = Array.isArray(pack?.pack_items) ? pack.pack_items : []
    const prefs = data.reminder_prefs as {
      do_not_disturb?: boolean
      intensity?: string
      quiet_hours_active?: boolean
      quiet_hours?: { enabled?: boolean; start?: string; end?: string }
    } | null
    if (prefs) {
      reminderDoNotDisturb.value = !!prefs.do_not_disturb
      todayQuietHoursActive.value = !!prefs.quiet_hours_active
      if (prefs.intensity === 'low' || prefs.intensity === 'normal' || prefs.intensity === 'high') {
        reminderIntensity.value = prefs.intensity
      }
      quietHoursEnabled.value = !!prefs.quiet_hours?.enabled
      if (prefs.quiet_hours?.start && typeof prefs.quiet_hours.start === 'string') {
        quietHoursStart.value = prefs.quiet_hours.start
      }
      if (prefs.quiet_hours?.end && typeof prefs.quiet_hours.end === 'string') {
        quietHoursEnd.value = prefs.quiet_hours.end
      }
    }
    const recKb = data.recommended_curriculum_kb_id
    if (recKb != null && String(recKb).trim()) {
      recommendedCurriculumKbId.value = String(recKb).trim()
    }
  } catch {
    todayTasks.value = []
  }
}

async function doDrillTouch() {
  drillLoading.value = true
  try {
    await api.post('/english-learning/drill-touch/', {})
    await refreshToday()
    ElMessage.success('已记录巩固时间')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { error?: string } } }
    ElMessage.error(err.response?.data?.error || '记录失败')
  } finally {
    drillLoading.value = false
  }
}

function goTodayChat(t: TodayTask) {
  const query: Record<string, string> = {
    agent: 'english_orchestrator',
    english_phase: 'tutor'
  }
  if (profile.value?.id != null) {
    query.english_profile_id = String(profile.value.id)
  }
  const rec = recommendedCurriculumKbId.value
  if (rec) query.kb = rec
  else if (profile.value?.default_kb_id) query.kb = String(profile.value.default_kb_id)
  if (t.english_delegate) query.english_delegate = t.english_delegate
  router.push({ path: '/chat', query })
}

const WIZARD_STEP_TITLES = ['开始', '做一套题', '互动反馈', '学习报告']

/** 今日任务 CTA：打开弹窗向导并定位步骤 */
async function goTodayStep(t: TodayTask) {
  const step = Number(t.cta_step)
  if (!Number.isFinite(step) || step < 0 || step > 3) {
    ElMessage.warning('该任务暂无可跳转的步骤')
    return
  }
  openSetupWizard(step)
  await nextTick()
  const title = WIZARD_STEP_TITLES[step] || `步骤 ${step}`
  ElMessage.success(`已打开「${title}」设置`)
}

function levelTargetFromTags(): string {
  return inferAssessmentLevelFromTags(levelTagsPayload(levelTag.value))
}

async function loadExistingProfile() {
  try {
    const { data } = await api.get('/english-learning/profile/')
    profile.value = data
    if (typeof data.session_state_version === 'number') {
      sessionStateVersion.value = data.session_state_version
    } else if (data.session_state_version != null) {
      const n = parseInt(String(data.session_state_version), 10)
      sessionStateVersion.value = Number.isFinite(n) ? n : 0
    } else {
      sessionStateVersion.value = 0
    }
    const st = data.session_state as { bootstrap_completed?: boolean } | undefined
    if (st?.bootstrap_completed) {
      bootstrapDone.value = true
    }
    if (Array.isArray(data.level_tags) && data.level_tags.length) {
      levelTag.value = pickPrimaryLevelTag(data.level_tags as string[])
    }
    restoreWizardProgressFromSessionState(data.session_state as Record<string, unknown> | undefined)
    await refreshGraphObservability()
  } catch {
    /* 未登录或网络错误 */
    graphObservability.value = null
  }
}

async function saveReminderPrefs() {
  reminderPrefsSaving.value = true
  try {
    const { data } = await api.patch('/english-learning/profile/', {
      session_state: {
        reminder_prefs: {
          do_not_disturb: reminderDoNotDisturb.value,
          intensity: reminderIntensity.value,
          quiet_hours: {
            enabled: quietHoursEnabled.value,
            start: quietHoursStart.value,
            end: quietHoursEnd.value
          }
        }
      },
      session_state_version: sessionStateVersion.value
    })
    profile.value = data
    if (typeof data.session_state_version === 'number') {
      sessionStateVersion.value = data.session_state_version
    }
    ElMessage.success('提醒设置已保存')
    await refreshToday()
    void refreshGraphObservability()
  } catch (e: unknown) {
    const err = e as {
      response?: { status?: number; data?: { detail?: string; session_state_version?: number } }
    }
    if (err.response?.status === 409) {
      ElMessage.warning('档案已在别处更新，已为你刷新页面上的版本号。请确认后再次保存。')
      await loadExistingProfile()
      await refreshToday()
      return
    }
    ElMessage.error(err.response?.data?.detail || '保存失败')
  } finally {
    reminderPrefsSaving.value = false
  }
}

async function doBootstrap() {
  levelTag.value = DEFAULT_LEVEL_TAG
  if (!String(examGoal.value || '').trim()) examGoal.value = DEFAULT_EXAM_GOAL
  loading.value = true
  finalizeResult.value = null
  examItems.value = []
  assessmentId.value = null
  try {
    if (graphWizardMode.value) {
      const data = await postWizardStart({
        level_tags: levelTagsPayload(DEFAULT_LEVEL_TAG),
        exam_goal: examGoal.value || DEFAULT_EXAM_GOAL,
        weekly_minutes: weeklyMinutes.value,
        placement_choice: placementChoiceFromKind()
      })
      await syncWizardGraphResponse(data)
      bootstrapSummary.value = '四级诊断已启动'
      bootstrapDone.value = true
      const wg = wizardGraph.value
      ElMessage.success(
        wg?.interrupted
          ? '已锁定四级，请继续做题'
          : '向导图流程已完成'
      )
    } else {
      const { data } = await api.post('/english-learning/profile/bootstrap/', {
        level_tags: levelTagsPayload(DEFAULT_LEVEL_TAG),
        exam_goal: examGoal.value || DEFAULT_EXAM_GOAL,
        weekly_minutes: weeklyMinutes.value
      })
      profile.value = data.profile
      if (typeof data.profile?.session_state_version === 'number') {
        sessionStateVersion.value = data.profile.session_state_version
      }
      bootstrapSummary.value = String(data.skill?.summary_for_user || '')
      bootstrapDone.value = true
      ElMessage.success('四级档案已就绪')
      await refreshGraphObservability()
    }
    await refreshToday()
  } catch (e: unknown) {
    graphApiError(e, '启动失败')
  } finally {
    loading.value = false
  }
}

/** Step0 一键：建档（若需）并进入做题 */
async function doBootstrapAndGoExam() {
  if (!bootstrapDone.value || !profile.value) {
    await doBootstrap()
    if (!bootstrapDone.value) return
  }
  activeStep.value = 1
}

async function doStartAssessment() {
  if (!profile.value) {
    ElMessage.warning('请先建档')
    return
  }
  loading.value = true
  try {
    if (graphWizardMode.value) {
      await wizardResumeViaStream(
        {
          placement_choice: placementChoiceFromKind(),
          kind: assessmentKind.value,
          level_target: levelTargetFromTags(),
          question_count: assessmentKind.value === 'placement' ? 3 : 5
        },
        { progressLabel: '正在组卷…' }
      )
      const wg = wizardGraph.value
      if (!examItems.value.length) {
        ElMessage.warning('组卷未返回题目，请查看图状态' + (wizardDevMode.value ? '或改用经典 REST' : ''))
      } else {
        ElMessage.success(wg?.interrupted ? '已组卷，请作答' : '测评阶段已推进')
      }
    } else {
      const start = await api.post('/english-learning/assessment/start/', {
        kind: assessmentKind.value,
        level_target: levelTargetFromTags(),
        question_count: assessmentKind.value === 'placement' ? 3 : 5
      })
      assessmentId.value = start.data.assessment_id
      examItems.value = start.data.items || []
      answers.value = {}
      ElMessage.success('已组卷，请作答')
      await refreshGraphObservability()
    }
    await refreshToday()
  } catch (e: unknown) {
    graphApiError(e, '组卷失败')
  } finally {
    loading.value = false
  }
}

/** 测评页返回：有题目时清空本题卷回到「开始组卷」；否则回到建档页 */
function goBackAssessment() {
  if (examItems.value.length) {
    examItems.value = []
    assessmentId.value = null
    answers.value = {}
    ElMessage.info('已退出本题卷，可重新组卷或返回修改档案')
    return
  }
  activeStep.value = 0
}

async function doSubmitExam() {
  if (!graphWizardMode.value && !assessmentId.value) return
  loading.value = true
  try {
    const responses = examItems.value.map((q) => ({
      item_id: q.id,
      answer: answers.value[q.id]
    }))
    if (graphWizardMode.value) {
      await wizardResumeViaStream(
        {
          responses,
          assessment_id: assessmentId.value || undefined
        },
        { progressLabel: '正在评分…' }
      )
      if (!focusDimensions.value.length) {
        focusDimensions.value = ['vocabulary', 'grammar']
      }
      const wg = wizardGraph.value
      ElMessage.success(
        wg?.interrupted && (wg.next_nodes || []).includes('roadmap_draft_skill')
          ? '评分完成，请确认加强维度并生成路线'
          : '评分完成'
      )
    } else {
      const { data } = await api.post(
        `/english-learning/assessment/${assessmentId.value}/submit/`,
        { responses }
      )
      gapSummary.value = data.gap_summary || ''
      const weak = (data.weak_dimensions || []) as string[]
      weakDimensions.value = weak
      focusDimensions.value = weak.filter((d) => dimensionOptions.includes(d))
      if (!focusDimensions.value.length) {
        focusDimensions.value = ['vocabulary', 'grammar']
      }
      roadmapMarkdown.value = ''
      activeStep.value = 2
      ElMessage.success('评分完成')
      await refreshGraphObservability()
    }
    await refreshToday()
  } catch (e: unknown) {
    graphApiError(e, '提交失败')
  } finally {
    loading.value = false
  }
}

async function doRoadmapDraft() {
  loading.value = true
  wizardStreamProgress.value = ''
  if (graphWizardMode.value) {
    roadmapMarkdown.value = ''
  }
  try {
    if (graphWizardMode.value) {
      await wizardResumeViaStream(
        {
          focus_dimensions: focusDimensions.value,
          assessment_id: assessmentId.value || undefined,
          learner_note: learnerNote.value.trim() || undefined
        },
        { progressLabel: '正在生成学习报告…' }
      )
      if (!roadmapMarkdown.value) ElMessage.warning('报告为空，请检查后端日志')
      else {
        const wg = wizardGraph.value
        const hint = wg?.human_action?.title
        ElMessage.success(
          hint ||
            (wg?.interrupted ? '学习报告已生成，可在下一步确认保存' : '报告阶段已推进')
        )
      }
    } else {
      const { data } = await api.post('/english-learning/roadmap/draft/', {
        assessment_id: assessmentId.value,
        focus_dimensions: focusDimensions.value,
        learner_note: learnerNote.value.trim() || undefined
      })
      roadmapMarkdown.value = data.roadmap_markdown || ''
      const oj = data.outline_json
      roadmapOutlineJson.value =
        oj && typeof oj === 'object' && !Array.isArray(oj) ? { ...(oj as Record<string, unknown>) } : {}
      if (!roadmapMarkdown.value) ElMessage.warning('报告为空，请检查后端日志')
      else ElMessage.success('学习报告已生成')
      await refreshGraphObservability()
    }
    await refreshToday()
  } catch (e: unknown) {
    graphApiError(e, '生成路线失败')
  } finally {
    loading.value = false
  }
}

async function doSaveRoadmapDraft() {
  const md = (roadmapMarkdown.value || '').trim()
  if (!md) {
    ElMessage.warning('路线正文为空')
    return
  }
  draftSaveLoading.value = true
  try {
    if (graphWizardMode.value) {
      await wizardResumeViaStream(
        {
          roadmap_markdown: roadmapMarkdown.value,
          outline_json:
            Object.keys(roadmapOutlineJson.value).length > 0 ? roadmapOutlineJson.value : undefined
        },
        { progressLabel: '正在保存路线草稿…' }
      )
      ElMessage.success('路线草稿已写入图状态')
      await refreshToday()
      return
    }
    const body: Record<string, unknown> = {
      roadmap_markdown: roadmapMarkdown.value,
      session_state_version: sessionStateVersion.value
    }
    if (Object.keys(roadmapOutlineJson.value).length > 0) {
      body.outline_json = roadmapOutlineJson.value
    }
    const { data } = await api.post('/english-learning/roadmap/save-draft/', body)
    if (typeof data.session_state_version === 'number') {
      sessionStateVersion.value = data.session_state_version
    }
    const r = data.roadmap_hitl_rounds
    ElMessage.success(typeof r === 'number' ? `草稿已保存（第 ${r} 轮修订）` : '草稿已保存')
    await refreshToday()
    void refreshGraphObservability()
  } catch (e: unknown) {
    const err = e as { response?: { status?: number; data?: { detail?: string } } }
    if (err.response?.status === 409) {
      ElMessage.warning('档案版本冲突，正在刷新…')
      await loadExistingProfile()
      await refreshToday()
      return
    }
    ElMessage.error(err.response?.data?.detail || '保存草稿失败')
  } finally {
    draftSaveLoading.value = false
  }
}

async function doFinalize() {
  const kb = profile.value?.default_kb_id
  if (!kb) {
    ElMessage.error('缺少默认知识库，请重新建档')
    return
  }
  loading.value = true
  try {
    if (graphWizardMode.value) {
      await wizardResumeViaStream(
        {
          roadmap_markdown: roadmapMarkdown.value,
          knowledge_base_id: kb,
          title: finalizeTitle.value || DEFAULT_ROADMAP_TITLE
        },
        { progressLabel: '正在定稿入库…' }
      )
      if (wizardGraph.value?.completed) {
        ElMessage.success('已定稿入库（图向导完成）')
      } else {
        ElMessage.warning(wizardGraph.value?.last_error || '定稿未完全结束，请查看图状态')
      }
      await refreshToday()
      await loadRoadmapRevisions()
      return
    }
    const { data } = await api.post('/english-learning/roadmap/finalize/', {
      roadmap_markdown: roadmapMarkdown.value,
      knowledge_base_id: kb,
      title: finalizeTitle.value || DEFAULT_ROADMAP_TITLE,
      session_state_version: sessionStateVersion.value
    })
    if (typeof data.session_state_version === 'number') {
      sessionStateVersion.value = data.session_state_version
    }
    finalizeResult.value = {
      document_id: data.document_id,
      knowledge_base_id: data.knowledge_base_id
    }
    ElMessage.success('已定稿入库')
    await refreshToday()
    await loadRoadmapRevisions()
    void refreshGraphObservability()
  } catch (e: unknown) {
    const err = e as {
      response?: { status?: number; data?: { error?: string; detail?: string } }
    }
    if (err.response?.status === 409) {
      ElMessage.warning('档案版本冲突，正在刷新…')
      await loadExistingProfile()
      await refreshToday()
      return
    }
    ElMessage.error(
      err.response?.data?.detail || err.response?.data?.error || '定稿失败'
    )
  } finally {
    loading.value = false
  }
}

function goChat() {
  const kb = finalizeResult.value?.knowledge_base_id || profile.value?.default_kb_id
  if (!kb) {
    router.push('/chat')
    return
  }
  const query: Record<string, string> = {
    kb: String(kb),
    agent: 'english_orchestrator',
    english_phase: 'tutor'
  }
  if (profile.value?.id != null) {
    query.english_profile_id = String(profile.value.id)
  }
  router.push({ path: '/chat', query })
}

watch(activeStep, (s) => {
  if (s === 3) void loadRoadmapRevisions()
})

function shouldAutoOpenSetupWizard(): boolean {
  const q = route.query.setup
  if (q === '1' || q === 'true') return true
  if (todayPhase.value === 'tutor') return false
  if (wizardGraph.value?.interrupted) return true
  return false
}

onMounted(async () => {
  await loadExistingProfile()
  await refreshToday()
  restoreWizardProgressFromSessionState(profile.value?.session_state as Record<string, unknown> | undefined)
  if (graphWizardMode.value && profile.value) {
    await refreshGraphObservability()
    if (graphObservability.value?.wizard_graph) {
      wizardGraph.value = { ...graphObservability.value.wizard_graph }
      const nd = wizardGraph.value?.node_data
      if (nd && typeof nd === 'object' && Object.keys(nd).length) {
        applyNodeDataToForm(nd)
      }
      routeStepFromWizardGraph(wizardGraph.value)
    }
  }
  if (activeStep.value === 3) void loadRoadmapRevisions()
  if (shouldAutoOpenSetupWizard()) {
    openSetupWizard(activeStep.value)
  }
})
</script>

<style scoped>
.el-wizard {
  min-height: 100%;
}
.wiz-head h2 {
  margin: 0 0 4px;
  font-size: 1.35rem;
}
.wiz-sub {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 0.9rem;
}
.wiz-card {
  margin-top: 12px;
}
.graph-mode-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 16px;
}
.graph-mode-alert {
  margin: 0;
}
.graph-stream-hint {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
}
.hint-inline {
  margin-left: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.today-card {
  margin-bottom: 20px;
}
.hub-pause-alert {
  margin-bottom: 16px;
}
.hub-pause-btn {
  margin-left: 8px;
  vertical-align: baseline;
}
.wizard-hub-cta {
  margin-top: 4px;
  padding: 20px 22px;
  border-radius: 12px;
  border: 1px solid var(--el-color-primary-light-7);
  background: linear-gradient(135deg, var(--el-color-primary-light-9) 0%, var(--el-fill-color-blank) 100%);
}
.hub-cta-inner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.hub-cta-text h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}
.hub-progress {
  margin-top: 16px;
}
.wiz-setup-dialog :deep(.el-dialog__body) {
  max-height: min(72vh, 680px);
  overflow-y: auto;
  padding-top: 4px;
}
.wiz-dialog-intro {
  margin: 0 0 14px;
  font-size: 0.9rem;
  color: var(--el-text-color-secondary);
}
.wiz-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.form-field-hint {
  margin: 0 0 8px;
}
.graph-mode-bar--dialog {
  margin-bottom: 14px;
}
.prefs-collapse {
  margin-top: 12px;
}
.prefs-card {
  margin-bottom: 20px;
}
.graph-obs-collapse {
  margin-bottom: 20px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  overflow: hidden;
}
.mt-tight {
  margin-top: 8px;
}
.graph-obs-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.prefs-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 10px;
}
.prefs-row-top {
  align-items: flex-start;
}
.prefs-label {
  min-width: 88px;
  color: var(--el-text-color-regular);
  font-size: 0.9rem;
}
.warn-hint {
  color: var(--el-color-warning);
  margin-left: 4px;
}
.time-pair {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.time-sep {
  color: var(--el-text-color-secondary);
  font-size: 0.85rem;
}
.today-header-row {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
}
.today-head {
  font-weight: 600;
}
.today-phase {
  font-size: 0.85rem;
  color: var(--el-text-color-secondary);
  font-weight: normal;
}
.today-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.today-item {
  margin-bottom: 16px;
}
.today-item:last-child {
  margin-bottom: 0;
}
.tight-p {
  margin: 6px 0 8px;
}
.today-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.recall-pack {
  padding-top: 4px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.recall-title {
  margin: 0 0 8px;
  font-size: 0.95rem;
}
.recall-ol {
  margin: 0;
  padding-left: 1.2rem;
}
.recall-li {
  margin-bottom: 10px;
}
.wiz-steps {
  margin-bottom: 28px;
}
.wiz-panel {
  max-width: 720px;
  margin: 0 auto;
}
.wiz-form {
  max-width: 560px;
  margin-bottom: 16px;
}
.q-block {
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.q-stem {
  margin: 0 0 10px;
  line-height: 1.5;
}
.q-choices {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
}
.wiz-actions {
  margin-top: 20px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.hint {
  color: var(--el-text-color-secondary);
  font-size: 0.88rem;
}
.gap-alert {
  margin-bottom: 16px;
}
.gap-pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: inherit;
  font-size: 0.9rem;
}
.mt {
  margin-top: 20px;
}
.roadmap-preview {
  padding: 12px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
  max-height: 360px;
  overflow: auto;
}
.roadmap-ta {
  font-family: ui-monospace, monospace;
  font-size: 13px;
}
.wiz-row {
  display: flex;
  gap: 12px;
  align-items: center;
}
.result-meta {
  margin: 4px 0;
  font-size: 0.88rem;
  color: var(--el-text-color-secondary);
}
.bootstrap-sum {
  margin: 0 0 8px;
  white-space: pre-wrap;
  font-size: 0.92rem;
}
.revisions-block {
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
}
.revisions-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}
.revisions-title {
  font-weight: 600;
  font-size: 0.95rem;
}
.revisions-table {
  width: 100%;
}
.rev-doc-id {
  font-size: 11px;
  word-break: break-all;
}
.rev-preview-body {
  max-height: 60vh;
  overflow: auto;
}
.lg-hist-pre {
  margin: 0;
  max-height: 70vh;
  overflow: auto;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, monospace;
}
.tight {
  margin-top: 8px;
  margin-bottom: 0;
}
</style>
