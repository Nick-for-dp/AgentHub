<template>
  <a-card class="task-header" :bordered="false">
    <div class="task-heading">
      <div>
        <span class="eyebrow">风控任务</span>
        <h1>{{ task.business_code }}</h1>
        <div class="task-meta">
          <a-tag :color="statusMeta.color">{{ statusMeta.label }}</a-tag>
          <span>{{ nodeLabel }}</span>
          <span>{{ task.documents.length }} 份文件</span>
          <span>耗时 {{ durationLabel }}</span>
        </div>
      </div>
      <div class="task-actions">
        <a-button :loading="operation === 'LOADING_TASK' || operation === 'POLLING'" @click="$emit('refresh')">
          <ReloadOutlined />
          刷新
        </a-button>
        <a-button v-if="canRetry" type="dashed" @click="$emit('retry')">安全重试执行</a-button>
        <a-popconfirm
          v-if="canCancel"
          title="确认取消当前风控任务？"
          ok-text="取消任务"
          cancel-text="返回"
          @confirm="$emit('cancel')"
        >
          <a-button danger :loading="operation === 'CANCELLING'">取消任务</a-button>
        </a-popconfirm>
        <a-tooltip :title="exportReason">
          <span>
            <a-button
              type="primary"
              :disabled="task.status !== 'SUCCEEDED'"
              :loading="operation === 'EXPORTING'"
              @click="$emit('export')"
            >
              <DownloadOutlined />
              导出审计底稿
            </a-button>
          </span>
        </a-tooltip>
      </div>
    </div>
    <a-alert
      v-if="task.error_message || errorMessage"
      class="task-error"
      type="error"
      show-icon
      :message="errorMessage || task.error_message"
    />
  </a-card>
</template>

<script setup lang="ts">
import { DownloadOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { computed } from 'vue'

import type { RiskAssessmentTask } from '../../api/internalRiskAssistant'
import type { RiskWorkbenchOperation } from '../../composables/useRiskAssistantWorkbench'

const props = defineProps<{
  task: RiskAssessmentTask
  operation: RiskWorkbenchOperation
  errorMessage?: string | null
  canRetry?: boolean
}>()

defineEmits<{
  refresh: []
  retry: []
  cancel: []
  export: []
}>()

const STATUS_META = {
  PENDING: { label: '待执行', color: 'default' },
  RUNNING: { label: '处理中', color: 'processing' },
  WAITING_REVIEW: { label: '待人工复核', color: 'warning' },
  SUCCEEDED: { label: '已完成', color: 'success' },
  FAILED: { label: '执行失败', color: 'error' },
  CANCELLED: { label: '已取消', color: 'default' },
} as const

const KNOWN_NODE_LABELS: Record<string, string> = {
  validate_declared_document_types: '正在校验文档类型',
  extract_documents: '正在理解业务文档',
  normalize_document_facts: '正在归一化审计信息',
  run_document_checks: '正在执行确定性核对',
  apply_human_review: '正在应用人工复核',
  rerun_affected_checks: '正在重算受影响核对',
}

const statusMeta = computed(() => STATUS_META[props.task.status])
const canCancel = computed(() => !['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(props.task.status))
const nodeLabel = computed(() => {
  if (props.task.status !== 'RUNNING') return '状态已持久化'
  if (!props.task.current_node) return '处理中'
  return KNOWN_NODE_LABELS[props.task.current_node] ?? '处理中'
})
const durationLabel = computed(() => {
  const start = Date.parse(props.task.created_at)
  const end = props.task.finished_at ? Date.parse(props.task.finished_at) : Date.now()
  if (!Number.isFinite(start) || !Number.isFinite(end)) return '-'
  const seconds = Math.max(0, Math.round((end - start) / 1000))
  if (seconds < 60) return `${seconds} 秒`
  return `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
})
const exportReason = computed(() => (
  props.task.status === 'SUCCEEDED'
    ? '导出仅包含“业务总览”的 Excel 审计底稿'
    : '只有已完成的任务可导出审计底稿'
))
</script>

<style scoped>
.task-header {
  border: 1px solid rgba(187, 223, 255, 0.8);
  border-radius: 14px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
}

.task-heading,
.task-meta,
.task-actions {
  display: flex;
}

.task-heading {
  align-items: flex-start;
  justify-content: space-between;
  gap: 22px;
}

.eyebrow {
  color: var(--color-primary);
  font-size: 12px;
  font-weight: 600;
}

h1 {
  margin: 4px 0 8px;
  color: var(--color-text-primary);
  font-size: 24px;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.task-meta,
.task-actions {
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.task-meta span:not(.ant-tag) {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.task-actions {
  justify-content: flex-end;
}

.task-error {
  margin-top: 16px;
}

@media (max-width: 760px) {
  .task-heading {
    flex-direction: column;
  }

  .task-actions {
    width: 100%;
    justify-content: flex-start;
  }
}

@media (max-width: 480px) {
  .task-actions > *,
  .task-actions :deep(.ant-btn) {
    width: 100%;
  }
}
</style>
