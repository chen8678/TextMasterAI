<template>
  <div class="knowledge-container">
    <!-- 顶部导航 -->
    <el-header class="knowledge-header">
      <div class="header-content">
        <div class="header-left">
          <BrandMark class="header-logo" :size="42" padded circular />
          <el-button @click="goBack" class="back-button">
            <AppleIcon name="arrow-left" :size="16" />
          </el-button>
          <div class="header-title">
            <h2>知识库管理</h2>
            <p>管理和组织您的专业知识库</p>
            <p class="header-hint">系统预置英语词库（小学→六级）只读可用；个人「英语学习 · …」库用于保存学习路线定稿。</p>
          </div>
        </div>
        <div class="header-actions">
          <el-button type="primary" @click="showCreateDialog = true" class="create-button">
            <AppleIcon name="plus" :size="16" />
            创建知识库
          </el-button>
        </div>
      </div>
    </el-header>

    <!-- 主要内容 -->
    <el-main class="knowledge-main">
      <PageScaffold>
        <template #toolbar>
          <KnowledgeFilterBar>
            <div class="kb-filters">
              <el-input
                v-model="filterKeyword"
                placeholder="按名称/描述搜索知识库"
                clearable
                class="filter-input"
              />
              <el-select v-model="filterCategory" clearable placeholder="分类" class="filter-select">
                <el-option label="全部分类" value="" />
                <el-option label="通用" value="general" />
                <el-option label="法律" value="legal" />
                <el-option label="教育" value="education" />
                <el-option label="医疗健康" value="healthcare" />
                <el-option label="金融" value="finance" />
                <el-option label="技术" value="technology" />
                <el-option label="商业" value="business" />
                <el-option label="科学" value="science" />
                <el-option label="人文社科" value="humanities" />
                <el-option label="工程" value="engineering" />
                <el-option label="艺术设计" value="arts" />
                <el-option label="其他" value="other" />
              </el-select>
              <el-select v-model="filterSort" placeholder="排序" class="filter-select">
                <el-option label="最近创建" value="created_desc" />
                <el-option label="最早创建" value="created_asc" />
                <el-option label="文档数从多到少" value="docs_desc" />
                <el-option label="文档数从少到多" value="docs_asc" />
                <el-option label="名称 A-Z" value="title_asc" />
              </el-select>
              <el-button @click="resetFilters">重置筛选</el-button>
            </div>
            <template #extra>
              <div class="kb-filter-summary">
                共 {{ knowledgeBases.length }} 个知识库，筛选后 {{ filteredKnowledgeBases.length }} 个
              </div>
            </template>
          </KnowledgeFilterBar>
        </template>

        <div class="knowledge-list">
          <el-card
            v-for="kb in filteredKnowledgeBases"
            :key="kb.id"
            class="kb-card"
            @click="viewKnowledgeBase(kb)"
          >
          <div class="kb-header">
            <div class="kb-icon">
              <AppleIcon name="folder" :size="22" />
            </div>
            <div class="kb-info">
              <h3>{{ kb.title }}</h3>
              <p class="kb-description">{{ kb.description || '暂无描述' }}</p>
            </div>
            <el-dropdown
              v-if="isKbEditable(kb)"
              @command="(command: string) => handleCommand(command, kb)"
              @click.stop
            >
              <el-button type="text" class="more-button">
                <AppleIcon name="more" :size="16" />
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">编辑</el-dropdown-item>
                  <el-dropdown-item command="upload">上传文档</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
            <el-tag v-else-if="kb.is_system_curriculum" size="small" type="info">系统预置 · 只读</el-tag>
            <el-tag v-else-if="isPersonalEnglishKb(kb)" size="small" type="success">个人路线库</el-tag>
          </div>
          <div class="kb-meta">
            <div class="kb-tags">
              <el-tag :type="getCategoryType(kb.category)" size="small">{{ getCategoryName(kb.category) }}</el-tag>
            </div>
            <div class="kb-stats">
              <span class="kb-count">
                <AppleIcon name="document" :size="16" />
                {{ kb.document_count }} 个文档
              </span>
              <span class="kb-date">{{ formatDate(kb.created_at) }}</span>
            </div>
          </div>
          
          <!-- 操作按钮组 -->
          <div class="kb-actions">
            <div class="action-row">
              <el-button 
                type="info" 
                size="small" 
                @click.stop="viewDocuments(kb)" 
                class="action-btn"
              >
                <AppleIcon name="document" :size="14" />
                查看文档
              </el-button>
            </div>
          </div>
          </el-card>
        </div>
        <template #feedback>
          <el-empty v-if="filteredKnowledgeBases.length === 0" description="没有匹配的知识库，请调整筛选条件" />
        </template>
      </PageScaffold>
    </el-main>

    <!-- 创建知识库对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="创建知识库"
      width="500px"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        :rules="createRules"
        label-width="80px"
      >
        <el-form-item label="标题" prop="title">
          <el-input v-model="createForm.title" placeholder="请输入知识库标题" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="createForm.description"
            type="textarea"
            placeholder="请输入知识库描述"
            :rows="3"
          />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="createForm.category" placeholder="请选择分类">
            <el-option label="通用" value="general" />
            <el-option label="法律" value="legal" />
            <el-option label="教育" value="education" />
            <el-option label="医疗健康" value="healthcare" />
            <el-option label="金融" value="finance" />
            <el-option label="技术" value="technology" />
            <el-option label="商业" value="business" />
            <el-option label="科学" value="science" />
            <el-option label="人文社科" value="humanities" />
            <el-option label="工程" value="engineering" />
            <el-option label="艺术设计" value="arts" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- 编辑知识库对话框 -->
    <el-dialog
      v-model="showEditDialog"
      title="编辑知识库"
      width="500px"
    >
      <el-form
        ref="editFormRef"
        :model="editForm"
        :rules="createRules"
        label-width="80px"
      >
        <el-form-item label="标题" prop="title">
          <el-input v-model="editForm.title" placeholder="请输入知识库标题" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="editForm.description"
            type="textarea"
            placeholder="请输入知识库描述"
            :rows="3"
          />
        </el-form-item>
        <el-form-item label="分类" prop="category">
          <el-select v-model="editForm.category" placeholder="请选择分类">
            <el-option label="通用" value="general" />
            <el-option label="法律" value="legal" />
            <el-option label="教育" value="education" />
            <el-option label="医疗健康" value="healthcare" />
            <el-option label="金融" value="finance" />
            <el-option label="技术" value="technology" />
            <el-option label="商业" value="business" />
            <el-option label="科学" value="science" />
            <el-option label="人文社科" value="humanities" />
            <el-option label="工程" value="engineering" />
            <el-option label="艺术设计" value="arts" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleEdit" :loading="editing">
          更新
        </el-button>
      </template>
    </el-dialog>

    <!-- 上传文档对话框 -->
    <el-dialog
      v-model="showUploadDialog"
      :title="uploadMode === 'file' ? '上传文档' : '导入 JSON 文档'"
      width="520px"
    >
      <el-form
        ref="uploadFormRef"
        :model="uploadForm"
        label-width="100px"
      >
        <el-form-item label="上传方式">
          <el-radio-group v-model="uploadMode">
            <el-radio-button label="file">单文件</el-radio-button>
            <el-radio-button label="json">JSON 导入</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="uploadMode === 'file'" label="选择文件">
          <div class="file-upload-container">
            <el-upload
              :auto-upload="false"
              :on-change="handleFileChange"
              :show-file-list="true"
              :limit="1"
              accept=".pdf,.doc,.docx,.txt,.md,.json"
              drag
            >
              <AppleIcon name="upload" :size="24" />
              <div class="el-upload__text">
                将文件拖到此处，或<em>点击上传</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 PDF、Word、TXT、Markdown、JSON；单文件最大 {{ formatFileSize(uploadLimits.max_file_bytes) }}，大于 {{
                    formatFileSize(uploadLimits.chunk_max_bytes)
                  }} 时自动分片上传。选择 SCAR 领域后将对 JSON 做结构编译。
                </div>
              </template>
            </el-upload>
            
            <!-- 备选方案：简单的文件选择 -->
            <div class="simple-file-input">
              <input
                type="file"
                ref="fileInput"
                @change="handleSimpleFileChange"
                accept=".pdf,.doc,.docx,.txt,.md,.json"
                style="display: none"
              />
              <el-button @click="triggerFileInput" type="primary" plain>
                <AppleIcon name="upload" :size="16" />
                选择文件
              </el-button>
              <span v-if="uploadForm.file" class="selected-file">
                已选择: {{ uploadForm.file.name }}
              </span>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="SCAR 领域">
          <el-select v-model="uploadForm.scar_domain" clearable placeholder="无（不编译）" style="width: 100%">
            <el-option label="无（普通文档）" value="" />
            <el-option label="construction（工地/建筑 JSON）" value="construction" />
          </el-select>
          <div class="el-upload__tip">上传 construction JSON（如 site_A.json）时请选择对应领域以触发结构编译。</div>
        </el-form-item>

        <el-form-item v-if="uploadMode === 'json'" label="JSON 文件">
          <el-upload
            :auto-upload="false"
            :on-change="handleJsonFileChange"
            :show-file-list="true"
            :limit="1"
            accept=".json"
            drag
          >
            <AppleIcon name="upload" :size="24" />
            <div class="el-upload__text">
              拖拽 JSON 到此或 <em>点击上传</em>
            </div>
            <div class="el-upload__tip">单个 JSON 文件 ≤ 100MB，结构需包含 documents 数组</div>
          </el-upload>
        </el-form-item>

        <el-form-item v-if="uploadMode === 'json'" label="结构示例">
          <div class="json-tip">
            <pre>{
  "documents": [
    {"title": "示例 1", "content": "内容...", "metadata": {"source": "dataset"}},
    {"content": "只提供 content 也可以"}
  ]
}</pre>
          </div>
        </el-form-item>
      </el-form>
      <p v-if="uploadMode === 'file' && uploadProgressLabel" class="upload-progress-hint">{{ uploadProgressLabel }}</p>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button
          v-if="uploadMode === 'file'"
          type="primary"
          @click="handleUpload"
          :loading="uploading"
        >
          上传
        </el-button>
        <el-button
          v-else
          type="primary"
          @click="handleJsonImport"
          :loading="jsonUploading"
        >
          导入 JSON
        </el-button>
      </template>
    </el-dialog>

    <!-- JSON 导入进度对话框 -->
    <el-dialog
      v-model="showImportProgressDialog"
      title="JSON 导入进度"
      width="500px"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      :show-close="false"
    >
      <div class="import-progress-content">
        <el-progress
          :percentage="importProgress.percentage"
          :status="importProgress.status === 'FAILED' ? 'exception' : (importProgress.status === 'SUCCEEDED' ? 'success' : undefined)"
          :stroke-width="12"
        />
        <div class="progress-stats">
          <div class="stat-item">
            <span class="stat-label">状态：</span>
            <el-tag :type="getImportStatusType(importProgress.status)">
              {{ getImportStatusText(importProgress.status) }}
            </el-tag>
          </div>
          <div class="stat-item">
            <span class="stat-label">总数：</span>
            <span>{{ importProgress.total }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">已创建：</span>
            <span class="text-success">{{ importProgress.created }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">已向量化：</span>
            <span class="text-primary">{{ importProgress.vectorized }}</span>
          </div>
          <div class="stat-item">
            <span class="stat-label">已跳过：</span>
            <span class="text-warning">{{ importProgress.skipped }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button
          v-if="!['SUCCEEDED', 'FAILED', 'CANCELED'].includes(importProgress.status)"
          @click="cancelImportJob"
        >
          取消任务
        </el-button>
        <el-button
          type="primary"
          @click="showImportProgressDialog = false"
          :disabled="!['SUCCEEDED', 'FAILED', 'CANCELED'].includes(importProgress.status)"
        >
          关闭
        </el-button>
      </template>
    </el-dialog>

    <!-- 文档查看对话框 -->
    <el-dialog
      v-model="showDocumentsDialog"
      :title="selectedKB?.title + ' - 文档列表'"
      width="80%"
      :before-close="handleDocumentsClose"
    >
      <template #header>
        <div class="dialog-header">
          <span>{{ selectedKB?.title }} - 文档列表</span>
        </div>
      </template>
      
      <div v-if="documents.length === 0" class="empty-documents">
        <el-empty description="该知识库暂无文档">
          <div class="empty-actions">
            <el-button type="primary" @click="uploadDocument(selectedKB)">
              上传文档
            </el-button>
            <el-button type="primary" plain @click="startJsonImport(selectedKB)">
              上传 JSON 文档
            </el-button>
          </div>
        </el-empty>
      </div>
      
      <div v-else class="documents-list">
        <div v-for="doc in documents" :key="doc.id" class="document-item">
          <div class="document-header">
            <h4>{{ doc.title }}</h4>
            <div class="document-actions">
              <el-button size="small" @click="viewDocumentContent(doc)">
                <AppleIcon name="view" :size="14" />
                查看内容
              </el-button>
              <el-button size="small" type="danger" @click="deleteDocument(doc)">
                <AppleIcon name="trash" :size="14" />
                删除
              </el-button>
            </div>
          </div>
          <div class="document-meta">
            <el-tag size="small" type="info">{{ doc.content_type }}</el-tag>
            <el-tag
              v-if="doc.scar_domain"
              size="small"
              type="warning"
            >{{ doc.scar_domain }}</el-tag>
            <el-tag
              v-if="doc.compile_status && doc.compile_status !== 'none'"
              size="small"
              :type="compileStatusTagType(doc.compile_status)"
            >
              编译 {{ compileStatusLabel(doc.compile_status) }}
            </el-tag>
            <span class="document-size">{{ formatFileSize(doc.file_size) }}</span>
            <span class="document-date">{{ formatDate(doc.created_at) }}</span>
          </div>
          <p
            v-if="doc.compile_status === 'failed' && doc.scar_compile_error"
            class="scar-compile-error"
          >
            编译失败：{{ doc.scar_compile_error }}
          </p>
          <div class="document-preview">
            <p>{{ doc.content?.substring(0, 200) }}...</p>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 文档内容查看对话框 -->
    <el-dialog
      v-model="showDocumentContentDialog"
      :title="selectedDocument?.title"
      width="80%"
      :before-close="() => showDocumentContentDialog = false"
      class="document-content-dialog"
    >
      <div v-if="selectedDocument" class="document-content">
        <div class="document-info">
          <el-tag type="info">{{ selectedDocument.content_type }}</el-tag>
          <span class="document-size">{{ formatFileSize(selectedDocument.file_size) }}</span>
          <span class="document-date">{{ formatDate(selectedDocument.created_at) }}</span>
        </div>
        <div class="document-text">
          <pre>{{ selectedDocument.content }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import AppleIcon from '@/components/AppleIcon.vue'
import BrandMark from '@/components/BrandMark.vue'
import PageScaffold from '@/components/templates/PageScaffold.vue'
import KnowledgeFilterBar from '@/components/composite/KnowledgeFilterBar.vue'

const router = useRouter()
const route = useRoute()

interface KnowledgeBase {
  id: string
  title: string
  description: string
  category: string
  document_count: number
  created_at: string
  updated_at: string
  is_system_curriculum?: boolean
  is_owner?: boolean
  access_role?: 'owner' | 'viewer'
}

function isPersonalEnglishKb(kb: KnowledgeBase): boolean {
  return !!(kb.is_owner && String(kb.title || '').includes('英语学习 ·'))
}

function isKbEditable(kb: KnowledgeBase): boolean {
  return !!kb.is_owner && !kb.is_system_curriculum
}

const knowledgeBases = ref<KnowledgeBase[]>([])
const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const showUploadDialog = ref(false)
const uploadMode = ref<'file' | 'json'>('file')
const jsonUploading = ref(false)
const currentImportJobId = ref<string | null>(null)
const importProgress = ref({
  status: '',
  total: 0,
  created: 0,
  vectorized: 0,
  skipped: 0,
  percentage: 0
})
const showImportProgressDialog = ref(false)
const importProgressInterval = ref<number | null>(null)
const creating = ref(false)
const editing = ref(false)
const uploading = ref(false)
/** 与后端 settings / KNOWLEDGE_UPLOAD_MAX_BYTES、KNOWLEDGE_CHUNK_MAX_BYTES 对齐，打开对话框时拉取 */
const uploadLimits = ref({
  max_file_bytes: 100 * 1024 * 1024,
  chunk_max_bytes: 8 * 1024 * 1024
})
const uploadProgressLabel = ref('')

// 学习内容相关
const showDocumentsDialog = ref(false)
const documents = ref<any[]>([])
const selectedDocument = ref<any>(null)
const showDocumentContentDialog = ref(false)
const selectedKB = ref<any>(null)
const filterKeyword = ref('')
const filterCategory = ref('')
const filterSort = ref<'created_desc' | 'created_asc' | 'docs_desc' | 'docs_asc' | 'title_asc'>('created_desc')

type AnalysisPayload = {
  relevance: string
  content_type: string
  quality_score: number
  confidence: number
  issues: string[]
  suggestions: string[]
}

const createForm = reactive({
  title: '',
  description: '',
  category: 'general'
})

const editForm = reactive({
  id: '',
  title: '',
  description: '',
  category: 'general'
})

const uploadForm = reactive({
  knowledge_base_id: '',
  file: null as File | null,
  scar_domain: '' as '' | 'construction'
})

const compileStatusLabel = (status?: string) => {
  if (status === 'ok') return 'ok'
  if (status === 'failed') return 'failed'
  return status || 'none'
}

const compileStatusTagType = (status?: string) => {
  if (status === 'ok') return 'success'
  if (status === 'failed') return 'danger'
  return 'info'
}

const createRules = {
  title: [
    { required: true, message: '请输入标题', trigger: 'blur' }
  ],
  description: [
    { required: true, message: '请输入描述', trigger: 'blur' }
  ],
  category: [
    { required: true, message: '请选择分类', trigger: 'change' }
  ]
}

const createFormRef = ref()
const editFormRef = ref()
const uploadFormRef = ref()
const fileInput = ref()

const ANALYSIS_SAMPLE_BYTES = 512 * 1024

const loadUploadLimits = async (kbId: string) => {
  try {
    const { data } = await api.get(`/knowledge/${kbId}/documents/upload-limits/`)
    uploadLimits.value = {
      max_file_bytes: Number(data.max_file_bytes) || uploadLimits.value.max_file_bytes,
      chunk_max_bytes: Number(data.chunk_max_bytes) || uploadLimits.value.chunk_max_bytes
    }
  } catch {
    /* 使用默认上限 */
  }
}

onMounted(async () => {
  await loadKnowledgeBases()
  await tryOpenDocumentDeepLink()
})

/** 从 /knowledge?kb=<uuid>&document=<uuid> 打开文档列表并定位正文（如英语学习向导定稿历史） */
async function tryOpenDocumentDeepLink() {
  const q = route.query
  const kbRaw = q.kb ?? q.knowledge_base_id
  const docRaw = q.document ?? q.doc
  if (!kbRaw || !docRaw) return
  const kbId = (Array.isArray(kbRaw) ? kbRaw[0] : kbRaw) as string
  const docId = (Array.isArray(docRaw) ? docRaw[0] : docRaw) as string
  const kb = knowledgeBases.value.find((k) => String(k.id) === String(kbId))
  if (!kb) {
    ElMessage.warning('未在您的知识库列表中找到该知识库')
    return
  }
  await viewDocuments(kb)
  const doc = documents.value.find((d) => String(d.id) === String(docId))
  if (doc) {
    viewDocumentContent(doc)
  } else {
    ElMessage.info('已打开该知识库的文档列表，但未找到对应文档（可能已删除）')
  }
  await nextTick()
  await router.replace({ path: '/knowledge', query: {} })
}

const loadKnowledgeBases = async () => {
  try {
    const response = await api.get('/knowledge/')
    knowledgeBases.value = response.data
  } catch (error) {
    ElMessage.error('加载知识库失败')
  }
}

const filteredKnowledgeBases = computed(() => {
  const kw = filterKeyword.value.trim().toLowerCase()
  let arr = [...knowledgeBases.value]
  if (kw) {
    arr = arr.filter((kb) =>
      String(kb.title || '').toLowerCase().includes(kw) ||
      String(kb.description || '').toLowerCase().includes(kw)
    )
  }
  if (filterCategory.value) {
    arr = arr.filter((kb) => kb.category === filterCategory.value)
  }
  switch (filterSort.value) {
    case 'created_asc':
      arr.sort((a, b) => +new Date(a.created_at) - +new Date(b.created_at))
      break
    case 'docs_desc':
      arr.sort((a, b) => (b.document_count || 0) - (a.document_count || 0))
      break
    case 'docs_asc':
      arr.sort((a, b) => (a.document_count || 0) - (b.document_count || 0))
      break
    case 'title_asc':
      arr.sort((a, b) => String(a.title || '').localeCompare(String(b.title || ''), 'zh-Hans-CN'))
      break
    case 'created_desc':
    default:
      arr.sort((a, b) => +new Date(b.created_at) - +new Date(a.created_at))
      break
  }
  return arr
})

const resetFilters = () => {
  filterKeyword.value = ''
  filterCategory.value = ''
  filterSort.value = 'created_desc'
}

const handleCreate = async () => {
  if (!createFormRef.value) return

  await createFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      creating.value = true
      try {
        await api.post('/knowledge/', createForm)
        ElMessage.success('创建成功')
        showCreateDialog.value = false
        loadKnowledgeBases()
        // 重置表单
        createForm.title = ''
        createForm.description = ''
        createForm.category = 'general'
      } catch (error) {
        ElMessage.error('创建失败')
      } finally {
        creating.value = false
      }
    }
  })
}

const handleCommand = async (command: string, kb: KnowledgeBase) => {
  if (!isKbEditable(kb)) {
    ElMessage.info('系统预置库为只读，无法编辑或上传')
    return
  }
  switch (command) {
    case 'edit':
      // 编辑知识库
      editKnowledgeBase(kb)
      break
    case 'upload':
      // 上传文档
      uploadDocument(kb)
      break
    case 'delete':
      try {
        await ElMessageBox.confirm('确定要删除这个知识库吗？', '确认删除', {
          type: 'warning'
        })
        await api.delete(`/knowledge/${kb.id}/`)
        ElMessage.success('删除成功')
        loadKnowledgeBases()
      } catch (error) {
        if (error !== 'cancel') {
          ElMessage.error('删除失败')
        }
      }
      break
  }
}

const viewKnowledgeBase = (kb: KnowledgeBase) => {
  // 查看知识库详情
  console.log('查看知识库:', kb)
}

const getCategoryType = (category: string): 'primary' | 'success' | 'warning' | 'danger' | 'info' => {
  const types: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
    'general': 'info',
    'legal': 'primary',
    'education': 'success',
    'healthcare': 'warning',
    'finance': 'danger',
    'technology': 'info',
    'business': 'primary',
    'science': 'success',
    'humanities': 'warning',
    'engineering': 'danger',
    'arts': 'info',
    'other': 'info'
  }
  return types[category] || 'info'
}

