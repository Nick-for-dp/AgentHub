<template>
  <div class="page-block">
    <div class="page-toolbar">
      <div>
        <h3>调用记录</h3>
        <p class="page-subtitle">查看 Agent 调用的请求、响应、耗时和运行时快照</p>
      </div>
    </div>

    <!-- 错误态 -->
    <a-result
      v-if="error"
      status="error"
      title="加载失败"
      sub-title="无法获取调用记录"
    >
      <template #extra>
        <a-button type="primary" @click="load">重试</a-button>
      </template>
    </a-result>

    <template v-else>

    <!-- 筛选栏 -->
    <a-card size="small" class="filter-card" style="margin-bottom: 16px">
      <form class="filter-form" @submit.prevent="search">
        <label class="filter-field filter-agent">
          <span class="filter-label">智能体</span>
          <a-input v-model:value="filter.agent_code" placeholder="输入智能体编码" allow-clear size="small" />
        </label>
        <label class="filter-field filter-status">
          <span class="filter-label">状态</span>
          <a-radio-group
            v-model:value="filter.status"
            size="small"
            option-type="button"
            button-style="solid"
            :options="statusOptions"
            @change="handleStatusChange"
          />
        </label>
        <label class="filter-field filter-date">
          <span class="filter-label">开始时间</span>
          <a-date-picker
            v-model:value="filter.created_from"
            show-time
            format="YYYY-MM-DD HH:mm:ss"
            placeholder="开始时间"
            allow-clear
            size="small"
          />
        </label>
        <label class="filter-field filter-date">
          <span class="filter-label">截止时间</span>
          <a-date-picker
            v-model:value="filter.created_to"
            show-time
            format="YYYY-MM-DD HH:mm:ss"
            placeholder="截止时间"
            allow-clear
            size="small"
          />
        </label>
        <div class="filter-actions">
          <a-button type="primary" html-type="submit" size="small">查询</a-button>
          <a-button size="small" @click="resetFilter">重置</a-button>
        </div>
      </form>
    </a-card>

    <!-- 表格 -->
    <a-table
      :columns="columns"
      :data-source="records"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      size="middle"
      style="margin-top: 16px"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="invokeStatusColor(record.status)">
            {{ invokeStatusText(record.status) }}
          </a-tag>
        </template>
        <template v-if="column.key === 'customer'">
          <div class="primary-cell">{{ record.customer_phone || '-' }}</div>
          <div class="secondary-cell">{{ record.customer_name || record.org_unit_name || '-' }}</div>
        </template>
        <template v-if="column.key === 'agent'">
          <div class="primary-cell">{{ record.agent_name || record.agent_code || '-' }}</div>
          <div class="secondary-cell">{{ record.agent_code || '-' }}</div>
        </template>
        <template v-if="column.key === 'question'">
          <span class="question-text">{{ questionSummary(record) }}</span>
        </template>
        <template v-if="column.key === 'latency_ms'">
          {{ formatLatency(record.latency_ms) }}
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDateTime(record.created_at) }}
        </template>
        <template v-if="column.key === 'action'">
          <a-button type="link" size="small" @click="openDetail(record)">详情</a-button>
        </template>
      </template>
    </a-table>

    <!-- 详情抽屉 -->
    <a-drawer
      title="调用详情"
      :open="detailVisible"
      :width="560"
      @close="detailVisible = false"
    >
      <template v-if="detail">
        <a-descriptions :column="1" size="small" bordered>
          <a-descriptions-item label="客户电话">{{ detail.customer_phone ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="客户名称">{{ detail.customer_name ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="客户组织">{{ detail.org_unit_name ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="Agent">{{ detail.agent_name ?? detail.agent_code ?? detail.agent_id }}</a-descriptions-item>
          <a-descriptions-item label="Agent Code">{{ detail.agent_code ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="Request ID">{{ detail.request_id }}</a-descriptions-item>
          <a-descriptions-item label="状态">
            <a-tag :color="invokeStatusColor(detail.status)">{{ detail.status }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="调用方式">{{ detail.caller_type === 'USER' ? '网页登录' : 'API Key' }}</a-descriptions-item>
          <a-descriptions-item v-if="detail.api_key_id" label="API Key">{{ detail.api_key_name ?? detail.api_key_prefix ?? detail.api_key_id }}</a-descriptions-item>
          <a-descriptions-item label="渠道">{{ detail.source_channel ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="耗时">{{ formatLatency(detail.latency_ms) }}</a-descriptions-item>
          <a-descriptions-item label="错误码">{{ detail.error_code ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="错误信息">{{ detail.error_message ?? '-' }}</a-descriptions-item>
          <a-descriptions-item label="创建时间">{{ formatDateTime(detail.created_at) }}</a-descriptions-item>
          <a-descriptions-item label="完成时间">{{ formatDateTime(detail.finished_at) }}</a-descriptions-item>
        </a-descriptions>

        <a-divider />

        <h4>输入 (input)</h4>
        <pre class="json-block">{{ JSON.stringify(detail.input, null, 2) }}</pre>

        <h4>输出 (output)</h4>
        <pre class="json-block">{{ JSON.stringify(detail.output, null, 2) }}</pre>

        <h4>运行时快照 (runtime_snapshot)</h4>
        <pre class="json-block">{{ JSON.stringify(detail.runtime_snapshot, null, 2) }}</pre>

        <h4>Token 用量</h4>
        <pre class="json-block">{{ JSON.stringify(detail.token_usage, null, 2) }}</pre>
      </template>
    </a-drawer>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { Dayjs } from 'dayjs'

import { listInvocationRecords } from '../../api/admin'
import type { InvocationRecord } from '../../api/types'
import { formatDateTime, toISOString } from '../../utils/format'

const loading = ref(false)
const error = ref(false)
const records = ref<InvocationRecord[]>([])
const total = ref(0)

const filter = reactive({
  agent_code: '' as string | undefined,
  status: '',
  created_from: undefined as Dayjs | undefined,
  created_to: undefined as Dayjs | undefined,
  page: 1,
  page_size: 10,
})

const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  pageSizeOptions: ['10', '20', '50'],
  size: 'small',
  showTotal: (t: number) => `共 ${t} 条`,
})

const statusOptions = [
  { label: '全部', value: '' },
  { label: '成功', value: 'SUCCEEDED' },
  { label: '失败', value: 'FAILED' },
]

const columns = [
  { title: '客户', key: 'customer', width: 180 },
  { title: '智能体', key: 'agent', width: 180 },
  { title: '提问摘要', key: 'question', ellipsis: true },
  { title: '状态', key: 'status', width: 92 },
  { title: '耗时', key: 'latency_ms', width: 90 },
  { title: '调用时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: '操作', key: 'action', width: 70 },
]

// ---- 详情抽屉 ----
const detailVisible = ref(false)
const detail = ref<InvocationRecord | null>(null)

function openDetail(record: InvocationRecord) {
  detail.value = record
  detailVisible.value = true
}

// ---- 查询 ----
async function load() {
  loading.value = true
  error.value = false
  try {
    const result = await listInvocationRecords({
      agent_code: filter.agent_code || undefined,
      status: filter.status || undefined,
      created_from: toISOString(filter.created_from),
      created_to: toISOString(filter.created_to),
      page: filter.page,
      page_size: filter.page_size,
    })
    records.value = result.items
    total.value = result.total
    pagination.current = result.page
    pagination.pageSize = result.page_size
    pagination.total = result.total
  } catch {
    error.value = true
  } finally {
    loading.value = false
  }
}

function search() {
  detailVisible.value = false
  detail.value = null
  filter.page = 1
  pagination.current = 1
  load()
}

function resetFilter() {
  detailVisible.value = false
  detail.value = null
  filter.agent_code = ''
  filter.status = ''
  filter.created_from = undefined
  filter.created_to = undefined
  filter.page = 1
  pagination.current = 1
  load()
}

function handleStatusChange() {
  search()
}

function onTableChange(p: { current: number; pageSize: number }) {
  detailVisible.value = false
  detail.value = null
  const pageSizeChanged = p.pageSize !== filter.page_size
  filter.page = pageSizeChanged ? 1 : p.current
  filter.page_size = p.pageSize
  pagination.current = filter.page
  pagination.pageSize = p.pageSize
  load()
}

function invokeStatusColor(status: string) {
  const map: Record<string, string> = {
    SUCCEEDED: 'green',
    FAILED: 'red',
    STREAMING: 'blue',
    PENDING: 'default',
  }
  return map[status] ?? 'default'
}

function invokeStatusText(status: string) {
  const map: Record<string, string> = {
    SUCCEEDED: '成功',
    FAILED: '失败',
    STREAMING: '进行中',
    PENDING: '等待中',
  }
  return map[status] ?? status
}

function questionSummary(record: InvocationRecord): string {
  const value = record.input?.question
  return typeof value === 'string' && value.trim() ? value : '-'
}

function formatLatency(value: number | undefined): string {
  if (value == null) return '-'
  return value >= 1000 ? `${(value / 1000).toFixed(1)} s` : `${value} ms`
}

onMounted(load)
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
.filter-card {
  margin-bottom: 0;
  overflow-x: auto;
}
.filter-form {
  display: grid;
  grid-template-columns: 220px 220px 214px 214px auto;
  gap: 10px;
  align-items: center;
  min-width: 962px;
}
.filter-field {
  display: flex;
  align-items: center;
  margin: 0;
  min-width: 0;
}
.filter-label {
  flex: 0 0 auto;
  margin-right: 6px;
  color: var(--color-text-secondary);
  font-size: 13px;
  line-height: 32px;
}
.filter-form :deep(.ant-form-item-control-input),
.filter-form :deep(.ant-input),
.filter-form :deep(.ant-picker),
.filter-form :deep(.ant-select-selector),
.filter-form :deep(.ant-btn) {
  min-height: 32px !important;
  height: 32px;
}
.filter-form :deep(.ant-picker),
.filter-form :deep(.ant-select),
.filter-form :deep(.ant-input) {
  flex: 1 1 auto;
  width: 100% !important;
  min-width: 0;
}
.filter-form :deep(.ant-radio-button-wrapper) {
  height: 32px;
  line-height: 30px;
  padding-inline: 10px;
}
.filter-form :deep(.ant-radio-group) {
  white-space: nowrap;
}
.filter-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.filter-actions :deep(.ant-btn) {
  padding-inline: 14px;
}
.json-block {
  max-height: 320px;
  overflow: auto;
  background: var(--color-code-inline-bg);
  border: 1px solid var(--color-border);
  padding: 12px;
  border-radius: var(--radius);
  font-size: 12px;
  line-height: 1.5;
  font-family: var(--font-mono);
  white-space: pre-wrap;
  word-break: break-all;
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
.question-text {
  color: var(--color-text-primary);
}
@media (max-width: 1180px) {
  .filter-form {
    grid-template-columns: 210px 210px 206px 206px auto;
    min-width: 932px;
  }
}
</style>
