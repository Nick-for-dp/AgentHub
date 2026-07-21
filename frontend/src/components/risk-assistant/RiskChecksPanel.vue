<template>
  <section class="checks-panel">
    <a-alert
      v-if="warnings.length"
      class="warnings"
      type="warning"
      show-icon
      :message="`当前有 ${warnings.length} 条处理提示`"
    >
      <template #description>
        <ul><li v-for="warning in warnings" :key="warning">{{ warning }}</li></ul>
      </template>
    </a-alert>
    <a-empty v-if="checks.length === 0" description="当前没有确定性核对结果" />
    <div v-else class="check-list">
      <article v-for="check in checks" :key="check.rule_code" class="check-card">
        <header>
          <div>
            <strong>{{ check.rule_code }}</strong>
            <a-tag :color="outcomeColor(check.outcome)">{{ check.outcome }}</a-tag>
          </div>
          <span v-if="check.version">{{ check.version }}</span>
        </header>
        <p>{{ check.message }}</p>
        <dl>
          <div>
            <dt>影响字段</dt>
            <dd>
              <a-tag v-for="field in check.affected_fields || []" :key="field">{{ field }}</a-tag>
              <span v-if="!check.affected_fields?.length">-</span>
            </dd>
          </div>
          <div v-if="check.selected_value !== undefined">
            <dt>选定值</dt>
            <dd>{{ displayValue(check.selected_value) }}</dd>
          </div>
        </dl>
        <a-button
          v-if="evidenceSources(check).length"
          type="link"
          size="small"
          @click="$emit('show-evidence', evidenceSources(check))"
        >
          查看输入证据（{{ evidenceSources(check).length }}）
        </a-button>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { RiskCheck, RiskSource } from '../../api/internalRiskAssistant'

defineProps<{
  checks: RiskCheck[]
  warnings: string[]
}>()

defineEmits<{
  'show-evidence': [evidence: RiskSource[]]
}>()

function evidenceSources(check: RiskCheck): RiskSource[] {
  return (check.input_evidence ?? []).flatMap((item) => {
    if (Array.isArray(item.sources)) {
      return item.sources.filter(isRecord) as RiskSource[]
    }
    if (isSource(item)) return [item]
    return []
  })
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isSource(value: Record<string, unknown>): value is RiskSource {
  return [
    'document_id',
    'original_filename',
    'source',
    'page_number',
    'block_id',
    'quote',
    'bbox',
  ].some((key) => key in value)
}

function outcomeColor(value: string): string {
  const normalized = value.toUpperCase()
  if (['PASS', 'PASSED', 'OK'].includes(normalized)) return 'success'
  if (['FAIL', 'FAILED', 'RISK'].includes(normalized)) return 'error'
  if (['WARNING', 'REVIEW'].includes(normalized)) return 'warning'
  return 'default'
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'string') return value
  try { return JSON.stringify(value) } catch { return String(value) }
}
</script>

<style scoped>
.checks-panel,
.check-list {
  min-width: 0;
  display: grid;
  gap: 12px;
}

.warnings ul {
  margin: 0;
  padding-left: 18px;
}

.warnings {
  min-width: 0;
}

.warnings :deep(.ant-alert-content) {
  min-width: 0;
}

.warnings li {
  overflow-wrap: anywhere;
}

.check-card {
  min-width: 0;
  padding: 14px 16px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #ffffff;
}

.check-card header,
.check-card header > div,
.check-card dl > div {
  display: flex;
}

.check-card header {
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.check-card header > div {
  min-width: 0;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.check-card header > span,
.check-card dt {
  color: var(--color-text-secondary);
  font-size: 12px;
}

.check-card p {
  margin: 10px 0;
  color: var(--color-text-primary);
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.check-card strong {
  overflow-wrap: anywhere;
}

.check-card dl {
  margin: 0;
  display: grid;
  gap: 7px;
}

.check-card dl > div {
  gap: 10px;
}

.check-card dt {
  width: 72px;
  flex: none;
}

.check-card dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