const getCategoryName = (category: string) => {
  const names: Record<string, string> = {
    'general': '通用',
    'legal': '法律',
    'education': '教育',
    'healthcare': '医疗健康',
    'finance': '金融',
    'technology': '技术',
    'business': '商业',
    'science': '科学',
    'humanities': '人文社科',
    'engineering': '工程',
    'arts': '艺术设计',
    'other': '其他'
  }
  return names[category] || category
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString()
}

// 编辑知识库
const editKnowledgeBase = (kb: KnowledgeBase) => {
  editForm.id = kb.id
  editForm.title = kb.title
  editForm.description = kb.description
  editForm.category = kb.category
  showEditDialog.value = true
}

const handleEdit = async () => {
  if (!editFormRef.value) return

  await editFormRef.value.validate(async (valid: boolean) => {
    if (valid) {
      editing.value = true
      try {
        await api.put(`/knowledge/${editForm.id}/`, {
          title: editForm.title,
          description: editForm.description,
          category: editForm.category
        })
        ElMessage.success('更新成功')
        showEditDialog.value = false
        loadKnowledgeBases()
      } catch (error) {
        ElMessage.error('更新失败')
      } finally {
        editing.value = false
      }
    }
  })
}

// 上传文档
const uploadDocument = async (kb: KnowledgeBase) => {
  uploadForm.knowledge_base_id = kb.id
  uploadForm.file = null
  uploadForm.scar_domain = ''
  uploadMode.value = 'file'
  uploadProgressLabel.value = ''
  await loadUploadLimits(kb.id)
  showUploadDialog.value = true
}

