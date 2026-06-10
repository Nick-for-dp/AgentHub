<template>
  <div class="page-block">
    <div class="page-toolbar">
      <div>
        <h3>数据分析</h3>
        <p class="page-subtitle">基于聊天和线索事实的轻量运营指标，不依赖独立埋点体系</p>
      </div>
    </div>

    <a-result
      v-if="error"
      status="error"
      title="加载失败"
      sub-title="无法获取统计数据"
    >
      <template #extra>
        <a-button type="primary" @click="loadActiveTab">重试</a-button>
      </template>
    </a-result>

    <template v-else>
      <!-- 全局筛选 -->
      <a-card size="small" class="filter-card" style="margin-bottom: 16px">
        <form class="filter-form" @submit.prevent="search">
          <label class="filter-field filter-date">
            <span class="filter-label">时间范围</span>
            <a-range-picker
              v-model:value="filter.dateRange"
              show-time
              format="YYYY-MM-DD HH:mm:ss"
              :placeholder="['开始时间', '结束时间']"
              allow-clear
              size="small"
            />
          </label>
          <label class="filter-field filter-agent">
            <span class="filter-label">Agent</span>
            <a-input v-model:value="filter.agentCode" placeholder="agent code" allow-clear size="small" />
          </label>
          <label class="filter-field filter-user">
            <span class="filter-label">用户 ID</span>
            <a-input v-model:value="filter.userId" placeholder="user id" allow-clear size="small" />
          </label>
          <label class="filter-field filter-org">
            <span class="filter-label">组织 ID</span>
            <a-input v-model:value="filter.orgUnitId" placeholder="org unit id" allow-clear size="small" />
          </label>
          <div class="filter-actions">
            <a-button type="primary" html-type="submit" size="small">查询</a-button>
            <a-button size="small" @click="resetFilter">重置</a-button>
          </div>
        </form>
      </a-card>

      <!-- 指标 Tab -->
      <a-tabs v-model:activeKey="activeTab" @change="onTabChange">
        <a-tab-pane key="dau" tab="日活趋势" />
        <a-tab-pane key="messages" tab="消息排行" />
        <a-tab-pane key="duration" tab="活跃跨度" />
        <a-tab-pane key="followups" tab="业务追问" />
      </a-tabs>

      <!-- 日活趋势 -->
      <a-table
        v-if="activeTab === 'dau'"
        :columns="dauColumns"
        :data-source="dauData"
        :loading="loading"
        :pagination="false"
        row-key="date"
        size="middle"
        style="margin-top: 0"
      />

      <!-- 用户消息排行 -->
      <a-table
        v-if="activeTab === 'messages'"
        :columns="msgColumns"
        :data-source="msgData.items"
        :loading="loading"
        :pagination="msgPagination"
        row-key="user_id"
        size="middle"
        style="margin-top: 0"
        @change="onMsgTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'user'">
            <div class="primary-cell">{{ record.user_name || '-' }}</div>
            <div class="secondary-cell">{{ record.phone_normalized || '未留电话' }}</div>
          </template>
          <template v-if="column.key === 'org'">
            {{ record.org_unit_name || '-' }}
          </template>
          <template v-if="column.key === 'agents'">
            <a-tag v-for="code in record.agent_codes" :key="code" color="blue" size="small">{{ code }}</a-tag>
            <span v-if="!record.agent_codes.length">-</span>
          </template>
          <template v-if="column.key === 'last_message_at'">
            {{ formatDateTime(record.last_message_at) }}
          </template>
        </template>
      </a-table>

      <!-- 聊天活跃跨度 -->
      <div v-if="activeTab === 'duration'">
        <a-table
          :columns="durColumns"
          :data-source="durData.items"
          :loading="loading"
          :pagination="durPagination"
          :row-key="durationRowKey"
          size="middle"
          style="margin-top: 0"
          @change="onDurTableChange"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'user'">
              <div class="primary-cell">{{ record.user_name || '-' }}</div>
            </template>
            <template v-if="column.key === 'span'">
              {{ formatDuration(record.duration_seconds) }}
            </template>
            <template v-if="column.key === 'time_range'">
              <div>{{ formatDateTime(record.first_message_at) }}</div>
              <div>{{ formatDateTime(record.last_message_at) }}</div>
            </template>
          </template>
        </a-table>
        <div class="metric-note">* 聊天活跃跨度根据用户当天首末条消息时间估算，非严格页面停留时长。</div>
      </div>

      <!-- 业务追问次数 -->
      <a-table
        v-if="activeTab === 'followups'"
        :columns="fwColumns"
        :data-source="fwData.items"
        :loading="loading"
        :pagination="fwPagination"
        row-key="agent_code"
        size="middle"
        style="margin-top: 0"
        @change="onFwTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'agent'">
            <div class="primary-cell">{{ record.agent_name || record.agent_code || '-' }}</div>
            <div class="secondary-cell">{{ record.agent_code || '-' }}</div>
          </template>
        </template>
      </a-table>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { Dayjs } from 'dayjs'

