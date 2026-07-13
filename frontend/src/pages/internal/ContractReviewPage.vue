<template>
  <main class="contract-review-page">
    <section class="page-intro">
      <div>
        <a-typography-title :level="2">合同审查工作台</a-typography-title>
        <p>上传 PDF 或 DOCX 合同，按对手方资信等级审查敏感条款，并在解析文本中定位原文。</p>
      </div>
      <a-button v-if="hasResult || phase === 'failed'" @click="handleReset">
        新建审查
      </a-button>
    </section>

    <a-card class="submission-card" :bordered="false">
      <a-form layout="vertical">
        <div class="submission-grid">
          <a-form-item
            class="file-field"
            label="合同文件"
            :validate-status="fieldErrors.file ? 'error' : undefined"
            :help="fieldErrors.file || (selectedFile ? '支持 PDF、DOCX；仅在当前页面内存中使用。' : '必填：请选择 PDF 或 DOCX 合同文件。')"
          >
            <a-upload-dragger
              :file-list="fileList"
              :before-upload="beforeUpload"
              :disabled="isBusy"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              :max-count="1"
              @remove="handleRemoveFile"
            >
              <p class="ant-upload-drag-icon"><InboxOutlined /></p>
              <p class="ant-upload-text">选择或拖入合同文件</p>
              <p class="ant-upload-hint">文件会先上传至内部对象存储，再解析和审查。</p>
            </a-upload-dragger>
          </a-form-item>

          <div class="parameter-fields">
            <a-form-item
              label="合同类型"
              :validate-status="fieldErrors.contractType ? 'error' : undefined"
              :help="fieldErrors.contractType || (!contractType ? '必填：请选择合同类型。' : undefined)"
            >
              <a-select
                v-model:value="contractType"
                :disabled="isBusy"
                placeholder="请选择合同类型"
                :options="contractTypeOptions"
                @change="clearFieldError('contractType')"
              />
            </a-form-item>
            <a-form-item
              label="对手方资信等级"
              :validate-status="fieldErrors.counterpartyLevel ? 'error' : undefined"
              :help="fieldErrors.counterpartyLevel || (!counterpartyLevel ? '必填：请选择 A1-A7。' : undefined)"
            >
              <a-select
                v-model:value="counterpartyLevel"
                :disabled="isBusy"
                placeholder="请选择 A1-A7"
                :options="counterpartyLevelOptions"
                @change="clearFieldError('counterpartyLevel')"
              />
            </a-form-item>
            <a-alert
              class="credit-level-note"
              type="info"
              show-icon
              message="资信等级是合同对手方等级，不是当前内部用户等级。"
            />
            <div class="submit-actions">
              <a-button
                type="primary"
                :loading="isBusy"
                :disabled="isBusy || !canStart"
                @click="handleStart"
              >
                开始审查
              </a-button>
              <a-button v-if="isBusy" @click="handleStopWaiting">
                停止等待
              </a-button>
              <a-button v-else-if="canRetryExecute" type="dashed" @click="handleRetryExecute">
                安全重试审查
              </a-button>
            </div>
          </div>
        </div>
      </a-form>
    </a-card>

    <a-card v-if="phase !== 'idle'" class="progress-card" :bordered="false">
      <div class="progress-heading">
        <div>
          <span class="eyebrow">当前状态</span>
          <strong>{{ phaseLabel(phase) }}</strong>
        </div>
        <span v-if="startedAt" class="elapsed">已耗时 {{ formatElapsed(elapsedSeconds) }}</span>
      </div>
      <a-steps :current="currentStep" size="small" :status="phase === 'failed' ? 'error' : undefined">
        <a-step title="上传" />
        <a-step title="解析" />
        <a-step title="创建任务" />
        <a-step title="审查" />
      </a-steps>
      <a-progress
        v-if="phase === 'uploading'"
        class="upload-progress"
        :percent="uploadProgress"
        size="small"
        status="active"
      />
      <a-alert
        v-if="phase === 'failed' && errorMessage"
        class="workflow-error"
        type="error"
        show-icon
        :message="errorMessage"
        :description="failureDescription"
      />
      <a-alert
        v-else-if="isBusy"
        class="workflow-hint"
        type="info"
        show-icon
        message="请保持当前页面打开。若已停止等待，后台任务仍可能继续完成。"
      />
    </a-card>

    <template v-if="hasResult">
      <section class="summary-grid" aria-label="审查摘要">
        <a-card :bordered="false" class="summary-card">
          <a-statistic title="抽取条款" :value="reviewSummary.total_clause_count" />
        </a-card>
        <a-card :bordered="false" class="summary-card summary-card--sensitive">
          <a-statistic title="敏感条款" :value="reviewSummary.sensitive_clause_count" />
        </a-card>
        <a-card :bordered="false" class="summary-card">
          <a-statistic title="最高风险" :value="reviewSummary.highest_risk_level || '-'" />
        </a-card>
        <a-card :bordered="false" class="summary-card">
          <a-statistic title="审查提示" :value="totalWarningCount" />
        </a-card>
      </section>

      <a-alert
        v-if="topLevelWarnings.length > 0"
        class="result-warning"
        type="warning"
        show-icon
        :message="`本次审查包含 ${topLevelWarnings.length} 条提示`"
      >
        <template #description>
          <ul class="warning-list">
            <li v-for="(warning, index) in topLevelWarnings" :key="`result-warning-${index}`">
              {{ warningText(warning) }}
            </li>
          </ul>
        </template>
      </a-alert>

      <a-alert
        v-if="documentBlocks.length === 0"
        class="result-warning"
        type="warning"
        show-icon
        message="审查任务已完成，但缺少可展示的解析文本。条款结果仍可查看。"
      />

      <section class="result-workspace">
        <ReviewDocumentPane
          ref="documentPane"
          :blocks="documentBlocks"
          :sections="documentSections"
          :parse-warnings="parseWarnings"
          :highlight-index="highlightIndex"
        />

        <aside class="clause-pane" aria-label="合同审查条款结果">
          <header class="clause-header">
            <div>
              <h2>审查条款</h2>
              <p>默认突出敏感条款；点击条款定位到左侧原文。</p>
            </div>
            <a-radio-group v-model:value="clauseFilter" size="small" button-style="solid">
              <a-radio-button value="sensitive">敏感</a-radio-button>
              <a-radio-button value="all">全部</a-radio-button>
            </a-radio-group>
          </header>

          <a-empty
            v-if="visibleClauses.length === 0 && clauseFilter === 'sensitive'"
            description="未发现敏感条款"
          >
            <template #description>
              <span>审查已成功完成，可切换到“全部”查看已抽取条款与提示。</span>
            </template>
          </a-empty>
          <a-empty v-else-if="visibleClauses.length === 0" description="未抽取到可展示的条款" />
          <div v-else class="clause-list">
            <article
              v-for="item in visibleClauses"
              :key="item.index"
              class="clause-card"
              :class="{ 'clause-card--sensitive': item.clause.is_sensitive }"
            >
              <button
                type="button"
                class="clause-location-button"
                :disabled="highlightIndex.targetsByClause[item.index]?.disabled"
                :aria-label="`定位条款 ${item.index + 1} 的原文`"
                @click="focusClause(item.index)"
              >
                <span class="clause-card-topline">
                  <strong>条款 #{{ item.index + 1 }}</strong>
                  <span class="tag-row">
                    <a-tag :color="item.clause.is_sensitive ? 'orange' : 'blue'">
                      {{ item.clause.is_sensitive ? '敏感' : '一般' }}
                    </a-tag>
                    <a-tag :color="riskTagColor(item.clause.risk_level)">{{ item.clause.risk_level || '-' }}</a-tag>
                    <a-tag>{{ item.clause.category || '-' }}</a-tag>
                  </span>
                </span>
                <p class="clause-text">{{ item.clause.text }}</p>
                <span class="clause-source">{{ sourceLabel(item.index) }}</span>
              </button>

              <dl class="clause-details">
                <div>
                  <dt>判定原因</dt>
                  <dd>{{ item.clause.reason || '-' }}</dd>
                </div>
                <div>
                  <dt>命中规则</dt>
                  <dd>
                    <a-tag v-for="rule in item.clause.matched_rules" :key="rule" class="rule-tag">{{ rule }}</a-tag>
                    <span v-if="item.clause.matched_rules.length === 0">-</span>
                  </dd>
                </div>
                <div>
                  <dt>置信度</dt>
                  <dd>{{ formatConfidence(item.clause.confidence) }}</dd>
                </div>
              </dl>

              <a-alert
                v-for="(warning, warningIndex) in clauseWarnings(item.index, item.clause.warnings)"
                :key="`${item.index}-warning-${warningIndex}`"
                class="clause-warning"
                type="warning"
                show-icon
                :message="warning.message"
              />
            </article>
          </div>
        </aside>
      </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { InboxOutlined } from '@ant-design/icons-vue'
