<template>
  <div class="page-block">
    <div class="page-toolbar">
      <div>
        <h3>API Key 管理</h3>
        <p class="page-subtitle">按手机号签发 API Key，查看和管理已有 Key</p>
      </div>
    </div>

    <!-- 手机号签发区域 -->
    <a-card title="按手机号签发 API Key" size="small" class="issue-card">
      <a-form layout="inline" @finish="issue">
        <a-form-item label="手机号" required>
          <a-input v-model:value="phone" placeholder="外部客户手机号" />
        </a-form-item>
        <a-form-item label="Key 名称" required>
          <a-input v-model:value="keyName" placeholder="便于识别的名称" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="issuing">签发</a-button>
        </a-form-item>
      </a-form>

      <!-- 签发成功后仅展示一次完整 Key -->
      <a-alert
        v-if="issuedKey"
        type="success"
        show-icon
        closable
        class="issued-alert"
        @close="issuedKey = ''"
      >
        <template #message>
          <div>
            <strong>签发成功！</strong>
            以下 Key 仅在本次展示，请立即复制保存：
          </div>
          <a-input-password
            :value="issuedKey"
            readonly
            class="key-display"
            @focus="$event.target.select()"
          />
          <a-button size="small" type="primary" ghost @click="copyKey">复制到剪贴板</a-button>
        </template>
      </a-alert>
    </a-card>

    <!-- 错误态 -->
    <a-result
      v-if="error"
      status="error"
      title="加载失败"
      sub-title="无法获取 API Key 列表"
      style="margin-top: 16px"
    >
      <template #extra>
        <a-button type="primary" @click="load">重试</a-button>
      </template>
    </a-result>

    <!-- 空状态 / 表格 -->
    <a-empty
      v-else-if="items.length === 0 && !loading"
      description="暂无 API Key，在上方按手机号签发"
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
      style="margin-top: 16px"
      @change="onTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'status'">
          <a-tag :color="keyStatusColor(record.status)">
            {{ keyStatusText(record.status) }}
          </a-tag>
        </template>
        <template v-if="column.key === 'customer'">
          <div class="primary-cell">{{ record.issued_for_phone || '-' }}</div>
          <div class="secondary-cell">{{ record.name }}</div>
        </template>
        <template v-if="column.key === 'scopes'">
          <a-tag v-for="s in record.scopes" :key="s" style="margin-right: 4px">{{ scopeText(s) }}</a-tag>
        </template>
        <template v-if="column.key === 'key_prefix'">
          <span class="mono-cell">{{ record.key_prefix }}...</span>
        </template>
        <template v-if="column.key === 'created_at'">
          {{ formatDateTime(record.created_at) }}
        </template>
        <template v-if="column.key === 'last_used_at'">
          {{ formatDateTime(record.last_used_at) }}
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { message } from 'ant-design-vue'

import { issueApiKeyByPhone, listApiKeys } from '../../api/admin'
import type { APIKeyRecord } from '../../api/types'
import { formatDateTime } from '../../utils/format'

const loading = ref(false)
const error = ref(false)
const issuing = ref(false)
const items = ref<APIKeyRecord[]>([])
const phone = ref('')
const keyName = ref('customer-key')
const issuedKey = ref('')

const tablePagination = reactive({
  current: 1,
  pageSize: 10,
  pageSizeOptions: ['10', '20', '50'],
  showSizeChanger: true,
  size: 'small',
  showTotal: (t: number) => `共 ${t} 条`,
  onShowSizeChange: (_current: number, size: number) => {
    tablePagination.current = 1
    tablePagination.pageSize = size
  },
})

const columns = [
  { title: '客户', key: 'customer', width: 210 },
  { title: 'Key 前缀', dataIndex: 'key_prefix', key: 'key_prefix', width: 130 },
  { title: '权限范围', key: 'scopes', width: 150 },
  { title: '状态', key: 'status', width: 90 },
  { title: '最近使用', dataIndex: 'last_used_at', key: 'last_used_at', width: 170 },
  { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170 },
]

function keyStatusColor(status: string) {
  const map: Record<string, string> = {
    ACTIVE: 'green',
    DISABLED: 'orange',
    EXPIRED: 'red',
    REVOKED: 'red',
  }
  return map[status] ?? 'default'
}

function keyStatusText(status: string) {
  const map: Record<string, string> = {
    ACTIVE: '启用',
    DISABLED: '禁用',
    EXPIRED: '过期',
    REVOKED: '撤销',
  }
  return map[status] ?? status
}

function scopeText(scope: string) {
  const map: Record<string, string> = {
    invoke: '调用',
    read: '读取',
    manage: '管理',
    '*': '全部',
  }
  return map[scope] ?? scope
}

async function load() {
  loading.value = true
  error.value = false
  try {
    items.value = await listApiKeys()
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

async function issue() {
  issuing.value = true
  try {
    const result = await issueApiKeyByPhone({
      phone: phone.value.trim(),
      name: keyName.value,
      scopes: ['invoke'],
    })
    issuedKey.value = result.api_key
    await load()
  } catch {
    // 错误由 http 层处理
  } finally {
    issuing.value = false
  }
}

async function copyKey() {
  await navigator.clipboard.writeText(issuedKey.value)
  message.success('已复制到剪贴板')
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
.issue-card {
  margin-bottom: 0;
  border-left: 3px solid var(--color-primary);
}
.page-subtitle {
  margin: 4px 0 0;
  color: var(--color-text-secondary);
  font-size: 13px;
}
.key-display {
  margin: 8px 0;
  max-width: 520px;
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
.mono-cell {
  font-family: var(--font-mono);
  color: var(--color-text-secondary);
}
</style>