import {
  fetchAgentBusinessFollowups,
  fetchDailyActiveUsers,
  fetchUserChatDuration,
  fetchUserMessageCounts,
} from '../../api/admin'
import type {
  AgentBusinessFollowupItem,
  DAUItem,
  UserChatDurationItem,
  UserMessageCountItem,
} from '../../api/types'
import { formatDateTime, toISOString } from '../../utils/format'

// ── 状态 ──

const loading = ref(false)
const error = ref(false)
const activeTab = ref('dau')

// 日活趋势
const dauData = ref<DAUItem[]>([])

// 消息排行
const msgData = reactive<{
  items: UserMessageCountItem[]
  total: number
  page: number
  page_size: number
}>({ items: [], total: 0, page: 1, page_size: 10 })

// 活跃跨度
const durData = reactive<{
  items: UserChatDurationItem[]
  total: number
  page: number
  page_size: number
}>({ items: [], total: 0, page: 1, page_size: 10 })

// 业务追问
const fwData = reactive<{
  items: AgentBusinessFollowupItem[]
  total: number
  page: number
  page_size: number
}>({ items: [], total: 0, page: 1, page_size: 10 })

// 全局筛选
const filter = reactive({
  dateRange: undefined as [Dayjs, Dayjs] | undefined,
  agentCode: '',
  userId: '',
  orgUnitId: '',
})

let requestSeq = 0

// ── 分页对象 ──

const msgPagination = makePagination(msgData, 'msg')
const durPagination = makePagination(durData, 'dur')
const fwPagination = makePagination(fwData, 'fw')

function makePagination(
  data: { total: number; page: number; page_size: number },
  _label: string,
) {
  return reactive({
    current: data.page,
    pageSize: data.page_size,
    total: data.total,
    showSizeChanger: true,
    pageSizeOptions: ['10', '20', '50'],
    size: 'small' as const,
    showTotal: (t: number) => `共 ${t} 条`,
  })
}

// ── 列定义 ──

const dauColumns = [
  { title: '日期', dataIndex: 'date', key: 'date', width: 160 },
  { title: '活跃用户数', dataIndex: 'active_users', key: 'active_users', width: 140 },
]

const msgColumns = [
  { title: '用户', key: 'user', ellipsis: true },
  { title: '组织', key: 'org', width: 150 },
  { title: '消息数', dataIndex: 'message_count', key: 'message_count', width: 100, sorter: false },
  { title: '关联 Agent', key: 'agents', width: 180 },
  { title: '最近发送时间', key: 'last_message_at', width: 170 },
]

const durColumns = [
  { title: '用户', key: 'user', width: 140 },
  { title: '日期', dataIndex: 'chat_date', key: 'chat_date', width: 120 },
  { title: '消息数', dataIndex: 'message_count', key: 'message_count', width: 90 },
  { title: '估算跨度', key: 'span', width: 130 },
  { title: '首条 / 末条时间', key: 'time_range', width: 340 },
]

const fwColumns = [
  { title: '智能体', key: 'agent', width: 200 },
  { title: '追问次数', dataIndex: 'followup_count', key: 'followup_count', width: 120 },
]

// ── 数据加载 ──

function buildFilterParams(overrides: { page?: number; page_size?: number } = {}) {
  return {
    created_from: toISOString(filter.dateRange?.[0]),
    created_to: toISOString(filter.dateRange?.[1]),
    agent_code: filter.agentCode || undefined,
    user_id: filter.userId || undefined,
    org_unit_id: filter.orgUnitId || undefined,
    page: overrides.page ?? 1,
    page_size: overrides.page_size ?? 10,
  }
}

function isLatestRequest(seq?: number): boolean {
  return seq == null || seq === requestSeq
}

