<template>
  <main class="risk-assistant-page">
    <section class="page-intro">
      <div>
        <a-typography-title :level="2">风控助手工作台</a-typography-title>
        <p>提交供应链业务文件，查看 17 项业务总览、确定性核对、来源证据和人工复核记录。</p>
      </div>
      <a-button type="primary" ghost @click="startNewTask">
        <PlusOutlined />
        新建任务
      </a-button>
    </section>

    <div class="workbench-layout">
      <aside class="recent-tasks" aria-label="最近风控任务">
        <div class="recent-header">
          <div>
            <strong>最近任务</strong>
            <span>{{ taskList.total }} 条</span>
          </div>
          <a-button type="text" size="small" :loading="taskList.loading" @click="loadTaskList()">
            <ReloadOutlined />
          </a-button>
        </div>
        <a-select
          class="status-filter"
          :value="taskList.status"
          allow-clear
          placeholder="全部状态"
          :options="statusOptions"
          @change="changeStatusFilter"
        />
        <a-alert v-if="taskList.errorMessage" type="error" show-icon :message="taskList.errorMessage" />
        <a-spin :spinning="taskList.loading">
          <a-empty v-if="!taskList.loading && taskList.items.length === 0" description="暂无风控任务" />
          <div v-else class="task-list">
            <div
              v-for="task in taskList.items"
              :key="task.id"
              class="task-list-item"
              :class="{ active: selectedTask?.id === task.id }"
            >
              <button type="button" class="task-list-open" @click="openTask(task.id)">
                <span class="task-list-topline">
                  <strong>{{ task.business_code }}</strong>
                  <a-tag :color="taskStatusColor(task.status)">{{ taskStatusLabel(task.status) }}</a-tag>
                </span>
                <span>{{ task.document_count }} 份文件 · {{ formatTime(task.updated_at) }}</span>
                <small v-if="task.error_message">{{ task.error_message }}</small>
              </button>
              <a-popconfirm
                :disabled="!isTaskDeletable(task.status)"
                title="确认删除该风控任务？"
                description="删除后将不再显示，但审计数据仍会保留。"
                ok-text="删除"
                cancel-text="取消"
                @confirm="handleDeleteTask(task.id)"
              >
                <a-button
                  class="task-delete"
                  type="text"
                  danger
                  size="small"
                  :aria-label="`删除任务 ${task.business_code}`"
                  :loading="deletingTaskId === task.id"
                  :title="isTaskDeletable(task.status) ? '删除任务' : '任务结束后才可删除'"
                  :disabled="!isTaskDeletable(task.status)
                    || (deletingTaskId !== null && deletingTaskId !== task.id)"
                >
                  <DeleteOutlined />
                </a-button>
              </a-popconfirm>
            </div>
          </div>
        </a-spin>
        <a-pagination
          v-if="taskList.total > taskList.pageSize"
          class="task-pagination"
          size="small"
          :current="taskList.page"
          :page-size="taskList.pageSize"
          :total="taskList.total"
          :show-size-changer="false"
          @change="changePage"
        />
      </aside>

      <section class="main-workspace">
        <a-spin v-if="operation === 'LOADING_TASK' && !selectedTask" class="detail-loading" />
        <RiskFilePackagePanel
          v-else-if="!selectedTask"
          :files="files"
          :business-code="businessCode"
          :disabled="isTaskBusy"
          :can-submit="canCreateTask"
          :error-message="packageErrorMessage"
          @add-files="addFiles"
          @set-type="setDeclaredDocumentType"
          @remove="removeFile"
          @retry="retryFile"
          @submit="handleCreateTask"
          @reset="resetPackage"
          @update:business-code="businessCode = $event"
        />
        <template v-else>
          <RiskTaskHeader
            :task="selectedTask"
            :operation="operation"
            :error-message="detailErrorMessage"
            :can-retry="canRetryExecute"
            @refresh="refreshSelectedTask"
            @retry="retryExecute"
            @cancel="handleCancel"
            @export="exportSelectedTask"
          />

          <a-alert
            v-if="selectedTask.status === 'RUNNING'"
            class="state-alert"
            type="info"
            show-icon
            message="任务正在处理中"
            description="工作台按稳定任务状态轮询；即使 LangGraph 新增未知节点，也会继续显示“处理中”。"
          />
          <a-alert
            v-else-if="selectedTask.status === 'PENDING'"
            class="state-alert"
            type="info"
            show-icon
            message="任务已创建，尚未开始执行"
          />
          <a-alert
            v-else-if="selectedTask.status === 'FAILED'"
            class="state-alert"
            type="error"
            show-icon
            message="任务执行失败"
            :description="selectedTask.error_message || '请查看任务错误并重新创建。'"
          />

          <div class="primary-grid" :class="{ 'has-review': selectedTask.status === 'WAITING_REVIEW' }">
            <RiskOverviewTable
              :projection="selectedTask.business_overview"
              :audit-items="auditItems"
              @show-audit="showAuditEvidence"
            />
            <RiskReviewPanel
              v-if="selectedTask.status === 'WAITING_REVIEW'"
              :task="selectedTask"
              :item="activeReviewItem"
              :audit-items="auditItems"
              :submitting="operation === 'REVIEWING' || operation === 'POLLING'"
              :conflict-message="checkpointConflictMessage"
              @submit="submitReview"
            />
          </div>

          <a-tabs class="detail-tabs" default-active-key="checks">
            <a-tab-pane key="checks" :tab="`核对与提示（${checks.length}）`">
              <RiskChecksPanel
                :checks="checks"
                :warnings="warnings"
                @show-evidence="showRawEvidence"
              />
            </a-tab-pane>
            <a-tab-pane key="audit" :tab="`原子审计信息（${auditItems.length}）`">
              <div class="audit-table-scroll">
                <table class="audit-table">
                  <thead><tr><th>字段</th><th>值</th><th>状态</th><th>来源</th></tr></thead>
                  <tbody>
                    <tr v-for="audit in auditItems" :key="audit.field_code">
                      <th>{{ audit.label || audit.field_code }}</th>
                      <td>{{ displayValue(audit.normalized_value ?? audit.value ?? audit.raw_value) }}</td>
                      <td><a-tag :color="auditStatusColor(audit.status)">{{ audit.status }}</a-tag></td>
                      <td>
                        <a-button
                          v-if="audit.sources?.length"
                          type="link"
                          size="small"
                          @click="showSources(audit.sources)"
                        >
                          查看证据（{{ audit.sources.length }}）
                        </a-button>
                        <span v-else>-</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </a-tab-pane>
            <a-tab-pane key="timeline" :tab="`复核轨迹（${selectedTask.review_events.length}）`">
              <RiskReviewTimeline :events="selectedTask.review_events" />
            </a-tab-pane>
          </a-tabs>
        </template>
      </section>
    </div>

    <RiskEvidenceDrawer
      :open="evidenceDrawerOpen"
      :sources="evidenceSources"
      :busy="operation === 'OPENING_SOURCE'"
      @close="evidenceDrawerOpen = false"
      @open-document="openSourceDocument"
    />
  </main>
