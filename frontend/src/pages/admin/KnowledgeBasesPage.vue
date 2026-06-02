<template>
  <div class="page-block">
    <div class="page-toolbar">
      <div>
        <h3>知识库管理</h3>
        <p class="page-subtitle">管理知识库元数据和文档元数据</p>
      </div>
      <a-space>
        <a-button @click="openCreateKB">
          <template #icon><PlusOutlined /></template>
          新建知识库
        </a-button>
        <a-button @click="openCreateDoc">
          <template #icon><FileAddOutlined /></template>
          添加文档
        </a-button>
      </a-space>
    </div>

    <a-tabs v-model:activeKey="activeTab">
      <a-tab-pane key="kb" tab="知识库">
        <a-result
          v-if="kbError"
          status="error"
          title="加载失败"
          sub-title="无法获取知识库列表"
        >
          <template #extra>
            <a-button type="primary" @click="loadKBs">重试</a-button>
          </template>
        </a-result>
        <a-empty
          v-else-if="kbs.length === 0 && !kbLoading"
          description="暂无可用知识库"
          style="margin-top: 48px"
        />
        <a-table
          v-else
          :columns="kbColumns"
          :data-source="kbs"
          :loading="kbLoading"
          :pagination="kbPagination"
          row-key="id"
          size="middle"
          @change="onKbTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'status'">
              <a-tag :color="record.status === 'ACTIVE' ? 'green' : 'default'">
                {{ record.status === 'ACTIVE' ? '启用' : record.status }}
              </a-tag>
            </template>
            <template v-if="column.key === 'kb'">
              <div class="primary-cell">{{ record.name }}</div>
              <div class="secondary-cell">{{ record.provider }}</div>
            </template>
            <template v-if="column.key === 'created_at'">
              {{ formatDateTime(record.created_at) }}
            </template>
          </template>
        </a-table>
      </a-tab-pane>

      <a-tab-pane key="doc" tab="文档">
        <a-result
          v-if="docError"
          status="error"
          title="加载失败"
          sub-title="无法获取文档列表"
        >
          <template #extra>
            <a-button type="primary" @click="loadDocs">重试</a-button>
          </template>
        </a-result>
        <a-empty
          v-else-if="docs.length === 0 && !docLoading"
          description="暂无已接入文档"
          style="margin-top: 48px"
        />
        <a-table
          v-else
          :columns="docColumns"
          :data-source="docs"
          :loading="docLoading"
          :pagination="docPagination"
          row-key="id"
          size="middle"
          @change="onDocTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'parse_status'">
              <a-tag :color="parseColor(record.parse_status)">
                {{ record.parse_status }}
              </a-tag>
            </template>
            <template v-if="column.key === 'created_at'">
              {{ formatDateTime(record.created_at) }}
            </template>
          </template>
        </a-table>
      </a-tab-pane>
    </a-tabs>

    <!-- 新建知识库弹窗 -->
    <a-modal
      v-model:open="kbModalVisible"
      title="新建知识库"
      :confirm-loading="submitting"
      @ok="submitKB"
      destroyOnClose
    >
      <a-form layout="vertical">
        <a-form-item label="名称" required>
          <a-input v-model:value="kbForm.name" placeholder="知识库名称" />
        </a-form-item>
        <a-form-item label="所属组织" required>
          <a-select
            v-model:value="kbForm.owner_org_unit_id"
            placeholder="选择所属组织"
            show-search
            :filter-option="filterOrgOption"
            :options="orgOptions"
            class="modal-select"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="提供方">
          <a-select
            v-model:value="kbForm.provider"
            :options="providerOptions"
            class="modal-select"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="Provider KB ID">
          <a-input v-model:value="kbForm.provider_kb_id" placeholder="Dify 知识库的 dataset_id" />
        </a-form-item>
        <a-form-item label="Embedding 模型">
          <a-input v-model:value="kbForm.embedding_model" placeholder="如 text-embedding-ada-002" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加文档弹窗 -->
    <a-modal
      v-model:open="docModalVisible"
      title="添加文档元数据"
      :confirm-loading="submitting"
      @ok="submitDoc"
      destroyOnClose
    >
      <a-form layout="vertical">
        <a-form-item label="所属知识库 ID" required>
          <a-input v-model:value="docForm.knowledge_base_id" placeholder="知识库 UUID" />
        </a-form-item>
        <a-form-item label="所属组织" required>
          <a-select
            v-model:value="docForm.owner_org_unit_id"
            placeholder="选择所属组织"
            show-search
            :filter-option="filterOrgOption"
            :options="orgOptions"
            class="modal-select"
            style="width: 100%"
          />
        </a-form-item>
        <a-form-item label="文件名" required>
          <a-input v-model:value="docForm.file_name" placeholder="如 contract-sample.pdf" />
        </a-form-item>
        <a-form-item label="Provider Doc ID">
          <a-input v-model:value="docForm.provider_doc_id" placeholder="Dify 文档 ID" />
        </a-form-item>
        <a-form-item label="Storage URI">
          <a-input v-model:value="docForm.storage_uri" placeholder="文件存储路径" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { FileAddOutlined, PlusOutlined } from '@ant-design/icons-vue'

