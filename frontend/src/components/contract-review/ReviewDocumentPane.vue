<template>
  <section class="document-pane" aria-label="合同解析文本">
    <header class="pane-header">
      <div>
        <h2>合同解析文本</h2>
        <p>按解析顺序展示；高亮仅基于后端返回的来源位置。</p>
      </div>
      <a-badge :count="blocks.length" :number-style="{ backgroundColor: '#007ACC' }" />
    </header>

    <a-alert
      v-if="parseWarnings.length > 0"
      class="parse-warning"
      type="warning"
      show-icon
      :message="`解析结果包含 ${parseWarnings.length} 条提示`"
    >
      <template #description>
        <a-collapse ghost size="small">
          <a-collapse-panel key="parse-warnings" header="查看解析提示">
            <ul class="warning-list">
              <li v-for="(warning, index) in parseWarnings" :key="`${warning.code || 'warning'}-${index}`">
                {{ warningText(warning) }}
              </li>
            </ul>
          </a-collapse-panel>
        </a-collapse>
      </template>
    </a-alert>

    <a-empty v-if="blocks.length === 0" description="没有可展示的解析文本" />
    <div v-else ref="scrollContainer" class="document-scroll">
      <article
        v-for="block in blocks"
        :id="blockElementId(block.id)"
        :key="block.id"
        class="document-block"
        :class="{ 'document-block--focused': focusedBlockId === block.id }"
        :data-block-id="block.id"
      >
        <div class="block-meta">
          <span class="block-id">{{ block.id }}</span>
          <span>{{ block.kind || 'block' }}</span>
          <span v-if="getSectionTitle(block.id)">{{ getSectionTitle(block.id) }}</span>
          <span v-if="block.source_location?.page_number">第 {{ block.source_location.page_number }} 页</span>
        </div>
        <p class="block-text">
          <template v-for="(segment, index) in segmentsFor(block)" :key="`${block.id}-${index}-${segment.mark?.key || 'text'}`">
            <mark
              v-if="segment.kind === 'highlight' && segment.mark"
              class="contract-highlight"
              :class="[
                segment.mark.isSensitive ? 'contract-highlight--sensitive' : 'contract-highlight--normal',
                { 'contract-highlight--focused': focusedMarkKey === segment.mark.key },
              ]"
              :data-mark-key="segment.mark.key"
              :data-clause-index="segment.mark.clauseIndex"
              :title="highlightTitle(segment.mark)"
            >{{ segment.text }}</mark>
            <template v-else>{{ segment.text }}</template>
          </template>
        </p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'

import type { ParsedDocumentBlock, ParsedDocumentSection, ReviewWarning } from '../../api/internalContractReview'
import type { ClauseTarget, HighlightIndex, HighlightMark } from '../../utils/contractHighlight'
import { renderHighlightSegments } from '../../utils/contractHighlight'

const props = withDefaults(defineProps<{
  blocks: ParsedDocumentBlock[]
  sections?: ParsedDocumentSection[]
  parseWarnings?: ReviewWarning[]
  highlightIndex: HighlightIndex
}>(), {
  sections: () => [],
  parseWarnings: () => [],
})

const scrollContainer = ref<HTMLElement | null>(null)
const focusedBlockId = ref<string | null>(null)
const focusedMarkKey = ref<string | null>(null)
let focusTimer: ReturnType<typeof setTimeout> | null = null

function segmentsFor(block: ParsedDocumentBlock) {
  return renderHighlightSegments(block.text, props.highlightIndex.marksByBlock[block.id] ?? [])
}

function getSectionTitle(blockId: string): string | null {
  return props.sections.find((section) => section.block_ids.includes(blockId))?.title ?? null
}

function blockElementId(blockId: string): string {
  return `contract-block-${blockId}`
}

function highlightTitle(mark: HighlightMark): string {
  return `条款 #${mark.clauseIndex + 1}${mark.riskLevel ? ` · ${mark.riskLevel}` : ''}`
}

function focusClause(target: ClauseTarget | undefined): void {
  if (!target?.blockId || target.disabled) return
  const blockElement = document.getElementById(blockElementId(target.blockId))
  if (!blockElement) return

  focusedBlockId.value = target.blockId
  focusedMarkKey.value = target.markKey ?? null
  blockElement.scrollIntoView({ behavior: 'smooth', block: 'center' })
  blockElement.setAttribute('tabindex', '-1')
  blockElement.focus({ preventScroll: true })

  if (focusTimer) clearTimeout(focusTimer)
  focusTimer = setTimeout(() => {
    focusedBlockId.value = null
    focusedMarkKey.value = null
  }, 2_400)
}

function warningText(warning: ReviewWarning): string {
  if (typeof warning.message === 'string' && warning.message.trim()) return warning.message
  if (typeof warning.code === 'string' && warning.code.trim()) return warning.code
  return '解析结果包含未分类提示。'
}

defineExpose({ focusClause })
</script>

<style scoped>
.document-pane {
  min-width: 0;
  min-height: 580px;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

.pane-header {
  min-height: 76px;
  padding: 18px 20px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  border-bottom: 1px solid var(--color-border);
}

.pane-header h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 16px;
  line-height: 1.35;
}

.pane-header p {
  margin: 5px 0 0;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.parse-warning {
  margin: 12px 16px 0;
}

.warning-list {
  margin: 0;
  padding-left: 18px;
}

.document-scroll {
  flex: 1;
  max-height: calc(100vh - 260px);
  overflow: auto;
  padding: 16px;
}

.document-block {
  scroll-margin-top: 84px;
  margin-bottom: 10px;
  padding: 12px 14px;
  border: 1px solid transparent;
  border-radius: var(--radius);
  background: #ffffff;
  transition: border-color 160ms ease, background 160ms ease, box-shadow 160ms ease;
}

.document-block:hover {
  background: #fbfdff;
}

.document-block--focused {
  border-color: var(--color-primary-border);
  background: var(--color-primary-bg);
  box-shadow: 0 0 0 4px rgba(0, 122, 204, 0.1);
}

.document-block:focus-visible {
  outline: 3px solid rgba(0, 122, 204, 0.22);
  outline-offset: 2px;
}

.block-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px 9px;
  margin-bottom: 7px;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.4;
}

.block-id {
  color: var(--color-primary-hover);
  font-weight: 700;
}

.block-text {
  margin: 0;
  color: var(--color-text-primary);
  font-size: 14px;
  line-height: 1.85;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.contract-highlight {
  padding: 1px 2px;
  border-radius: 2px;
  color: inherit;
  transition: box-shadow 160ms ease, background 160ms ease;
}

.contract-highlight--normal {
  background: #eaf5ff;
}

.contract-highlight--sensitive {
  background: #fff1d6;
  box-shadow: inset 0 -2px 0 #d97706;
}

.contract-highlight--focused {
  background: #ffd591;
  box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.25);
}

@media (max-width: 1024px) {
  .document-scroll {
    max-height: none;
  }
}
</style>