const startJsonImport = (kb: KnowledgeBase) => {
  uploadForm.knowledge_base_id = kb.id
  uploadForm.file = null
  uploadForm.scar_domain = ''
  uploadMode.value = 'json'
  showUploadDialog.value = true
}

const handleFileChange = (file: any) => {
  if (file && file.raw) {
    const maxFileSize = uploadLimits.value.max_file_bytes
    if (file.raw.size > maxFileSize) {
      ElMessage.error(
        `文件不能超过 ${formatFileSize(maxFileSize)}，当前：${formatFileSize(file.raw.size)}`
      )
      return
    }

    uploadForm.file = file.raw
    console.log('选择的文件:', file.name, '大小:', (file.raw.size / 1024 / 1024).toFixed(2) + 'MB')
  }
}

const handleJsonFileChange = (file: any) => {
  if (file && file.raw) {
    const maxFileSize = 100 * 1024 * 1024 // 100MB
    if (file.raw.size > maxFileSize) {
      ElMessage.error(`JSON 文件不能超过100MB，当前大小：${(file.raw.size / 1024 / 1024).toFixed(2)}MB`)
      return
    }
    uploadForm.file = file.raw
  }
}

const triggerFileInput = () => {
  fileInput.value?.click()
}

const handleSimpleFileChange = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    const file = target.files[0]

    const maxFileSize = uploadLimits.value.max_file_bytes
    if (file.size > maxFileSize) {
      ElMessage.error(
        `文件不能超过 ${formatFileSize(maxFileSize)}，当前：${formatFileSize(file.size)}`
      )
      return
    }

    uploadForm.file = file
    console.log('选择的文件:', file.name, '大小:', (file.size / 1024 / 1024).toFixed(2) + 'MB')
  }
}