import type { FileType, UploadFile } from 'ant-design-vue/es/upload/interface'
import { computed, ref } from 'vue'

import type {
  ContractClauseReviewResult,
  ContractType,
  CounterpartyLevel,
  ParsedDocumentBlock,
  ParsedDocumentSection,
  ReviewWarning,
} from '../../api/internalContractReview'
import ReviewDocumentPane from '../../components/contract-review/ReviewDocumentPane.vue'
import {
  phaseLabel,
  useContractReviewWorkbench,
  validateContractReviewSubmission,
  type SubmissionValidation,
} from '../../composables/useContractReviewWorkbench'
import { buildHighlightIndex, type ClauseTarget, type HighlightWarning } from '../../utils/contractHighlight'

type ClauseFilter = 'sensitive' | 'all'
type DocumentPaneInstance = { focusClause: (target: ClauseTarget | undefined) => void }

const contractType = ref<ContractType | null>(null)
const counterpartyLevel = ref<CounterpartyLevel | null>(null)
const selectedFile = ref<File | null>(null)
const fileList = ref<UploadFile[]>([])
const fieldErrors = ref<SubmissionValidation>({})
const clauseFilter = ref<ClauseFilter>('sensitive')
const documentPane = ref<DocumentPaneInstance | null>(null)

const {
  phase,
  errorMessage,
  uploadProgress,
  startedAt,
  elapsedSeconds,
  fileParseTask,
  reviewTask,
  isBusy,
  canRetryExecute,
  startReview,
  retryExecute,
  cancelWaiting,
  reset,
} = useContractReviewWorkbench()

