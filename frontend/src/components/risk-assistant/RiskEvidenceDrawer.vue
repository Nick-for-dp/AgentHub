<template>
  <a-drawer
    :open="open"
    class="evidence-drawer"
    title="来源证据"
    :width="560"
    placement="right"
    @close="$emit('close')"
  >
    <a-alert
      class="coordinate-warning"
      type="info"
      show-icon
      message="一期不绘制 OCR 位置高亮"
      description="页码、block id 和 bbox 仅按原始证据展示；如果没有浏览器坐标转换契约，不会绘制近似框。"
    />
    <a-empty v-if="sources.length === 0" description="当前项没有可用来源证据" />
    <div v-else class="source-list">
      <article v-for="(source, index) in sources" :key="sourceKey(source, index)" class="source-card">
        <header>
          <div>
            <FileSearchOutlined />
            <strong>{{ source.original_filename || source.source || '未知文件' }}</strong>
          </div>
          <a-button
            v-if="source.document_id"
            size="small"
            :loading="busy"
            @click="$emit('open-document', source.document_id)"
          >
            打开原件
          </a-button>
        </header>
        <dl>
          <div><dt>声明类型</dt><dd>{{ source.declared_document_type || '-' }}</dd></div>
          <div><dt>类型校验</dt><dd>{{ source.type_validation_status || '-' }}</dd></div>
          <div><dt>页码</dt><dd>{{ source.page_number ?? '-' }}</dd></div>
          <div><dt>Block ID</dt><dd>{{ source.block_id || '-' }}</dd></div>
          <div><dt>BBox</dt><dd>{{ source.bbox?.length ? `[${source.bbox.join(', ')}]` : '无精确坐标' }}</dd></div>
        </dl>
        <blockquote v-if="source.quote">{{ source.quote }}</blockquote>
        <a-alert
          v-for="warning in source.type_validation_warnings || []"
          :key="warning"
          class="source-warning"
          type="warning"
          show-icon
          :message="warning"
        />
      </article>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { FileSearchOutlined } from '@ant-design/icons-vue'

import type { RiskSource } from '../../api/internalRiskAssistant'

defineProps<{
  open: boolean
  sources: RiskSource[]
  busy?: boolean
}>()

defineEmits<{
  close: []
  'open-document': [documentId: string]
}>()

function sourceKey(source: RiskSource, index: number): string {
  return [source.document_id, source.block_id, source.page_number, index].filter(Boolean).join(':')
}
</script>

<style scoped>
.coordinate-warning {
  margin-bottom: 16px;
}

.source-list {
  display: grid;
  gap: 12px;
}

.source-card {
  padding: 14px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #ffffff;
}

.source-card header,
.source-card header > div,
.source-card dl > div {
  display: flex;
}

.source-card header {
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.source-card header > div {
  min-width: 0;
  align-items: center;
  gap: 8px;
  color: var(--color-primary);
}

.source-card strong {
  color: var(--color-text-primary);
  overflow-wrap: anywhere;
}

.source-card dl {
  margin: 14px 0 0;
  display: grid;
  gap: 7px;
}

.source-card dl > div {
  gap: 10px;
}

.source-card dt {
  width: 82px;
  flex: none;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.source-card dd {
  min-width: 0;
  margin: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  overflow-wrap: anywhere;
}

blockquote {
  margin: 14px 0 0;
  padding: 10px 12px;
  border-left: 3px solid var(--color-primary);
  background: #f6f9fc;
  color: var(--color-text-primary);
  line-height: 1.65;
  white-space: pre-wrap;
}

.source-warning {
  margin-top: 10px;
}

@media (max-width: 600px) {
  :global(.evidence-drawer .ant-drawer-content-wrapper) {
    width: 100% !important;
    max-width: 100vw;
  }
}
</style>
