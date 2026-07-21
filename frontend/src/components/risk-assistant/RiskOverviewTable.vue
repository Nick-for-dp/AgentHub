<template>
  <a-card class="overview-card" :bordered="false">
    <template #title>
      <div class="overview-title">
        <div>
          <strong>业务总览</strong>
          <span>与导出审计底稿使用同一后端投影</span>
        </div>
        <a-tag v-if="projection">{{ projection.rows.length }} 项</a-tag>
      </div>
    </template>

    <a-empty v-if="!projection" description="当前任务尚未生成业务总览" />
    <div v-else class="overview-scroll">
      <table>
        <thead>
          <tr>
            <th>项目</th>
            <th>内容</th>
            <th>来源文件</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in projection.rows"
            :key="row.code"
            :class="{ 'row-clickable': hasAuditItem(row.field_codes) }"
            @click="showAudit(row.field_codes)"
          >
            <th scope="row">{{ row.label }}</th>
            <td class="content-cell">{{ row.content }}</td>
            <td>
              <div v-if="row.source_files.length" class="source-list">
                <a-tag v-for="source in row.source_files" :key="source" :title="source">{{ source }}</a-tag>
                <a-tag v-if="row.is_human_reviewed" color="purple">人工复核</a-tag>
              </div>
              <span v-else class="muted">-</span>
            </td>
            <td><a-tag :color="statusColor(row.status)">{{ statusLabel(row.status) }}</a-tag></td>
          </tr>
        </tbody>
      </table>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import type {
  BusinessOverviewProjection,
  BusinessOverviewStatus,
  RiskAuditItem,
} from '../../api/internalRiskAssistant'

const props = defineProps<{
  projection?: BusinessOverviewProjection | null
  auditItems: RiskAuditItem[]
}>()

const emit = defineEmits<{
  'show-audit': [items: RiskAuditItem[]]
}>()

function hasAuditItem(fieldCodes: string[]): boolean {
  return props.auditItems.some((item) => fieldCodes.includes(item.field_code))
}

function showAudit(fieldCodes: string[]): void {
  const items = props.auditItems.filter((item) => fieldCodes.includes(item.field_code))
  if (items.length) emit('show-audit', items)
}

function statusLabel(status: BusinessOverviewStatus): string {
  return {
    READY: '已识别',
    PARTIAL: '部分信息',
    MISSING: '未识别/未明示',
    NEEDS_REVIEW: '待复核',
  }[status]
}

function statusColor(status: BusinessOverviewStatus): string {
  return {
    READY: 'success',
    PARTIAL: 'warning',
    MISSING: 'default',
    NEEDS_REVIEW: 'error',
  }[status]
}
</script>

<style scoped>
.overview-card {
  min-width: 0;
  border: 1px solid var(--color-border);
  border-radius: 14px;
}

.overview-title,
.overview-title > div,
.source-list {
  display: flex;
}

.overview-title {
  min-width: 0;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.overview-title > div {
  min-width: 0;
  flex-direction: column;
}

.overview-title span {
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 400;
}

.overview-scroll {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
  table-layout: fixed;
}

th,
td {
  padding: 11px 13px;
  border: 1px solid #dbe4ee;
  color: var(--color-text-primary);
  font-size: 13px;
  line-height: 1.55;
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}

thead th {
  background: #123b67;
  color: #ffffff;
  font-weight: 600;
}

thead th:nth-child(1) { width: 20%; }
thead th:nth-child(2) { width: 42%; }
thead th:nth-child(3) { width: 25%; }
thead th:nth-child(4) { width: 13%; }

tbody th {
  background: #f6f9fc;
  font-weight: 600;
}

.row-clickable {
  cursor: pointer;
}

.row-clickable:hover td,
.row-clickable:hover th {
  background: var(--color-primary-bg);
}

.content-cell {
  white-space: pre-wrap;
}

.source-list {
  flex-wrap: wrap;
  gap: 4px;
}

.source-list :deep(.ant-tag) {
  max-width: 100%;
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}

.muted {
  color: var(--color-text-secondary);
}
</style>