const contractTypeOptions = [
  { value: 'warehouse', label: '仓储合同' },
  { value: 'transport', label: '运输合同' },
]

const counterpartyLevelOptions = (['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7'] as CounterpartyLevel[])
  .map((value) => ({ value, label: value }))

const reviewResult = computed(() => reviewTask.value?.result ?? null)
const reviewSummary = computed(() => reviewResult.value?.summary ?? {
  total_clause_count: 0,
  sensitive_clause_count: 0,
  highest_risk_level: null,
  warning_count: 0,
})
const documentBlocks = computed<ParsedDocumentBlock[]>(() => (
  fileParseTask.value?.result_snapshot?.blocks ?? []
))
const documentSections = computed<ParsedDocumentSection[]>(() => (
  fileParseTask.value?.result_snapshot?.sections ?? []
))
const parseWarnings = computed<ReviewWarning[]>(() => (
  fileParseTask.value?.result_snapshot?.warnings ?? []
))
const allClauses = computed<ContractClauseReviewResult[]>(() => reviewResult.value?.clauses ?? [])
const highlightIndex = computed(() => buildHighlightIndex(documentBlocks.value, allClauses.value))
const visibleClauses = computed(() => allClauses.value
  .map((clause, index) => ({ clause, index }))
  .filter(({ clause }) => clauseFilter.value === 'all' || clause.is_sensitive))
const topLevelWarnings = computed<ReviewWarning[]>(() => reviewResult.value?.warnings ?? [])
const totalWarningCount = computed(() => (
  reviewSummary.value.warning_count
  + parseWarnings.value.length
  + Object.values(highlightIndex.value.warningsByClause).flat().length
))
const hasResult = computed(() => reviewTask.value?.status === 'SUCCEEDED' && reviewResult.value !== null)
const canStart = computed(() => Object.keys(validateContractReviewSubmission(currentSubmission())).length === 0)
const currentStep = computed(() => {
  if (phase.value === 'preparing_upload' || phase.value === 'uploading') return 0
  if (phase.value === 'parsing') return 1
  if (phase.value === 'creating_review') return 2
  return 3
})
const failureDescription = computed(() => (
  canRetryExecute.value
    ? '已先查询任务状态，确认它仍可执行；可点击“安全重试审查”。'
    : '请检查当前阶段提示；重新选择文件后可以发起新的审查。'
))