import {
  createDocument,
  createKnowledgeBase,
  listDocuments,
  listKnowledgeBases,
  listOrgUnits,
} from '../../api/admin'
import type { DocumentRead, KnowledgeBase, KnowledgeBaseCreate, OrgUnit } from '../../api/types'
import { formatDateTime } from '../../utils/format'

// ---- 知识库 ----
const kbLoading = ref(false)
const kbError = ref(false)
const kbs = ref<KnowledgeBase[]>([])
const orgUnits = ref<OrgUnit[]>([])
const kbModalVisible = ref(false)
const kbForm = reactive({ name: '', owner_org_unit_id: '', provider: 'DIFY', provider_kb_id: '', embedding_model: '' })
const providerOptions = [
  { label: 'Dify', value: 'DIFY' },
  { label: 'Custom', value: 'CUSTOM' },
]

function createTablePagination() {
  return {
    current: 1,
    pageSize: 10,
    pageSizeOptions: ['10', '20', '50'],
    showSizeChanger: true,
    size: 'small',
    showTotal: (t: number) => `共 ${t} 条`,
  }
}

const kbPagination = reactive(createTablePagination())
const docPagination = reactive(createTablePagination())

function onKbTableChange(p: { current: number; pageSize: number }) {
  kbPagination.current = p.current
  kbPagination.pageSize = p.pageSize
}

function onDocTableChange(p: { current: number; pageSize: number }) {
  docPagination.current = p.current
  docPagination.pageSize = p.pageSize
}


const orgOptions = computed(() => orgUnits.value.map(org => ({
  label: `${org.name}（${org.type}）`,
  value: org.id,
})))

const kbColumns = [
  { title: '知识库', key: 'kb' },
  { title: '状态', key: 'status', width: 90 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
]

// ---- 文档 ----
const docLoading = ref(false)
const docError = ref(false)
const docs = ref<DocumentRead[]>([])
const docModalVisible = ref(false)
const docForm = reactive({
  knowledge_base_id: '',
  owner_org_unit_id: '',
  file_name: '',
  provider_doc_id: '',
  storage_uri: '',
})

const docColumns = [
  { title: '文件名', dataIndex: 'file_name', key: 'file_name' },
  { title: '文件类型', dataIndex: 'file_type', key: 'file_type', width: 100 },
  { title: '解析状态', key: 'parse_status', width: 100 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
]

// ---- tabs / submit ----
const activeTab = ref('kb')
const submitting = ref(false)

function parseColor(status: string) {
  const map: Record<string, string> = { COMPLETED: 'success', PENDING: 'default', PARSING: 'processing', FAILED: 'error' }
  return map[status] ?? 'default'
}

async function loadKBs() {
  kbLoading.value = true
  kbError.value = false
  try { kbs.value = await listKnowledgeBases() } catch { kbError.value = true } finally { kbLoading.value = false }
}

async function loadDocs() {
  docLoading.value = true
  docError.value = false
  try { docs.value = await listDocuments() } catch { docError.value = true } finally { docLoading.value = false }
}

async function loadOrgUnits() {
  try {
    orgUnits.value = await listOrgUnits()
  } catch {
    orgUnits.value = []
  }
}

function filterOrgOption(input: string, option: any) {
  return String(option?.label ?? '').toLowerCase().includes(input.toLowerCase())
}

function openCreateKB() {
  Object.assign(kbForm, { name: '', owner_org_unit_id: '', provider: 'DIFY', provider_kb_id: '', embedding_model: '' })
  kbModalVisible.value = true
}

async function submitKB() {
  submitting.value = true
  try {
    const payload: KnowledgeBaseCreate = {
      name: kbForm.name,
      owner_org_unit_id: kbForm.owner_org_unit_id,
      provider: kbForm.provider,
      provider_kb_id: kbForm.provider_kb_id || undefined,
      embedding_model: kbForm.embedding_model || undefined,
    }
    await createKnowledgeBase(payload)
    kbModalVisible.value = false
    await loadKBs()
  } catch { /* */ } finally { submitting.value = false }
}

function openCreateDoc() {
  Object.assign(docForm, { knowledge_base_id: '', owner_org_unit_id: '', file_name: '', provider_doc_id: '', storage_uri: '' })
  docModalVisible.value = true
}

async function submitDoc() {
  submitting.value = true
  try {
    await createDocument({
      knowledge_base_id: docForm.knowledge_base_id,
      owner_org_unit_id: docForm.owner_org_unit_id,
      file_name: docForm.file_name,
      provider_doc_id: docForm.provider_doc_id || undefined,
      storage_uri: docForm.storage_uri || undefined,
    })
    docModalVisible.value = false
    await loadDocs()
  } catch { /* */ } finally { submitting.value = false }
}

onMounted(() => {
  loadKBs()
  loadDocs()
  loadOrgUnits()
})
</script>

<style scoped>
.page-block {
  width: 100%;
}
.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-toolbar h3 {
  margin: 0;
}
.page-subtitle {
  margin: 4px 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.primary-cell {
  color: var(--color-text-primary);
  font-weight: 500;
  line-height: 1.35;
}
.secondary-cell {
  margin-top: 2px;
  color: var(--color-text-tertiary);
  font-size: 12px;
  line-height: 1.35;
}
:deep(.modal-select) {
  width: 100%;
}
</style>
