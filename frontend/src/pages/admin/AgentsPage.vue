<template>
  <div class="page-block">
    <div class="page-toolbar">
      <div>
        <h3>Agent 管理</h3>
        <p class="page-subtitle">管理所有智能体的配置、运行时和知识库绑定</p>
      </div>
      <a-button type="primary" @click="openCreate">
        <template #icon><PlusOutlined /></template>
        新建 Agent
      </a-button>
    </div>

    <!-- 错误态 -->
    <a-result
      v-if="error"
      status="error"
      title="加载失败"
      sub-title="无法获取 Agent 列表，请检查网络或管理员 Key"
    >
      <template #extra>
        <a-button type="primary" @click="load">重试</a-button>
      </template>
    </a-result>

    <!-- 空状态 / 表格 -->
    <a-empty
      v-else-if="items.length === 0 && !loading"
      description="暂无 Agent，点击上方按钮创建"
      style="margin-top: 48px"
    />
    <a-table
      v-else
      :columns="columns"
      :data-source="items"
      :loading="loading"
      :pagination="tablePagination"
      row-key="id"
      size="middle"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'publish_status'">
          <a-tag :color="statusColor(record.publish_status)">
            {{ statusText(record.publish_status) }}
          </a-tag>
        </template>
        <template v-if="column.key === 'agent'">
          <div class="primary-cell">{{ record.name }}</div>
          <div class="secondary-cell">{{ record.code }}</div>
        </template>
        <template v-if="column.key === 'description'">
          {{ record.description || '-' }}
        </template>
        <template v-if="column.key === 'updated_at'">
          {{ formatDateTime(record.updated_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-button type="link" size="small" @click="openEdit(record)">编辑</a-button>
        </template>
      </template>
    </a-table>

    <!-- 创建 / 编辑弹窗 -->
    <a-modal
      v-model:open="modalVisible"
      :title="editingId ? '编辑 Agent' : '新建 Agent'"
      :confirm-loading="submitting"
      @ok="submit"
      @cancel="resetForm"
      destroyOnClose
    >
      <a-form :model="form" layout="vertical">
        <a-form-item label="编码 (code)" required>
          <a-input v-model:value="form.code" :disabled="!!editingId" placeholder="唯一标识，如 qa-agent" />
        </a-form-item>
        <a-form-item label="名称" required>
          <a-input v-model:value="form.name" placeholder="Agent 显示名称" />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea v-model:value="form.description" :rows="2" placeholder="简要描述 Agent 的功能" />
        </a-form-item>
        <a-form-item label="所属组织" required>
          <a-select
            v-model:value="form.owner_org_unit_id"
            placeholder="选择所属组织"
            show-search
            :filter-option="filterOrgOption"
            :options="orgOptions"
          />
        </a-form-item>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item label="运行时类型">
              <a-select v-model:value="form.runtime_type" :options="runtimeOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="可见性">
              <a-select v-model:value="form.visibility" :options="visibilityOptions" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-form-item label="Dify App ID">
          <a-input v-model:value="form.runtime_app_id" placeholder="Dify 应用的 App ID" />
        </a-form-item>
        <a-form-item v-if="!editingId" label="发布状态">
          <a-select v-model:value="form.publish_status" :options="publishStatusOptions" />
        </a-form-item>
        <a-form-item v-if="editingId" label="发布状态">
          <a-select v-model:value="form.publish_status" :options="publishStatusOptions" />
        </a-form-item>

        <!-- 知识库绑定（仅编辑模式可用） -->
        <a-divider v-if="editingId" orientation="left" style="font-size:13px;margin-top:8px">
          知识库绑定
        </a-divider>

        <a-form-item v-if="editingId" label="已绑定 KB">
          <a-space wrap>
            <a-tag
              v-for="b in boundKbs"
              :key="b.knowledge_base_id"
              closable
              @close="unbindKb(b.knowledge_base_id)"
            >
              {{ kbName(b.knowledge_base_id) }}
              <template v-if="b.priority !== 100">
                (优先: {{ b.priority }})
              </template>
            </a-tag>
            <span v-if="boundKbs.length === 0" style="color: var(--color-text-secondary); font-size:13px">
              暂未绑定知识库
            </span>
          </a-space>
        </a-form-item>

        <a-form-item v-if="editingId" label="添加绑定">
          <a-space>
            <a-select
              v-model:value="selectedKbId"
              placeholder="选择知识库"
              style="width:220px"
              show-search
              :filter-option="(input: string, option: any) =>
                (option?.label ?? '').toLowerCase().includes(input.toLowerCase())"
              :options="availableKbs
                .filter(k => !boundKbs.some(b => b.knowledge_base_id === k.id))
                .map(k => ({ label: k.name, value: k.id }))"
            />
            <a-input-number
              v-model:value="bindPriority"
              :min="1"
              :max="999"
              style="width:80px"
              placeholder="优先级"
            />
            <a-button
              type="primary"
              size="small"
              :loading="bindingLoading"
              :disabled="!selectedKbId"
              @click="bindKb"
            >
              绑定
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { PlusOutlined } from '@ant-design/icons-vue'

import { bindKnowledgeBase, createAgent, listAgentKnowledgeBases, listAgents, listKnowledgeBases, listOrgUnits, unbindKnowledgeBase, updateAgent } from '../../api/admin'
import type { Agent, AgentCreate, AgentKnowledgeBaseBind, AgentUpdate, KnowledgeBase, OrgUnit } from '../../api/types'
import { formatDateTime } from '../../utils/format'

const loading = ref(false)
const error = ref(false)
const submitting = ref(false)
const items = ref<Agent[]>([])
const orgUnits = ref<OrgUnit[]>([])
const modalVisible = ref(false)
const editingId = ref<string | null>(null)

const emptyForm = () => ({
  code: '',
  name: '',
  description: '',
  owner_org_unit_id: '',
  runtime_type: 'DIFY',
  runtime_app_id: '',
  visibility: 'EXTERNAL',
  publish_status: 'DRAFT',
})
const form = reactive(emptyForm())

const runtimeOptions = [
  { label: 'Dify', value: 'DIFY' },
  { label: 'Custom', value: 'CUSTOM' },
]
const visibilityOptions = [
  { label: '外部可见', value: 'EXTERNAL' },
  { label: '仅内部', value: 'INTERNAL' },
  { label: '私有', value: 'PRIVATE' },
]
const publishStatusOptions = [
  { label: '草稿', value: 'DRAFT' },
  { label: '已发布', value: 'PUBLISHED' },
  { label: '已禁用', value: 'DISABLED' },
  { label: '已归档', value: 'ARCHIVED' },
]

const tablePagination = reactive({
  current: 1,
  pageSize: 10,
  pageSizeOptions: ['10', '20', '50'],
  showSizeChanger: true,
  size: 'small',
  showTotal: (t: number) => `共 ${t} 条`,
})

const orgOptions = computed(() => orgUnits.value.map(org => ({
  label: `${org.name}（${org.type}）`,
  value: org.id,
})))

const columns = [
  { title: '智能体', key: 'agent', width: 220 },
  { title: '用途说明', key: 'description', ellipsis: true },
  { title: '运行时', dataIndex: 'runtime_type', key: 'runtime_type', width: 90 },
  { title: '可见性', dataIndex: 'visibility', key: 'visibility', width: 100 },
  { title: '发布状态', key: 'publish_status', width: 100 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
  { title: '操作', key: 'action', width: 80 },
]

function statusColor(status: string) {
  const map: Record<string, string> = {
    PUBLISHED: 'success',
    DRAFT: 'processing',
    DISABLED: 'warning',
    ARCHIVED: 'default',
  }
  return map[status] ?? 'default'
}

function statusText(status: string) {
  const map: Record<string, string> = {
    PUBLISHED: '已发布',
    DRAFT: '草稿',
    DISABLED: '已禁用',
    ARCHIVED: '已归档',
  }
  return map[status] ?? status
}

async function load() {
  loading.value = true
  error.value = false
  try {
    items.value = await listAgents()
    tablePagination.current = 1
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function onTableChange(p: { current: number; pageSize: number }) {
  tablePagination.current = p.current
  tablePagination.pageSize = p.pageSize
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

function openCreate() {
  editingId.value = null
  Object.assign(form, emptyForm())
  boundKbs.value = []
  selectedKbId.value = undefined
  modalVisible.value = true
}

function openEdit(agent: Agent) {
  editingId.value = agent.id
  form.code = agent.code
  form.name = agent.name
  form.description = agent.description ?? ''
  form.owner_org_unit_id = agent.owner_org_unit_id
  form.runtime_type = agent.runtime_type
  form.runtime_app_id = agent.runtime_app_id ?? ''
  form.visibility = agent.visibility
  form.publish_status = agent.publish_status
  loadBindings(agent.id)
  modalVisible.value = true
}

function resetForm() {
  Object.assign(form, emptyForm())
  editingId.value = null
}

async function submit() {
  submitting.value = true
  try {
    if (editingId.value) {
      const payload: AgentUpdate = {
        name: form.name,
        description: form.description || undefined,
        runtime_type: form.runtime_type,
        runtime_app_id: form.runtime_app_id || undefined,
        publish_status: form.publish_status,
        visibility: form.visibility,
      }
      await updateAgent(editingId.value, payload)
    } else {
      const payload: AgentCreate = {
        code: form.code,
        name: form.name,
        description: form.description || undefined,
        owner_org_unit_id: form.owner_org_unit_id,
        runtime_type: form.runtime_type,
        runtime_app_id: form.runtime_app_id || undefined,
        visibility: form.visibility,
      }
      await createAgent(payload)
    }
    modalVisible.value = false
    resetForm()
    await load()
  } catch {
    // 错误由 http.ts 统一处理
  } finally {
    submitting.value = false
  }
}

// ── 知识库绑定 ──────────────────────────────
const availableKbs = ref<KnowledgeBase[]>([])
const boundKbs = ref<AgentKnowledgeBaseBind[]>([])
const selectedKbId = ref<string | undefined>(undefined)
const bindPriority = ref(100)
const bindingLoading = ref(false)

async function loadAvailableKbs() {
  try {
    availableKbs.value = await listKnowledgeBases()
  } catch { /* 静默处理 */ }
}

async function loadBindings(agentId: string) {
  try {
    boundKbs.value = await listAgentKnowledgeBases(agentId)
  } catch {
    boundKbs.value = []
  }
}

/** 获取 KB 名称（用于显示已绑定 KB 的 tag） */
function kbName(knowledgeBaseId: string): string {
  return availableKbs.value.find(k => k.id === knowledgeBaseId)?.name ?? knowledgeBaseId
}

async function bindKb() {
  if (!selectedKbId.value || !editingId.value) return
  bindingLoading.value = true
  try {
    await bindKnowledgeBase(editingId.value, selectedKbId.value, bindPriority.value)
    selectedKbId.value = undefined
    bindPriority.value = 100
    await loadBindings(editingId.value)
  } catch { /* 错误由 http.ts 处理 */ }
  finally { bindingLoading.value = false }
}

async function unbindKb(knowledgeBaseId: string) {
  if (!editingId.value) return
  bindingLoading.value = true
  try {
    await unbindKnowledgeBase(editingId.value, knowledgeBaseId)
    await loadBindings(editingId.value)
  } catch { /* 错误由 http.ts 处理 */ }
  finally { bindingLoading.value = false }
}

onMounted(() => { load(); loadAvailableKbs(); loadOrgUnits() })
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
</style>