function beforeUpload(file: FileType): boolean {
  const nextErrors = validateContractReviewSubmission({
    file,
    contractType: contractType.value,
    counterpartyLevel: counterpartyLevel.value,
  })
  if (nextErrors.file) {
    fieldErrors.value = { ...fieldErrors.value, file: nextErrors.file }
    return false
  }

  reset()
  selectedFile.value = file
  fileList.value = [{
    uid: file.uid,
    name: file.name,
    size: file.size,
    type: file.type,
    status: 'done',
    originFileObj: file,
  }]
  fieldErrors.value = { ...fieldErrors.value, file: undefined }
  return false
}

function handleRemoveFile(): boolean {
  selectedFile.value = null
  fileList.value = []
  fieldErrors.value = { ...fieldErrors.value, file: undefined }
  return true
}

function clearFieldError(field: keyof SubmissionValidation): void {
  fieldErrors.value = { ...fieldErrors.value, [field]: undefined }
}

async function handleStart(): Promise<void> {
  const submission = currentSubmission()
  fieldErrors.value = validateContractReviewSubmission(submission)
  if (Object.keys(fieldErrors.value).length > 0) return
  await startReview(submission)
}

async function handleRetryExecute(): Promise<void> {
  await retryExecute()
}

function handleStopWaiting(): void {
  cancelWaiting()
}

function handleReset(): void {
  reset()
  selectedFile.value = null
  fileList.value = []
  fieldErrors.value = {}
  clauseFilter.value = 'sensitive'
}

function currentSubmission() {
  return {
    file: selectedFile.value,
    contractType: contractType.value,
    counterpartyLevel: counterpartyLevel.value,
  }
}

function focusClause(index: number): void {
  documentPane.value?.focusClause(highlightIndex.value.targetsByClause[index])
}

function clauseWarnings(
  index: number,
  backendWarnings: ReviewWarning[],
): Array<ReviewWarning | HighlightWarning> {
  return [
    ...backendWarnings,
    ...highlightIndex.value.warningsByClause[index] ?? [],
  ]
}

function sourceLabel(index: number): string {
  const target = highlightIndex.value.targetsByClause[index]
  if (!target?.blockId) return '无可用原文来源位置'
  return target.precise ? `${target.blockId} · 已精确高亮` : `${target.blockId} · 已定位原文块`
}

function riskTagColor(riskLevel: string): string {
  const normalized = riskLevel.toUpperCase()
  if (normalized === 'HIGH') return 'red'
  if (normalized === 'MEDIUM') return 'orange'
  if (normalized === 'LOW') return 'blue'
  return 'default'
}

function formatConfidence(value: number): string {
  return Number.isFinite(value) ? `${Math.round(value * 100)}%` : '-'
}

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  const remainder = seconds % 60
  return minutes > 0 ? `${minutes} 分 ${remainder} 秒` : `${remainder} 秒`
}

function warningText(warning: ReviewWarning): string {
  if (typeof warning.message === 'string' && warning.message.trim()) return warning.message
  if (typeof warning.code === 'string' && warning.code.trim()) return warning.code
  return '审查结果包含未分类提示。'
}
</script>

<style scoped>
.contract-review-page {
  max-width: 1640px;
  margin: 0 auto;
}

