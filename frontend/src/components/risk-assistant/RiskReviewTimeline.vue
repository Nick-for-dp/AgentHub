<template>
  <a-card class="timeline-card" :bordered="false">
    <template #title>人工复核轨迹</template>
    <a-empty v-if="events.length === 0" description="当前任务尚无人工复核记录" />
    <a-timeline v-else>
      <a-timeline-item v-for="event in events" :key="event.id" color="blue">
        <article class="event-card">
          <header>
            <strong>{{ event.target_code }}</strong>
            <a-tag>{{ actionLabel(event.action) }}</a-tag>
            <time>{{ formatTime(event.created_at) }}</time>
          </header>
          <dl>
            <div><dt>修改前</dt><dd>{{ displayValue(event.before_value) }}</dd></div>
            <div><dt>修改后</dt><dd>{{ displayValue(event.after_value) }}</dd></div>
            <div><dt>理由</dt><dd>{{ event.reason }}</dd></div>
            <div><dt>操作人</dt><dd>{{ event.actor_user_id || '-' }}</dd></div>
            <div><dt>版本</dt><dd>checkpoint v{{ event.checkpoint_version }}</dd></div>
          </dl>
        </article>
      </a-timeline-item>
    </a-timeline>
  </a-card>
</template>

<script setup lang="ts">
import type { RiskReviewEvent } from '../../api/internalRiskAssistant'

defineProps<{ events: RiskReviewEvent[] }>()

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') return value
  try { return JSON.stringify(value) } catch { return String(value) }
}

function actionLabel(action: string): string {
  return {
    SELECT_VALUE: '选择候选值',
    CORRECT_VALUE: '人工修正',
    MARK_MISSING: '确认缺失',
    CONFIRM_DECLARED_TYPE: '确认声明类型',
  }[action] ?? action
}

function formatTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.timeline-card {
  border: 1px solid var(--color-border);
  border-radius: 14px;
}

.event-card header,
.event-card dl > div {
  display: flex;
}

.event-card header {
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.event-card time {
  margin-left: auto;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.event-card dl {
  margin: 10px 0 0;
  display: grid;
  gap: 5px;
}

.event-card dl > div {
  gap: 10px;
}

.event-card dt {
  width: 60px;
  flex: none;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.event-card dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}
</style>
