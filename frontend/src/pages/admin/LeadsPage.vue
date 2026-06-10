<template>
  <div class="page-block">
    <div class="page-toolbar">
      <div>
        <h3>线索记录</h3>
        <p class="page-subtitle">查看 Dify 对话流识别并由 AgentHub 落库的业务线索</p>
      </div>
    </div>

    <a-result
      v-if="error"
      status="error"
      title="加载失败"
      sub-title="无法获取线索记录"
    >
      <template #extra>
        <a-button type="primary" @click="load">重试</a-button>
      </template>
    </a-result>

    <template v-else>
      <a-card size="small" class="filter-card" style="margin-bottom: 16px">
        <form class="filter-form" @submit.prevent="search">
          <label class="filter-field filter-keyword">
            <span class="filter-label">关键词</span>
            <a-input v-model:value="filter.keyword" placeholder="需求、地区、公司、电话" allow-clear size="small" />
          </label>
          <label class="filter-field filter-status">
            <span class="filter-label">状态</span>
            <a-select
              v-model:value="filter.status"
              :options="statusOptions"
              size="small"
              style="width: 100%"
              @change="search"
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
            <span class="filter-label">结束时间</span>
            <a-date-picker
              v-model:value="filter.created_to"
              show-time
              format="YYYY-MM-DD HH:mm:ss"
              placeholder="结束时间"
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

      <a-table
        :columns="columns"
        :data-source="leads"
        :loading="loading"
        :pagination="pagination"
        row-key="id"
        size="middle"
        style="margin-top: 16px"
        @change="onTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'requirement'">
            <div class="primary-cell">{{ record.requirement_summary || '-' }}</div>
            <div class="tag-line">
              <a-tag v-for="type in record.requirement_types" :key="type" color="blue">{{ type }}</a-tag>
              <span v-if="!record.requirement_types.length" class="secondary-cell">-</span>
            </div>
          </template>
          <template v-if="column.key === 'customer'">
            <div class="primary-cell">{{ record.company_name || record.customer_name || '-' }}</div>
            <div class="secondary-cell">{{ record.contact_value || record.phone_normalized || '未留联系方式' }}</div>
          </template>
          <template v-if="column.key === 'agent'">
            <div class="primary-cell">{{ record.agent_name || record.agent_code || '-' }}</div>
            <div class="secondary-cell">{{ record.agent_code || '-' }}</div>
          </template>
          <template v-if="column.key === 'region'">
            {{ record.region || '-' }}
          </template>
          <template v-if="column.key === 'status'">
            <a-tag :color="leadStatusColor(record.status)">{{ leadStatusText(record.status) }}</a-tag>
          </template>
          <template v-if="column.key === 'missing_fields'">
            <span v-if="!record.missing_fields.length">-</span>
            <a-tag v-for="field in record.missing_fields" v-else :key="field" color="orange">
              {{ missingFieldText(field) }}
            </a-tag>
          </template>
          <template v-if="column.key === 'updated_at'">
            {{ formatDateTime(record.updated_at) }}
          </template>
          <template v-if="column.key === 'action'">
            <a-button type="link" size="small" @click="openDetail(record)">详情</a-button>
          </template>
        </template>
      </a-table>

      <a-drawer
        title="线索详情"
        :open="detailVisible"
        :width="620"
        @close="detailVisible = false"
      >
        <template v-if="detail">
          <a-descriptions :column="1" size="small" bordered>
            <a-descriptions-item label="线索 ID">{{ detail.id }}</a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="leadStatusColor(detail.status)">{{ leadStatusText(detail.status) }}</a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="需求摘要">{{ detail.requirement_summary || '-' }}</a-descriptions-item>
            <a-descriptions-item label="需求类型">{{ detail.requirement_types.join('、') || '-' }}</a-descriptions-item>
            <a-descriptions-item label="地域">{{ detail.region || '-' }}</a-descriptions-item>
            <a-descriptions-item label="缺失字段">{{ detail.missing_fields.map(missingFieldText).join('、') || '-' }}</a-descriptions-item>
            <a-descriptions-item label="客户姓名">{{ detail.customer_name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="公司名称">{{ detail.company_name || '-' }}</a-descriptions-item>
            <a-descriptions-item label="联系方式">{{ detail.contact_value || detail.phone_normalized || '-' }}</a-descriptions-item>
            <a-descriptions-item label="智能体">{{ detail.agent_name || detail.agent_code || '-' }}</a-descriptions-item>
            <a-descriptions-item label="会话 ID">{{ detail.conversation_id || '-' }}</a-descriptions-item>
            <a-descriptions-item label="事件数">{{ detail.event_count }}</a-descriptions-item>
            <a-descriptions-item label="创建时间">{{ formatDateTime(detail.created_at) }}</a-descriptions-item>
            <a-descriptions-item label="更新时间">{{ formatDateTime(detail.updated_at) }}</a-descriptions-item>
          </a-descriptions>

          <template v-if="detail.latest_event">
            <a-divider />
            <h4>最近捕获事件</h4>
            <a-descriptions :column="1" size="small" bordered>
              <a-descriptions-item label="事件状态">{{ detail.latest_event.status }}</a-descriptions-item>
              <a-descriptions-item label="动作">{{ detail.latest_event.action || '-' }}</a-descriptions-item>
              <a-descriptions-item label="原因">{{ detail.latest_event.reason || '-' }}</a-descriptions-item>
              <a-descriptions-item label="调用记录">{{ detail.latest_event.invocation_record_id || '-' }}</a-descriptions-item>
              <a-descriptions-item label="捕获时间">{{ formatDateTime(detail.latest_event.created_at) }}</a-descriptions-item>
            </a-descriptions>

            <h4>lead_deltas</h4>
            <pre class="json-block">{{ JSON.stringify(detail.latest_event.normalized_delta, null, 2) }}</pre>

            <h4>followup_decision</h4>
            <pre class="json-block">{{ JSON.stringify(detail.latest_event.followup_decision, null, 2) }}</pre>
          </template>
        </template>
      </a-drawer>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { Dayjs } from 'dayjs'

import { listSalesLeads } from '../../api/admin'
import type { SalesLead } from '../../api/types'
import { formatDateTime, toISOString } from '../../utils/format'

const loading = ref(false)
const error = ref(false)
const leads = ref<SalesLead[]>([])

const filter = reactive({
  keyword: '',
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
  { label: '待补充', value: 'PROVISIONAL' },
  { label: '已识别', value: 'IDENTIFIED' },
  { label: '已完整', value: 'QUALIFIED' },
  { label: '已关闭', value: 'CLOSED' },
  { label: '已丢弃', value: 'DISCARDED' },
]

const columns = [
  { title: '需求', key: 'requirement', ellipsis: true },
  { title: '客户', key: 'customer', width: 190 },
  { title: '地域', key: 'region', width: 100 },
  { title: '智能体', key: 'agent', width: 160 },
  { title: '状态', key: 'status', width: 92 },
  { title: '待补充', key: 'missing_fields', width: 150 },
  { title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 170 },
  { title: '操作', key: 'action', width: 70 },
]

const detailVisible = ref(false)
const detail = ref<SalesLead | null>(null)

function openDetail(record: SalesLead) {
  detail.value = record
  detailVisible.value = true
}

async function load() {
  loading.value = true
  error.value = false
  try {
    const result = await listSalesLeads({
      keyword: filter.keyword || undefined,
      status: filter.status || undefined,
      created_from: toISOString(filter.created_from),
      created_to: toISOString(filter.created_to),
      page: filter.page,
      page_size: filter.page_size,
    })
    leads.value = result.items
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
  filter.keyword = ''
  filter.status = ''
  filter.created_from = undefined
  filter.created_to = undefined
  filter.page = 1
  pagination.current = 1
  load()
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

function leadStatusColor(status: string) {
  const map: Record<string, string> = {
    PROVISIONAL: 'orange',
    IDENTIFIED: 'blue',
    QUALIFIED: 'green',
    CLOSED: 'default',
    DISCARDED: 'red',
  }
  return map[status] ?? 'default'
}

function leadStatusText(status: string) {
  const map: Record<string, string> = {
    PROVISIONAL: '待补充',
    IDENTIFIED: '已识别',
    QUALIFIED: '已完整',
    CLOSED: '已关闭',
    DISCARDED: '已丢弃',
  }
  return map[status] ?? status
}

function missingFieldText(field: string) {
  const map: Record<string, string> = {
    requirement: '需求',
    region: '地域',
    contact: '联系方式',
  }
  return map[field] ?? field
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
.page-subtitle {
  margin: 4px 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.filter-card {
  margin-bottom: 0;
  overflow-x: auto;
}
.filter-form {
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) 150px 214px 214px auto;
  gap: 10px;
  align-items: center;
  min-width: 0;
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
.filter-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
@media (max-width: 1180px) {
  .filter-form {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }
  .filter-actions {
    grid-column: 1 / -1;
  }
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
.tag-line {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
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
</style>