const handleUpload = async () => {
  if (!uploadForm.file) {
    ElMessage.warning('请选择要上传的文件')
    return
  }

  uploading.value = true
  uploadProgressLabel.value = ''
  try {
    const maxBytes = uploadLimits.value.max_file_bytes
    const chunkMax = uploadLimits.value.chunk_max_bytes
    if (uploadForm.file.size > maxBytes) {
      ElMessage.error(`文件不能超过 ${formatFileSize(maxBytes)}，当前：${formatFileSize(uploadForm.file.size)}`)
      return
    }

    // 先分析文档内容（大文件只读前一段参与相关性预判，避免浏览器卡顿）
    const content = await readAnalysisSample(uploadForm.file)
    const analysisResult = await analyzeDocumentContent(content, uploadForm.file.name)
    
    // 如果文档不相关，显示警告并询问是否继续
    if (analysisResult.relevance === 'irrelevant') {
      const confirmed = await showAnalysisDialog(analysisResult)
      if (!confirmed) {
        uploading.value = false
        return
      }
    }
    
    // 如果文档质量较低，显示警告
    if (analysisResult.quality_score < 50) {
      ElMessage.warning(`文档质量较低（${analysisResult.quality_score.toFixed(1)}分），建议改进后再上传`)
    }

    const file = uploadForm.file
    const kbId = uploadForm.knowledge_base_id
    const useChunk = file.size > chunkMax

    let response: Awaited<ReturnType<typeof api.post>>

    if (!useChunk) {
      const formData = new FormData()
      formData.append('file', file)
      if (uploadForm.scar_domain) {
        formData.append('scar_domain', uploadForm.scar_domain)
        formData.append('domain', uploadForm.scar_domain)
      }
      response = await api.post(`/knowledge/${kbId}/documents/`, formData)
    } else {
      const uploadId = crypto.randomUUID()
      const totalChunks = Math.ceil(file.size / chunkMax)
      for (let i = 0; i < totalChunks; i++) {
        uploadProgressLabel.value = `分片上传 ${i + 1} / ${totalChunks}（自动分批，无需手动切割文件）`
        const start = i * chunkMax
        const end = Math.min(start + chunkMax, file.size)
        const blob = file.slice(start, end)
        const formData = new FormData()
        formData.append('file', blob, file.name)
        formData.append('upload_id', uploadId)
        formData.append('chunk_index', String(i))
        formData.append('total_chunks', String(totalChunks))
        if (i === 0) {
          formData.append('filename', file.name)
          if (uploadForm.scar_domain) {
            formData.append('scar_domain', uploadForm.scar_domain)
            formData.append('domain', uploadForm.scar_domain)
          }
        }
        response = await api.post(`/knowledge/${kbId}/documents/chunk-upload/`, formData, {
          timeout: 300000
        })
        if (i < totalChunks - 1 && response.status !== 200) {
          throw new Error(`分片 ${i + 1} 上传异常`)
        }
      }
    }

    
    // 显示分析结果
    if (response.data.warning) {
      ElMessage.warning(response.data.warning)
    } else if (response.data.compile_status === 'ok' || response.data?.data?.compile_status === 'ok') {
      ElMessage.success('上传成功（SCAR 结构已编译）')
    } else if (response.data.compile_status === 'failed' || response.data?.data?.compile_status === 'failed') {
      ElMessage.warning('上传成功，但 SCAR 编译失败，可在文档列表查看原因')
    } else {
      ElMessage.success('上传成功')
    }
    
    showUploadDialog.value = false
    loadKnowledgeBases()
  } catch (error: any) {
    console.error('上传失败:', error)
    if (error.response && error.response.data) {
      if (error.response.data.analysis) {
        // 显示详细的分析结果
        await showAnalysisDialog(error.response.data.analysis, true)
      } else if (error.response.data.error) {
        // 显示后端返回的错误信息
        ElMessage.error(`上传失败: ${error.response.data.error}`)
        if (error.response.data.detail) {
          console.error('错误详情:', error.response.data.detail)
        }
      } else {
        ElMessage.error(`上传失败: ${JSON.stringify(error.response.data)}`)
      }
    } else {
      ElMessage.error('上传失败，请检查网络连接')
    }
  } finally {
    uploading.value = false
    uploadProgressLabel.value = ''
  }
}