.page-intro {
  margin: 2px 0 18px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
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

.submission-card,
.progress-card,
.summary-card,
.clause-pane {
  border: 1px solid rgba(187, 223, 255, 0.75);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.submission-card :deep(.ant-card-body) {
  padding: 20px;
}

.submission-grid {
  display: grid;
  grid-template-columns: minmax(300px, 1.55fr) minmax(280px, 1fr);
  gap: 24px;
}

.file-field {
  margin-bottom: 0;
}

.file-field :deep(.ant-upload.ant-upload-drag) {
  min-height: 162px;
  border-color: var(--color-primary-border);
  background: #fbfdff;
}

.file-field :deep(.ant-upload.ant-upload-drag:hover) {
  border-color: var(--color-primary);
}

.ant-upload-drag-icon {
  margin-bottom: 10px;
  color: var(--color-primary);
  font-size: 30px;
}

.ant-upload-text {
  margin-bottom: 4px;
  color: var(--color-text-primary);
  font-weight: 600;
}

.ant-upload-hint {
  margin-bottom: 0;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.parameter-fields {
  display: flex;
  flex-direction: column;
}

.parameter-fields :deep(.ant-form-item) {
  margin-bottom: 15px;
}

.credit-level-note {
  margin: 1px 0 16px;
}

.submit-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: auto;
}

.progress-card {
  margin-top: 16px;
}

.progress-card :deep(.ant-card-body) {
  padding: 18px 20px;
}

.progress-heading {
  margin-bottom: 16px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}

.progress-heading > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.eyebrow,
.elapsed {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.progress-heading strong {
  color: var(--color-text-primary);
  font-size: 16px;
}

.upload-progress,
.workflow-error,
.workflow-hint {
  margin-top: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.summary-card :deep(.ant-card-body) {
  padding: 16px 18px;
}

.summary-card--sensitive {
  border-color: #ffd591;
  background: #fffaf2;
}

.result-warning {
  margin-top: 14px;
}

.warning-list {
  margin: 0;
  padding-left: 18px;
}

.result-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(340px, 0.9fr);
  gap: 18px;
  margin-top: 18px;
  align-items: start;
}

.clause-pane {
  min-width: 0;
  min-height: 580px;
  overflow: hidden;
  background: #ffffff;
}

.clause-header {
  min-height: 76px;
  padding: 18px 20px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
}

.clause-header h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 16px;
}

.clause-header p {
  margin: 5px 0 0;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.clause-pane > :deep(.ant-empty) {
  margin: 70px 20px;
}

.clause-list {
  max-height: calc(100vh - 260px);
  overflow: auto;
  padding: 12px;
}

.clause-card {
  margin-bottom: 10px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius);
  background: #ffffff;
  overflow: hidden;
}

.clause-card--sensitive {
  border-color: #ffd591;
}

.clause-location-button {
  width: 100%;
  padding: 13px 14px 11px;
  display: block;
  border: 0;
  border-bottom: 1px solid transparent;
  background: #ffffff;
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.clause-card--sensitive .clause-location-button {
  background: #fffdf9;
}

.clause-location-button:hover:not(:disabled) {
  background: var(--color-primary-bg);
}

.clause-location-button:focus-visible {
  outline: 3px solid rgba(0, 122, 204, 0.2);
  outline-offset: -3px;
}

.clause-location-button:disabled {
  cursor: not-allowed;
  opacity: 0.68;
}

.clause-card-topline,
.tag-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.clause-card-topline {
  justify-content: space-between;
}

.clause-card-topline strong {
  color: var(--color-text-primary);
  font-size: 13px;
}

.tag-row {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.tag-row :deep(.ant-tag) {
  margin-inline-end: 0;
}

.clause-text {
  margin: 10px 0 6px;
  color: var(--color-text-primary);
  font-size: 13px;
  line-height: 1.65;
  overflow-wrap: anywhere;
}

.clause-source {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
  font-size: 11px;
}

.clause-details {
  margin: 0;
  padding: 10px 14px 12px;
  display: grid;
  gap: 8px;
  background: #fafcff;
}

.clause-details > div {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  gap: 8px;
  font-size: 12px;
  line-height: 1.55;
}

.clause-details dt {
  color: var(--color-text-secondary);
}

.clause-details dd {
  min-width: 0;
  margin: 0;
  color: var(--color-text-primary);
  overflow-wrap: anywhere;
}

.rule-tag {
  margin: 0 4px 4px 0;
}

.clause-warning {
  margin: 0 10px 10px;
}

@media (max-width: 1100px) {
  .result-workspace {
    grid-template-columns: 1fr;
  }

  .clause-list {
    max-height: none;
  }
}

@media (max-width: 820px) {
  .submission-grid,
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .page-intro {
    align-items: stretch;
    flex-direction: column;
  }

  .page-intro > .ant-btn {
    align-self: flex-start;
  }
}

@media (max-width: 480px) {
  .submission-card :deep(.ant-card-body),
  .progress-card :deep(.ant-card-body) {
    padding: 14px;
  }

  .clause-header {
    align-items: stretch;
    flex-direction: column;
  }

  .clause-card-topline {
    align-items: flex-start;
    flex-direction: column;
  }

  .tag-row {
    justify-content: flex-start;
  }
}
</style>
