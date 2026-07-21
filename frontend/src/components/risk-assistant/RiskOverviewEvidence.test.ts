// @vitest-environment happy-dom

import { defineComponent } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import type {
  BusinessOverviewProjection,
  RiskAuditItem,
  RiskSource,
} from '../../api/internalRiskAssistant'
import RiskChecksPanel from './RiskChecksPanel.vue'
import RiskEvidenceDrawer from './RiskEvidenceDrawer.vue'
import RiskOverviewTable from './RiskOverviewTable.vue'

const PassThrough = defineComponent({ template: '<div><slot name="title" /><slot /><slot name="description" /></div>' })
const ButtonStub = defineComponent({
  emits: ['click'],
  template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
})
const AlertStub = defineComponent({
  props: ['message', 'description'],
  template: '<div>{{ message }} {{ description }}<slot name="description" /></div>',
})

const global = {
  stubs: {
    'a-card': PassThrough,
    'a-tag': PassThrough,
    'a-empty': PassThrough,
    'a-alert': AlertStub,
    'a-button': ButtonStub,
    'a-drawer': defineComponent({
      props: { open: Boolean },
      emits: ['close'],
      template: '<div v-if="open"><slot /></div>',
    }),
    FileSearchOutlined: PassThrough,
  },
}

function projection(): BusinessOverviewProjection {
  return {
    business_code: 'BIZ-001',
    generated_at: '2026-07-20T10:00:00+08:00',
    rows: [
      {
        code: 'business_mode',
        label: '业务模式',
        content: '联销（预付款+联合销售）以及一段很长的业务模式原文，不在前端摘要或枚举化',
        status: 'READY',
        source_files: ['业务审批最终版.docx'],
        field_codes: ['raw_business_mode_text'],
        is_human_reviewed: false,
      },
      {
        code: 'contract_quantity',
        label: '合同约定数量',
        content: '采购约定：2000 吨；销售约定：1980 吨',
        status: 'PARTIAL',
        source_files: ['上游供货协议.pdf', '客户供货协议.pdf'],
        field_codes: ['purchase_quantity', 'sales_quantity'],
        is_human_reviewed: true,
      },
      {
        code: 'deposit_ratio',
        label: '保证金比例',
        content: '未识别/未明示',
        status: 'MISSING',
        source_files: [],
        field_codes: ['deposit_ratio'],
        is_human_reviewed: false,
      },
    ],
  }
}

function auditItems(): RiskAuditItem[] {
  return [{
    field_code: 'raw_business_mode_text',
    label: '业务模式',
    normalized_value: '联销',
    status: 'FOUND',
    sources: [{ original_filename: '业务审批最终版.docx', quote: '联销' }],
  }]
}

describe('risk overview, checks, and evidence components', () => {
  it('renders long source text, stable statuses, and non-standard original filenames', async () => {
    const wrapper = mount(RiskOverviewTable, {
      props: { projection: projection(), auditItems: auditItems() },
      global,
    })

    expect(wrapper.text()).toContain('不在前端摘要或枚举化')
    expect(wrapper.text()).toContain('客户供货协议.pdf')
    expect(wrapper.text()).toContain('部分信息')
    expect(wrapper.text()).toContain('未识别/未明示')
    expect(wrapper.text()).toContain('人工复核')

    await wrapper.find('tbody tr').trigger('click')
    expect(wrapper.emitted('show-audit')?.[0]?.[0]).toEqual(auditItems())
  })

  it('shows generic checks without fabricating ERP columns and emits input evidence', async () => {
    const source = { original_filename: '采购合同.pdf', quote: '含税总金额' }
    const evidence = [{ field_code: 'purchase_amount_tax_included', sources: [source] }]
    const wrapper = mount(RiskChecksPanel, {
      props: {
        warnings: ['NON_CRITICAL_MISSING:key_customer_discount'],
        checks: [{
          rule_code: 'DEPOSIT_RATIO_CHECK',
          outcome: 'WARNING',
          message: '合同明示比例，未明示金额',
          affected_fields: ['deposit_ratio', 'deposit_amount'],
          input_evidence: evidence,
        }],
      },
      global,
    })

    expect(wrapper.text()).toContain('DEPOSIT_RATIO_CHECK')
    expect(wrapper.text()).not.toContain('ERP 匹配')
    expect(wrapper.text()).toContain('查看输入证据（1）')
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('show-evidence')?.[0]?.[0]).toEqual([source])
  })

  it('warns when precise browser coordinates are unavailable and opens only authorized originals', async () => {
    const sources: RiskSource[] = [{
      document_id: 'document-1',
      original_filename: '客户供货协议.pdf',
      declared_document_type: 'SALES_CONTRACT',
      page_number: 2,
      block_id: 'page-2-block-7',
      quote: '甲方向乙方采购货物',
    }]
    const wrapper = mount(RiskEvidenceDrawer, {
      props: { open: true, sources },
      global,
    })

    expect(wrapper.text()).toContain('不绘制 OCR 位置高亮')
    expect(wrapper.text()).toContain('无精确坐标')
    expect(wrapper.text()).toContain('page-2-block-7')
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('open-document')).toEqual([['document-1']])
  })
})