async function loadDAU(seq?: number) {
  const params = buildFilterParams()
  const result = await fetchDailyActiveUsers(params)
  if (!isLatestRequest(seq)) return
  dauData.value = result
}

async function loadMessages(p?: { page?: number; page_size?: number }, seq?: number) {
  const params = buildFilterParams({ page: msgData.page, page_size: msgData.page_size, ...p })
  const result = await fetchUserMessageCounts(params)
  if (!isLatestRequest(seq)) return
  msgData.items = result.items
  msgData.total = result.total
  msgData.page = result.page
  msgData.page_size = result.page_size
  syncPagination(msgPagination, msgData)
}

async function loadDuration(p?: { page?: number; page_size?: number }, seq?: number) {
  const params = buildFilterParams({ page: durData.page, page_size: durData.page_size, ...p })
  const result = await fetchUserChatDuration(params)
  if (!isLatestRequest(seq)) return
  durData.items = result.items
  durData.total = result.total
  durData.page = result.page
  durData.page_size = result.page_size
  syncPagination(durPagination, durData)
}

async function loadFollowups(p?: { page?: number; page_size?: number }, seq?: number) {
  const params = buildFilterParams({ page: fwData.page, page_size: fwData.page_size, ...p })
  const result = await fetchAgentBusinessFollowups(params)
  if (!isLatestRequest(seq)) return
  fwData.items = result.items
  fwData.total = result.total
  fwData.page = result.page
  fwData.page_size = result.page_size
  syncPagination(fwPagination, fwData)
}

function syncPagination(
  pag: { current: number; pageSize: number; total: number },
  data: { page: number; page_size: number; total: number },
) {
  pag.current = data.page
  pag.pageSize = data.page_size
  pag.total = data.total
}

async function loadActiveTab() {
  const seq = ++requestSeq
  loading.value = true
  error.value = false
  try {
    switch (activeTab.value) {
      case 'dau': await loadDAU(seq); break
      case 'messages': await loadMessages(undefined, seq); break
      case 'duration': await loadDuration(undefined, seq); break
      case 'followups': await loadFollowups(undefined, seq); break
    }
  } catch {
    if (seq === requestSeq) {
      error.value = true
    }
  } finally {
    if (seq === requestSeq) {
      loading.value = false
    }
  }
}

// ── 交互 ──

function search() {
  // 重置各 Tab 分页
  msgData.page = 1
  durData.page = 1
  fwData.page = 1
  loadActiveTab()
}

function resetFilter() {
  filter.dateRange = undefined
  filter.agentCode = ''
  filter.userId = ''
  filter.orgUnitId = ''
  search()
}

function onTabChange() {
  loadActiveTab()
}

function onMsgTableChange(p: { current: number; pageSize: number }) {
  const changed = p.pageSize !== msgData.page_size
  if (changed) msgData.page = 1
  else msgData.page = p.current
  msgData.page_size = p.pageSize
  loadMessages()
}

function onDurTableChange(p: { current: number; pageSize: number }) {
  const changed = p.pageSize !== durData.page_size
  if (changed) durData.page = 1
  else durData.page = p.current
  durData.page_size = p.pageSize
  loadDuration()
}

function onFwTableChange(p: { current: number; pageSize: number }) {
  const changed = p.pageSize !== fwData.page_size
  if (changed) fwData.page = 1
  else fwData.page = p.current
  fwData.page_size = p.pageSize
  loadFollowups()
}

// ── 格式化 ──

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds} 秒`
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟`
  return `${Math.round(seconds / 3600 * 10) / 10} 小时`
}

function durationRowKey(record: UserChatDurationItem): string {
  return `${record.user_id}-${record.chat_date}`
}

// ── 初始化 ──

onMounted(loadActiveTab)
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
  grid-template-columns: minmax(320px, 1.4fr) minmax(160px, 0.7fr) minmax(180px, 0.8fr) minmax(180px, 0.8fr) auto;
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
@media (max-width: 880px) {
  .filter-form {
    grid-template-columns: 1fr;
  }
  .filter-actions {
    grid-column: 1;
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
.metric-note {
  margin-top: 8px;
  color: var(--color-text-tertiary);
  font-size: 12px;
  font-style: italic;
}
:deep(.ant-tabs) {
  margin-bottom: 0;
}
:deep(.ant-tabs-nav) {
  margin-bottom: 12px;
}
</style>
