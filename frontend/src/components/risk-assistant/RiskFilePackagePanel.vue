<template>
  <a-card class="package-card" :bordered="false">
    <template #title>
      <div class="card-title">
        <div>
          <strong>新建风控任务</strong>
          <span>文件名仅用于展示，请为每份文件选择真实业务类型。</span>
        </div>
        <a-button v-if="files.length" size="small" :disabled="disabled" @click="$emit('reset')">
          清空
        </a-button>
      </div>
    </template>

    <a-form layout="vertical">
      <a-form-item label="业务编号" required>
        <a-input
          :value="businessCode"
          :disabled="disabled"
          placeholder="例如：浙物流杭供20250071S-01X"
          :maxlength="100"
          @update:value="$emit('update:businessCode', $event)"
        />
      </a-form-item>

      <a-upload-dragger
        class="file-drop"
        :show-upload-list="false"
        :before-upload="beforeUpload"
        :disabled="disabled"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        multiple
      >
        <p class="ant-upload-drag-icon"><InboxOutlined /></p>
        <p class="ant-upload-text">选择或拖入采购合同、销售合同、审批表和结算单</p>
        <p class="ant-upload-hint">PDF/DOCX；每份文件独立上传、解析和重试。</p>
      </a-upload-dragger>

      <a-empty v-if="files.length === 0" class="package-empty" description="尚未选择文件" />
      <div v-else class="file-list">
        <article v-for="item in files" :key="item.id" class="file-item">
          <div class="file-identity">
            <FileTextOutlined />
            <div>
              <strong :title="item.file.name">{{ item.file.name }}</strong>
              <span>{{ formatBytes(item.file.size) }}</span>
            </div>
          </div>
          <a-select
            class="type-select"
            :value="item.declaredDocumentType"
            :disabled="disabled"
            placeholder="选择声明类型"
            :options="documentTypeOptions"
            @update:value="$emit('set-type', item.id, $event)"
          />
          <div class="file-state">
            <a-tag :color="phaseColor(item.phase)">{{ phaseLabel(item.phase) }}</a-tag>
            <a-progress
              v-if="['PREPARING_UPLOAD', 'UPLOADING', 'PARSING'].includes(item.phase)"
              :percent="item.phase === 'PARSING' ? 100 : item.progress"
              :show-info="false"
              size="small"
              status="active"
            />
            <span v-if="item.errorMessage" class="file-error">{{ item.errorMessage }}</span>
          </div>
          <div class="file-actions">
            <a-button
              v-if="item.phase === 'FAILED'"
              size="small"
              :disabled="disabled"
              @click="$emit('retry', item.id)"
            >
              重试
            </a-button>
            <a-button size="small" type="text" danger :disabled="disabled" @click="$emit('remove', item.id)">
              <DeleteOutlined />
            </a-button>
          </div>
        </article>
      </div>

      <a-alert v-if="errorMessage" class="package-error" type="error" show-icon :message="errorMessage" />
      <div class="package-actions">
        <a-button type="primary" size="large" :loading="disabled" :disabled="!canSubmit" @click="$emit('submit')">
          创建并执行风控任务
        </a-button>
        <span>执行期间可离开页面，稍后可从最近任务恢复。</span>
      </div>
    </a-form>
  </a-card>
</template>

<script setup lang="ts">
import { DeleteOutlined, FileTextOutlined, InboxOutlined } from '@ant-design/icons-vue'
import type { FileType } from 'ant-design-vue/es/upload/interface'

import type { RiskDocumentType } from '../../api/internalRiskAssistant'
import type { RiskFilePackageItem, RiskFilePhase } from '../../composables/useRiskAssistantWorkbench'

defineProps<{
  files: RiskFilePackageItem[]
  businessCode: string
  disabled: boolean
  canSubmit: boolean
  errorMessage?: string | null
}>()

const emit = defineEmits<{
  'add-files': [files: File[]]
  'set-type': [fileId: string, value: RiskDocumentType | null]
  'remove': [fileId: string]
  'retry': [fileId: string]
  'submit': []
  'reset': []
  'update:businessCode': [value: string]
}>()

const documentTypeOptions: Array<{ value: RiskDocumentType; label: string }> = [
  { value: 'PURCHASE_CONTRACT', label: '采购合同' },
  { value: 'SALES_CONTRACT', label: '销售合同' },
  { value: 'APPROVAL_FORM', label: '供应链业务合同审批表' },
  { value: 'SETTLEMENT_STATEMENT', label: '结算单' },
]

function beforeUpload(file: FileType): boolean {
  emit('add-files', [file])
  return false
}

function phaseLabel(phase: RiskFilePhase): string {
  return {
    SELECTED: '已选择',
    PREPARING_UPLOAD: '准备上传',
    UPLOADING: '上传中',
    PARSING: '解析中',
    READY: '已就绪',
    FAILED: '处理失败',
  }[phase]
}

function phaseColor(phase: RiskFilePhase): string {
  if (phase === 'READY') return 'success'
  if (phase === 'FAILED') return 'error'
  if (phase === 'SELECTED') return 'default'
  return 'processing'
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '-'
  if (value < 1024 * 1024) return `${Math.max(1, Math.round(value / 1024))} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}
</script>

<style scoped>
.package-card {
  border: 1px solid rgba(187, 223, 255, 0.8);
  border-radius: 14px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
}

.card-title,
.card-title > div,
.file-identity,
.package-actions {
  display: flex;
}

.card-title {
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.card-title > div {
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.card-title span,
.package-actions span {
  color: var(--color-text-secondary);
  font-size: 12px;
  font-weight: 400;
}

.file-drop :deep(.ant-upload.ant-upload-drag) {
  border-color: var(--color-primary-border);
  background: #fbfdff;
}

.package-empty {
  margin: 16px 0 4px;
}

.file-list {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.file-item {
  display: grid;
  grid-template-columns: minmax(190px, 1.2fr) minmax(180px, 0.8fr) minmax(140px, 0.7fr) auto;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid var(--color-border);
  border-radius: 10px;
  background: #ffffff;
}

.file-identity {
  min-width: 0;
  align-items: center;
  gap: 10px;
  color: var(--color-primary);
}

.file-identity > div,
.file-state {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.file-identity strong {
  overflow: hidden;
  color: var(--color-text-primary);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-identity span,
.file-error {
  color: var(--color-text-secondary);
  font-size: 11px;
}

.file-error {
  color: #cf1322;
  overflow-wrap: anywhere;
}

.file-actions {
  display: flex;
  gap: 4px;
}

.package-error {
  margin-top: 16px;
}

.package-actions {
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 20px;
}

@media (max-width: 900px) {
  .file-item {
    grid-template-columns: minmax(0, 1fr) minmax(180px, 0.8fr) auto;
  }

  .file-state {
    grid-column: 1 / 3;
    grid-row: 2;
  }
}

@media (max-width: 560px) {
  .file-item {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .type-select,
  .file-state {
    grid-column: 1 / 3;
  }

  .file-state {
    grid-row: auto;
  }

  .package-actions .ant-btn {
    width: 100%;
  }
}
</style>