const handleJsonImport = async () => {
  if (!uploadForm.knowledge_base_id) {
    ElMessage.error('请选择知识库')
    return
  }

  if (!uploadForm.file) {
    ElMessage.error('请先选择 JSON 文件')
    return
  }

  const formData = new FormData()
  formData.append('file', uploadForm.file)

  try {
    jsonUploading.value = true
    const response = await api.post(
      `/knowledge/knowledge-bases/${uploadForm.knowledge_base_id}/import-json/`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30 * 1000 // 30秒超时，因为这是创建任务，不是执行任务
      }
    )
    
    // 获取任务ID并开始轮询
    currentImportJobId.value = response.data.job_id
    showUploadDialog.value = false
    showImportProgressDialog.value = true
    startImportProgressPolling(uploadForm.knowledge_base_id, response.data.job_id)
    
    ElMessage.success('JSON 导入任务已创建，正在后台处理...')
  } catch (error: any) {
    console.error('JSON 导入失败:', error)
    ElMessage.error(
      error?.response?.data?.error ||
      'JSON 导入失败，请检查文件结构或稍后重试'
    )
  } finally {
    jsonUploading.value = false
  }
}

const startImportProgressPolling = (kbId: string, jobId: string) => {
  // 清除之前的轮询
  if (importProgressInterval.value) {
    clearInterval(importProgressInterval.value)
  }

  // 立即查询一次
  fetchImportProgress(kbId, jobId)

  // 每2秒轮询一次
  importProgressInterval.value = window.setInterval(() => {
    fetchImportProgress(kbId, jobId)
  }, 2000)
}