</template>

<script setup lang="ts">
import { DeleteOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type {
  InternalTaskStatus,
} from '../../api/internalFiles'
import type {
  RiskAuditItem,
  RiskSource,
} from '../../api/internalRiskAssistant'
import RiskChecksPanel from '../../components/risk-assistant/RiskChecksPanel.vue'
import RiskEvidenceDrawer from '../../components/risk-assistant/RiskEvidenceDrawer.vue'
import RiskFilePackagePanel from '../../components/risk-assistant/RiskFilePackagePanel.vue'
import RiskOverviewTable from '../../components/risk-assistant/RiskOverviewTable.vue'
import RiskReviewPanel from '../../components/risk-assistant/RiskReviewPanel.vue'
import RiskReviewTimeline from '../../components/risk-assistant/RiskReviewTimeline.vue'
import RiskTaskHeader from '../../components/risk-assistant/RiskTaskHeader.vue'
import { useRiskAssistantWorkbench } from '../../composables/useRiskAssistantWorkbench'

const route = useRoute()
const router = useRouter()
const evidenceDrawerOpen = ref(false)
const evidenceSources = ref<RiskSource[]>([])

const {
  businessCode,
  files,
  packageErrorMessage,
  selectedTask,
  detailErrorMessage,
  checkpointConflictMessage,
  deletingTaskId,
  operation,
  taskList,
  isTaskBusy,
  canCreateTask,
  canRetryExecute,
  activeReviewItem,
  auditItems,
  checks,
  warnings,
  addFiles,
  setDeclaredDocumentType,
  removeFile,
  retryFile,
  createAndExecuteTask,
  retryExecute,
  loadTaskList,
  loadTask,
  deleteTask,
  refreshSelectedTask,
  submitReview,
  cancelSelectedTask,
  openSourceDocument,
  exportSelectedTask,
  resetPackage,
  clearSelectedTask,
} = useRiskAssistantWorkbench()

const statusOptions = [
  { value: 'PENDING', label: '待执行' },
  { value: 'RUNNING', label: '处理中' },
  { value: 'WAITING_REVIEW', label: '待人工复核' },
  { value: 'SUCCEEDED', label: '已完成' },
  { value: 'FAILED', label: '执行失败' },
  { value: 'CANCELLED', label: '已取消' },
]

onMounted(() => {
  void loadTaskList()
})

watch(
  () => route.params.taskId,
  (rawTaskId) => {
    const taskId = Array.isArray(rawTaskId) ? rawTaskId[0] : rawTaskId
    if (typeof taskId === 'string' && taskId) void loadTask(taskId)
    else if (selectedTask.value) clearSelectedTask()
  },
  { immediate: true },
)

watch(
  () => selectedTask.value?.id,
  (taskId) => {
    if (!taskId || route.params.taskId === taskId) return
    void router.replace(`/internal/risk-assistant/tasks/${encodeURIComponent(taskId)}`)
  },
)

async function handleCreateTask(): Promise<void> {
  await createAndExecuteTask()
  await loadTaskList({ page: 1 })
}

async function handleCancel(): Promise<void> {
  await cancelSelectedTask()
  await loadTaskList()
}

async function handleDeleteTask(taskId: string): Promise<void> {
  const rawRouteTaskId = route.params.taskId
  const routeTaskId = Array.isArray(rawRouteTaskId) ? rawRouteTaskId[0] : rawRouteTaskId
  const wasSelected = selectedTask.value?.id === taskId || routeTaskId === taskId
  if (!await deleteTask(taskId)) return
  if (wasSelected) await router.push('/internal/risk-assistant')
  const lastPage = Math.max(1, Math.ceil(taskList.value.total / taskList.value.pageSize))
  await loadTaskList({ page: Math.min(taskList.value.page, lastPage) })
}

function startNewTask(): void {
  clearSelectedTask()
  void router.push('/internal/risk-assistant')
}

function openTask(taskId: string): void {
  void router.push(`/internal/risk-assistant/tasks/${encodeURIComponent(taskId)}`)
}

function changePage(page: number): void {
  void loadTaskList({ page })
}

function changeStatusFilter(value: InternalTaskStatus | undefined): void {
  void loadTaskList({ page: 1, status: value ?? null })
}

function showAuditEvidence(items: RiskAuditItem[]): void {
  showSources(items.flatMap((item) => item.sources ?? []))
}

function showRawEvidence(items: Array<Record<string, unknown>>): void {
  showSources(items as RiskSource[])
}

function showSources(sources: RiskSource[]): void {
  evidenceSources.value = enrichSources(sources)
  evidenceDrawerOpen.value = true
}

function enrichSources(sources: RiskSource[]): RiskSource[] {
  return sources.map((source) => {
    const document = selectedTask.value?.documents.find((item) => (
      item.id === source.document_id
      || (!!source.original_filename && item.original_filename === source.original_filename)
    ))
    if (!document) return source
    return {
      ...source,
      document_id: source.document_id ?? document.id,
      original_filename: source.original_filename ?? document.original_filename,
      declared_document_type: source.declared_document_type ?? document.declared_document_type,
      type_validation_status: source.type_validation_status ?? document.type_validation_status,
      type_validation_warnings: source.type_validation_warnings ?? document.type_validation_warnings,
    }
  })
}

function taskStatusLabel(status: InternalTaskStatus): string {
  return {
    PENDING: '待执行',
    RUNNING: '处理中',
    WAITING_REVIEW: '待复核',
    SUCCEEDED: '已完成',
    FAILED: '失败',
    CANCELLED: '已取消',
  }[status]
}

function taskStatusColor(status: InternalTaskStatus): string {
  return {
    PENDING: 'default',
    RUNNING: 'processing',
    WAITING_REVIEW: 'warning',
    SUCCEEDED: 'success',
    FAILED: 'error',
    CANCELLED: 'default',
  }[status]
}

function isTaskDeletable(status: InternalTaskStatus): boolean {
  return ['SUCCEEDED', 'FAILED', 'CANCELLED'].includes(status)
}

function auditStatusColor(status: string): string {
  if (['FOUND', 'ACCEPTED'].includes(status)) return 'success'
  if (['UNRESOLVED', 'UNCERTAIN'].includes(status)) return 'warning'
  if (['MISSING', 'ACCEPTED_MISSING'].includes(status)) return 'default'
  return 'blue'
}

function formatTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'string') return value
  try { return JSON.stringify(value) } catch { return String(value) }
}
</script>

