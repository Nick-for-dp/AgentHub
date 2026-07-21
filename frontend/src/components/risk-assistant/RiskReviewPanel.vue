<template>
  <a-card class="review-card" :bordered="false">
    <template #title>
      <div class="review-title">
        <div>
          <strong>当前人工复核</strong>
          <span>每次只处理当前 review item，提交后使用同一任务恢复。</span>
        </div>
        <a-tag color="warning">checkpoint v{{ task.checkpoint_version }}</a-tag>
      </div>
    </template>

    <a-alert v-if="conflictMessage" class="review-alert" type="warning" show-icon :message="conflictMessage" />
    <a-empty v-if="!item" description="没有可提交的当前复核项" />
    <template v-else>
      <a-descriptions class="review-summary" size="small" bordered :column="1">
        <a-descriptions-item label="复核类型">
          {{ item.target_kind === 'DOCUMENT_TYPE' ? '文档类型确认' : '审计字段复核' }}
        </a-descriptions-item>
        <a-descriptions-item label="目标">{{ item.target_code }}</a-descriptions-item>
        <a-descriptions-item v-if="item.original_filename" label="文件">{{ item.original_filename }}</a-descriptions-item>
        <a-descriptions-item v-if="item.warning || item.reason" label="原因">
          {{ item.warning || item.reason }}
        </a-descriptions-item>
      </a-descriptions>

      <a-form class="review-form" layout="vertical" @submit.prevent>
        <template v-if="item.target_kind === 'DOCUMENT_TYPE'">
          <a-alert
            type="info"
            show-icon
            :message="`确认当前声明类型：${documentTypeLabel(item.declared_document_type)}`"
            description="如果声明类型错误，一期请取消任务并使用正确类型重建，不在当前 thread 中切换 extractor。"
          />
        </template>
        <template v-else>
          <a-radio-group v-model:value="action" class="action-group">
            <a-radio v-if="item.alternatives?.length" value="SELECT_VALUE">选择候选值</a-radio>
            <a-radio value="CORRECT_VALUE">人工修正</a-radio>
            <a-radio value="MARK_MISSING">确认缺失/未明示</a-radio>
          </a-radio-group>

          <a-form-item v-if="action === 'SELECT_VALUE'" label="候选值" required>
            <a-select
              v-model:value="selectedAlternativeIndex"
              placeholder="请选择有证据支持的值"
              :options="alternativeOptions"
            />
          </a-form-item>
          <a-form-item v-if="action === 'CORRECT_VALUE'" label="修正值" required>
            <a-textarea
              v-model:value="manualValue"
              :rows="3"
              placeholder="请输入经核对后的最终值"
            />
          </a-form-item>
        </template>

        <a-form-item label="复核理由" required>
          <a-textarea
            v-model:value="reason"
            :rows="3"
            :maxlength="2000"
            show-count
            placeholder="说明判断依据、查看的文件或确认缺失的原因"
          />
        </a-form-item>
        <a-button type="primary" :loading="submitting" :disabled="!canSubmit" @click="submit">
          提交复核并恢复任务
        </a-button>
      </a-form>

      <a-collapse class="audit-context" :bordered="false">
        <a-collapse-panel key="audit" :header="`当前任务全部审计信息（${auditItems.length}）`">
          <div class="audit-table-wrap">
            <table>
              <thead><tr><th>字段</th><th>值</th><th>状态</th><th>是否当前目标</th></tr></thead>
              <tbody>
                <tr v-for="audit in auditItems" :key="audit.field_code">
                  <th>{{ audit.label || audit.field_code }}</th>
                  <td>{{ displayValue(audit.normalized_value ?? audit.value ?? audit.raw_value) }}</td>
                  <td><a-tag>{{ audit.status }}</a-tag></td>
                  <td>{{ audit.field_code === item.target_code ? '是' : '否（只读）' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </a-collapse-panel>
      </a-collapse>
    </template>
  </a-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type {
  RiskAssessmentTask,
  RiskAuditItem,
  RiskDocumentType,
  RiskReviewItem,
  RiskReviewSubmitPayload,
} from '../../api/internalRiskAssistant'
import type { RiskReviewDecision } from '../../composables/useRiskAssistantWorkbench'

const props = defineProps<{
  task: RiskAssessmentTask
  item?: RiskReviewItem | null
  auditItems: RiskAuditItem[]
  submitting: boolean
  conflictMessage?: string | null
}>()

const emit = defineEmits<{
  submit: [decision: RiskReviewDecision]
}>()

const action = ref<RiskReviewSubmitPayload['action']>('CORRECT_VALUE')
const selectedAlternativeIndex = ref<string>()
const manualValue = ref('')
const reason = ref('')

const alternativeOptions = computed(() => (props.item?.alternatives ?? []).map((value, index) => ({
  value: String(index),
  label: displayValue(value),
})))
const canSubmit = computed(() => {
  if (!props.item || props.submitting || !reason.value.trim()) return false
  if (props.item.target_kind === 'DOCUMENT_TYPE') return true
  if (action.value === 'MARK_MISSING') return true
  if (action.value === 'SELECT_VALUE') return selectedAlternativeIndex.value !== undefined
  return manualValue.value.trim().length > 0
})

watch(() => props.item?.id, () => {
  action.value = props.item?.target_kind === 'DOCUMENT_TYPE'
    ? 'CONFIRM_DECLARED_TYPE'
    : (props.item?.alternatives?.length ? 'SELECT_VALUE' : 'CORRECT_VALUE')
  selectedAlternativeIndex.value = undefined
  manualValue.value = ''
  reason.value = ''
}, { immediate: true })

function submit(): void {
  if (!props.item || !canSubmit.value) return
  let value: unknown
  if (props.item.target_kind === 'DOCUMENT_TYPE') {
    value = props.item.declared_document_type
  } else if (action.value === 'SELECT_VALUE') {
    value = props.item.alternatives?.[Number(selectedAlternativeIndex.value)]
  } else if (action.value === 'CORRECT_VALUE') {
    value = manualValue.value.trim()
  }
  emit('submit', { action: action.value, value, reason: reason.value.trim() })
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'string') return value
  try { return JSON.stringify(value) } catch { return String(value) }
}

function documentTypeLabel(value?: RiskDocumentType): string {
  if (!value) return '-'
  return {
    PURCHASE_CONTRACT: '采购合同',
    SALES_CONTRACT: '销售合同',
    APPROVAL_FORM: '供应链业务合同审批表',
    SETTLEMENT_STATEMENT: '结算单',
  }[value]
}
</script>

<style scoped>
.review-card {
  min-width: 0;
  border: 1px solid #ffd591;
  border-radius: 14px;
  background: #fffdf8;
}

.review-title,
.review-title > div,
.action-group {
  display: flex;
}

.review-title {
  min-width: 0;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.review-title > div {
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.review-title span {
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 400;
}

.review-alert,
.review-form,
.audit-context {
  margin-top: 14px;
}

.action-group {
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.audit-table-wrap {
  overflow-x: auto;
}

table {
  width: 100%;
  min-width: 620px;
  border-collapse: collapse;
}

th,
td {
  padding: 8px 10px;
  border: 1px solid var(--color-border);
  font-size: 12px;
  text-align: left;
  overflow-wrap: anywhere;
}

thead th,
tbody th {
  background: #f6f9fc;
}
</style>