const fetchImportProgress = async (kbId: string, jobId: string) => {
  try {
    const response = await api.get(
      `/knowledge/knowledge-bases/${kbId}/import-jobs/${jobId}/`
    )
    const data = response.data
    
    importProgress.value = {
      status: data.status,
      total: data.total_documents || 0,
      created: data.created_documents || 0,
      vectorized: data.vectorized_documents || 0,
      skipped: data.skipped_documents || 0,
      percentage: data.progress_percentage || 0
    }

    // 如果任务完成，停止轮询
    if (['SUCCEEDED', 'FAILED', 'CANCELED'].includes(data.status)) {
      if (importProgressInterval.value) {
        clearInterval(importProgressInterval.value)
        importProgressInterval.value = null
      }

      if (data.status === 'SUCCEEDED') {
        ElMessage.success(`导入完成：成功 ${data.created_documents} 条，跳过 ${data.skipped_documents} 条`)
        loadKnowledgeBases()
        if (selectedKB.value?.id === kbId) {
          await loadDocuments(kbId)
        }
      } else if (data.status === 'FAILED') {
        ElMessage.error(`导入失败：${data.error_message || '未知错误'}`)
      }

      // 3秒后自动关闭对话框
      setTimeout(() => {
        showImportProgressDialog.value = false
        currentImportJobId.value = null
      }, 3000)
    }
  } catch (error: any) {
    console.error('查询导入进度失败:', error)
  }
}

const cancelImportJob = async () => {
  if (!currentImportJobId.value || !uploadForm.knowledge_base_id) {
    return
  }

  try {
    await api.post(
      `/knowledge/knowledge-bases/${uploadForm.knowledge_base_id}/import-jobs/${currentImportJobId.value}/cancel/`
    )
    ElMessage.info('已取消导入任务')
    if (importProgressInterval.value) {
      clearInterval(importProgressInterval.value)
      importProgressInterval.value = null
    }
    showImportProgressDialog.value = false
    currentImportJobId.value = null
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.error || '取消任务失败')
  }
}

// 获取导入状态类型
const getImportStatusType = (status: string) => {
  const statusMap: Record<string, string> = {
    'PENDING': 'info',
    'PROCESSING': 'primary',
    'SUCCEEDED': 'success',
    'FAILED': 'danger',
    'CANCELED': 'warning'
  }
  return statusMap[status] || 'info'
}

// 获取导入状态文本
const getImportStatusText = (status: string) => {
  const statusMap: Record<string, string> = {
    'PENDING': '待处理',
    'PROCESSING': '处理中',
    'SUCCEEDED': '成功',
    'FAILED': '失败',
    'CANCELED': '已取消'
  }
  return statusMap[status] || status
}

// 清理轮询
onUnmounted(() => {
  if (importProgressInterval.value) {
    clearInterval(importProgressInterval.value)
  }
})

// 读取文件内容（可为整文件或 Blob 片段）
const readFileContent = (file: File | Blob): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      let content = e.target?.result as string
      // 清理文件内容，移除问题字符
      if (content) {
        content = cleanFileContent(content)
      }
      resolve(content)
    }
    reader.onerror = reject
    reader.readAsText(file, 'UTF-8')
  })
}

/** 大文件仅截取开头一段做上传前相关性分析，降低内存占用 */
const readAnalysisSample = async (file: File): Promise<string> => {
  if (file.size <= ANALYSIS_SAMPLE_BYTES) {
    return readFileContent(file)
  }
  return readFileContent(file.slice(0, ANALYSIS_SAMPLE_BYTES))
}

// 清理文件内容
const cleanFileContent = (content: string): string => {
  // 过滤掉 NUL 字符和其他控制字符
  return content
    .replace(/\x00/g, '')  // 移除 NUL 字符
    .replace(/[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]/g, ' ')  // 移除其他控制字符，替换为空格
    .replace(/\s+/g, ' ')  // 合并多个空白字符
    .trim()  // 去除首尾空白
}

// 分析文档内容
const analyzeDocumentContent = async (content: string, filename: string) => {
  try {
    const response = await api.post('/knowledge/analyze-document/', {
      content,
      filename
    })
    return response.data
  } catch (error) {
    console.error('文档分析失败:', error)
    return {
      relevance: 'unknown',
      content_type: 'unknown',
      confidence: 0,
      quality_score: 0,
      keywords: [],
      issues: ['分析失败'],
      suggestions: ['请检查文档格式']
    }
  }
}

// 显示分析结果对话框
const showAnalysisDialog = (analysis: AnalysisPayload, isError = false): Promise<boolean> => {
  return new Promise((resolve) => {
    const relevanceText: Record<string, string> = {
      'highly_relevant': '高度相关',
      'relevant': '相关',
      'partially_relevant': '部分相关',
      'irrelevant': '不相关',
      'unknown': '未知'
    }
    
    const contentTypeText: Record<string, string> = {
      'educational': '教育内容',
      'technical': '技术文档',
      'research': '研究论文',
      'tutorial': '教程指南',
      'reference': '参考资料',
      'personal': '个人文档',
      'spam': '垃圾内容',
      'unknown': '未知类型'
    }

    const message = isError ? '文档上传被拒绝' : '文档分析结果'
    const type = isError ? 'error' : 'warning'
    
    ElMessageBox({
      title: message,
      message: `
        <div style="text-align: left;">
          <p><strong>相关性：</strong>${relevanceText[analysis.relevance] || analysis.relevance}</p>
          <p><strong>内容类型：</strong>${contentTypeText[analysis.content_type] || analysis.content_type}</p>
          <p><strong>质量分数：</strong>${analysis.quality_score.toFixed(1)}/100</p>
          <p><strong>置信度：</strong>${(analysis.confidence * 100).toFixed(1)}%</p>
          ${analysis.issues.length > 0 ? `<p><strong>问题：</strong></p><ul>${analysis.issues.map(issue => `<li>${issue}</li>`).join('')}</ul>` : ''}
          ${analysis.suggestions.length > 0 ? `<p><strong>建议：</strong></p><ul>${analysis.suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}</ul>` : ''}
        </div>
      `,
      type,
      dangerouslyUseHTMLString: true,
      showCancelButton: !isError,
      confirmButtonText: isError ? '确定' : '继续上传',
      cancelButtonText: '取消上传'
    }).then(() => {
      resolve(true)
    }).catch(() => {
      resolve(false)
    })
  })
}