<style scoped>
.risk-assistant-page {
  max-width: 1720px;
  margin: 0 auto;
}

.page-intro,
.recent-header,
.recent-header > div,
.task-list-topline {
  display: flex;
}

.page-intro {
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
  margin: 2px 0 18px;
}

.page-intro :deep(.ant-typography) {
  margin: 0;
  color: #0f172a;
}

.page-intro p {
  margin: 7px 0 0;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.workbench-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  align-items: start;
  gap: 18px;
}

.recent-tasks {
  position: sticky;
  top: 78px;
  min-width: 0;
  max-height: calc(100vh - 102px);
  padding: 14px;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.recent-header {
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.recent-header > div {
  flex-direction: column;
  gap: 2px;
}

.recent-header span {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.status-filter {
  width: 100%;
  margin: 12px 0;
}

.task-list {
  display: grid;
  gap: 8px;
}

.task-list-item {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  width: 100%;
  padding: 11px;
  border: 1px solid var(--color-border);
  border-radius: 9px;
  background: #ffffff;
  color: inherit;
}

.task-list-item:hover,
.task-list-item.active {
  border-color: var(--color-primary-border);
  background: var(--color-primary-bg);
}

.task-list-item.active {
  box-shadow: inset 3px 0 0 var(--color-primary);
}

.task-list-open {
  min-width: 0;
  flex: 1;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.task-delete {
  flex: none;
  margin: -5px -6px 0 0;
}

.task-list-topline {
  align-items: flex-start;
  justify-content: space-between;
  gap: 6px;
}

.task-list-topline strong {
  min-width: 0;
  color: var(--color-text-primary);
  font-size: 13px;
  overflow-wrap: anywhere;
}

.task-list-open > span:not(.task-list-topline),
.task-list-open small {
  display: block;
  margin-top: 6px;
  color: var(--color-text-secondary);
  font-size: 11px;
}

.task-list-open small {
  color: #cf1322;
}

.task-pagination {
  margin-top: 12px;
  text-align: center;
}

.main-workspace {
  min-width: 0;
}

.detail-loading {
  width: 100%;
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.state-alert,
.primary-grid,
.detail-tabs {
  margin-top: 14px;
}

.primary-grid {
  min-width: 0;
  display: grid;
  gap: 14px;
}

.primary-grid > * {
  min-width: 0;
}

.primary-grid.has-review {
  grid-template-columns: minmax(0, 1.4fr) minmax(360px, 0.8fr);
  align-items: start;
}

.detail-tabs {
  padding: 0 16px 16px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  background: #ffffff;
}

.audit-table-scroll {
  overflow-x: auto;
}

.audit-table {
  width: 100%;
  min-width: 700px;
  border-collapse: collapse;
}

.audit-table th,
.audit-table td {
  padding: 9px 11px;
  border: 1px solid var(--color-border);
  font-size: 12px;
  line-height: 1.55;
  text-align: left;
  overflow-wrap: anywhere;
}

.audit-table thead th,
.audit-table tbody th {
  background: #f6f9fc;
}

@media (max-width: 1180px) {
  .primary-grid.has-review {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 920px) {
  .workbench-layout {
    grid-template-columns: 1fr;
  }

  .recent-tasks {
    position: static;
    max-height: none;
  }

  .task-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 600px) {
  .page-intro {
    align-items: stretch;
    flex-direction: column;
  }

  .page-intro > .ant-btn {
    align-self: flex-start;
  }

  .task-list {
    grid-template-columns: 1fr;
  }

  .detail-tabs {
    padding: 0 10px 10px;
  }
}
</style>