const goBack = () => {
  router.push('/')
}

// 文档查看相关方法
const viewDocuments = async (kb: KnowledgeBase) => {
  selectedKB.value = kb
  showDocumentsDialog.value = true
  await loadDocuments(kb.id)
}

const loadDocuments = async (knowledgeBaseId: string) => {
  try {
    const response = await api.get(`/knowledge/${knowledgeBaseId}/documents/`)
    documents.value = response.data || []
  } catch (error: any) {
    ElMessage.error("加载文档失败")
    documents.value = []
  }
}

const viewDocumentContent = (doc: any) => {
  selectedDocument.value = doc
  showDocumentContentDialog.value = true
}

const deleteDocument = async (doc: any) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档 "${doc.title}" 吗？`,
      "确认删除",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    )
    
    await api.delete(`/knowledge/${selectedKB.value?.id}/documents/${doc.id}/`)
    ElMessage.success("文档删除成功")
    if (selectedKB.value?.id) {
      await loadDocuments(selectedKB.value.id)
    }
  } catch (error: any) {
    if (error !== "cancel") {
      ElMessage.error("删除文档失败")
    }
  }
}

const handleDocumentsClose = () => {
  showDocumentsDialog.value = false
  selectedKB.value = null
  documents.value = []
}

const formatFileSize = (bytes: number) => {
  if (!bytes) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i]
}

</script>

<style scoped>
.knowledge-container {
  min-height: 100vh;
  background: var(--apple-body-bg);
  padding: 32px 48px 64px;
}

.knowledge-header {
  background: var(--apple-surface);
  border: 1px solid var(--apple-border);
  border-radius: var(--apple-card-radius);
  padding: 0;
  height: 90px;
  margin-bottom: 24px;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 100%;
  padding: 0 32px;
  max-width: 1200px;
  margin: 0 auto;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.back-button {
  background: var(--apple-surface);
  border: 1px solid var(--apple-border);
  border-radius: var(--apple-control-radius);
  padding: 8px;
  color: var(--apple-text-primary);
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}

.back-button:hover {
  background: rgba(10, 132, 255, 0.08);
  border-color: var(--apple-brand-blue);
  color: var(--apple-brand-blue);
}

.header-title h2 {
  color: var(--apple-text-primary);
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
}

.header-title p {
  margin: 0;
  color: var(--apple-text-secondary);
  font-size: 0.9rem;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.create-button {
  border-radius: var(--apple-pill-radius);
  padding: 12px 24px;
  font-weight: 500;
}

.knowledge-main {
  flex: 1;
  padding: 0;
  overflow: visible;
}

.kb-filters {
  max-width: 1200px;
  margin: 0 auto 12px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.filter-input {
  width: 300px;
}

.filter-select {
  width: 180px;
}

.kb-filter-summary {
  max-width: 1200px;
  margin: 0 auto 14px;
  color: var(--apple-text-secondary);
  font-size: 13px;
}

.knowledge-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 1.5rem;
  max-width: 1200px;
  margin: 0 auto;
}

.kb-card {
  cursor: pointer;
  transition: border-color 0.2s ease, transform 0.2s ease;
  border: 1px solid var(--apple-border);
  border-radius: 20px;
  background: var(--apple-surface);
  overflow: hidden;
}

.kb-card:hover {
  border-color: var(--apple-brand-blue);
  transform: translateY(-3px);
}

/* 知识库卡片头部 */
.kb-header {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  padding: 1.5rem;
  padding-bottom: 1rem;
}

.kb-icon {
  width: 48px;
  height: 48px;
  background: linear-gradient(135deg, #0a84ff 0%, #5e5ce6 100%);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.kb-info {
  flex: 1;
  min-width: 0;
}

.kb-info h3 {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--apple-text-primary);
  margin: 0 0 0.5rem 0;
  line-height: 1.4;
}

.kb-description {
  color: var(--apple-text-secondary);
  font-size: 0.9rem;
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.more-button {
  color: var(--apple-text-secondary);
  padding: 4px;
  border-radius: 6px;
  transition: all 0.3s ease;
}

.more-button:hover {
  background: var(--apple-overlay);
  color: var(--apple-brand-blue);
}

/* 知识库卡片元数据 */
.kb-meta {
  padding: 0 1.5rem 1.5rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.kb-tags {
  display: flex;
  gap: 0.5rem;
}

.kb-stats {
  display: flex;
  align-items: center;
  gap: 1rem;
  color: var(--apple-text-secondary);
  font-size: 0.85rem;
}

.kb-count {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.kb-date {
  font-size: 0.8rem;
  color: #a1a1a6;
}

.kb-actions {
  margin-top: 8px;
  padding: 0 1.5rem 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

/* 学习内容样式 */
.empty-content {
  text-align: center;
  padding: 40px;
}

.learning-content {
  max-height: 600px;
  overflow-y: auto;
}

.content-display {
  padding: 20px;
}


.no-data {
  text-align: center;
  color: #909399;
  padding: 40px;
  font-size: 14px;
}

/* 按钮样式优化 */
.action-btn {
  border-radius: var(--apple-pill-radius) !important;
  font-weight: 500 !important;
  border: 1px solid var(--apple-border) !important;
  color: var(--apple-text-primary) !important;
  background: transparent !important;
  box-shadow: none !important;
}

.action-btn:hover {
  border-color: var(--apple-brand-blue) !important;
  color: var(--apple-brand-blue) !important;
}

.summary-content h4 {
  color: #2c3e50;
  margin-bottom: 20px;
}

.summary-section {
  margin-bottom: 24px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fafafa;
}

.summary-section h5 {
  color: #409eff;
  margin-bottom: 12px;
}

.key-points {
  margin-top: 12px;
}

.key-points h6 {
  color: #606266;
  margin-bottom: 8px;
}

.key-points ul {
  margin: 0;
  padding-left: 20px;
}

.key-points li {
  margin-bottom: 4px;
  color: #606266;
}

.outline-content h4 {
  color: #2c3e50;
  margin-bottom: 16px;
}

.chapter-item {
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: white;
}

.chapter-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.chapter-number {
  width: 32px;
  height: 32px;
  background: #409eff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  flex-shrink: 0;
}

.chapter-header h5 {
  margin: 0;
  flex: 1;
  color: #2c3e50;
}

.chapter-time {
  color: #999;
  font-size: 14px;
}

.key-topics {
  margin-top: 12px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.concepts-content h4 {
  color: #2c3e50;
  margin-bottom: 20px;
}

.concepts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.concept-card {
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.concept-card h5 {
  color: #409eff;
  margin-bottom: 8px;
}

.concept-card p {
  color: #606266;
  margin-bottom: 12px;
}

.related-docs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.related-docs span {
  color: #999;
  font-size: 14px;
}

.qa-content h4 {
  color: #2c3e50;
  margin-bottom: 20px;
}

.qa-item {
  margin-bottom: 24px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fafafa;
}

.qa-item h5 {
  color: #409eff;
  margin-bottom: 12px;
}

.answer {
  color: #606266;
  line-height: 1.6;
  margin-bottom: 12px;
}

.qa-source {
  margin-top: 8px;
}

/* 文档查看样式 */
.empty-documents {
  text-align: center;
  padding: 40px;
}

.empty-actions {
  display: flex;
  justify-content: center;
  gap: 16px;
  margin-top: 12px;
}

.json-tip {
  font-size: 12px;
  color: #606266;
  background: #f8f9fb;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 12px;
  line-height: 1.4;
}

.json-tip pre {
  background: #111827;
  color: #f9fafb;
  border-radius: 8px;
  padding: 12px;
  margin: 8px 0 0;
  font-size: 12px;
}

.dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.dialog-header span {
  font-size: 18px;
  font-weight: 500;
  color: #2c3e50;
}

.documents-list {
  max-height: 600px;
  overflow-y: auto;
}

.document-item {
  margin-bottom: 20px;
  padding: 16px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.document-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.document-header h4 {
  margin: 0;
  color: #2c3e50;
  flex: 1;
}

.document-actions {
  display: flex;
  gap: 8px;
}

.document-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
  font-size: 14px;
  color: #666;
  align-items: center;
}

.scar-compile-error {
  margin: 0 0 10px;
  font-size: 13px;
  color: #b91c1c;
}

.document-size,
.document-date {
  color: #999;
}

.document-preview {
  color: #606266;
  line-height: 1.6;
}

.document-preview p {
  margin: 0;
}

.document-content {
  flex: 1;
  overflow: hidden;
  width: 100%;
  box-sizing: border-box;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.document-content-dialog .el-dialog__body {
  padding: 20px;
  max-height: 80vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.document-content-dialog .el-dialog {
  max-height: 90vh;
}

.document-content-dialog .el-dialog__header {
  flex-shrink: 0;
}

/* 强制防止文字溢出 */
.document-content-dialog * {
  max-width: 100% !important;
  box-sizing: border-box !important;
}

.document-content-dialog .el-dialog__body {
  overflow: hidden !important;
}

.document-content-dialog .document-content {
  overflow: hidden !important;
}

.document-content-dialog .document-text {
  overflow: hidden !important;
}

.document-content-dialog .document-text pre {
  overflow: hidden !important;
  white-space: pre-wrap !important;
  word-break: break-all !important;
}

.document-info {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e4e7ed;
  font-size: 14px;
  color: #666;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.document-text {
  background: #f9f9f9;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden !important;
  min-height: 0;
  position: relative;
}

.document-text pre {
  margin: 0;
  white-space: pre-wrap !important;
  word-wrap: break-word !important;
  word-break: break-all !important;
  font-family: "Monaco", "Menlo", "Ubuntu Mono", monospace;
  font-size: 14px;
  line-height: 1.6;
  color: #2c3e50;
  max-width: 100% !important;
  width: 100% !important;
  overflow-x: hidden !important;
  overflow-wrap: break-word !important;
  hyphens: auto;
  box-sizing: border-box !important;
  padding: 0;
  display: block;
}

/* 上传组件样式 */
:deep(.el-upload) {
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: all 0.3s;
}

:deep(.el-upload:hover) {
  border-color: #409eff;
}

:deep(.el-upload-dragger) {
  width: 100%;
  height: 180px;
  text-align: center;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

:deep(.el-icon--upload) {
  font-size: 67px;
  color: #c0c4cc;
  margin-bottom: 16px;
}

:deep(.el-upload__text) {
  color: #606266;
  font-size: 14px;
  text-align: center;
}

:deep(.el-upload__text em) {
  color: #409eff;
  font-style: normal;
}

/* 文件上传容器样式 */
.file-upload-container {
  width: 100%;
}

.simple-file-input {
  margin-top: 16px;
  padding: 16px;
  border: 1px dashed #d9d9d9;
  border-radius: 6px;
  text-align: center;
  background-color: #fafafa;
}

.selected-file {
  display: block;
  margin-top: 8px;
  color: #409eff;
  font-size: 14px;
}

.action-btn {
  flex: 1;
  min-width: 120px;
  white-space: nowrap;
  position: relative;
  overflow: hidden;
}

.action-btn::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  transition: left 0.5s;
}

.action-btn:hover::before {
  left: 100%;
}

.action-btn .el-icon {
  margin-right: 6px;
  font-size: 16px;
}

/* JSON 导入进度对话框样式 */
.import-progress-content {
  padding: 20px 0;
}

.progress-stats {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.stat-item:last-child {
  border-bottom: none;
}

.stat-label {
  color: #606266;
  font-size: 14px;
}

.text-success {
  color: #67c23a;
  font-weight: 500;
}

.text-primary {
  color: #409eff;
  font-weight: 500;
}

.text-warning {
  color: #e6a23c;
  font-weight: 500;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .action-row {
    flex-direction: column;
  }
  
  .action-btn {
    min-width: auto;
    width: 100%;
  }
  
  .kb-stats {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
