// @vitest-environment happy-dom

import { defineComponent, nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import type { RiskAssessmentTask, RiskReviewItem } from '../../api/internalRiskAssistant'
import RiskReviewPanel from './RiskReviewPanel.vue'

const PassThrough = defineComponent({ template: '<div><slot name="title" /><slot /><slot name="description" /></div>' })
const RadioGroupStub = defineComponent({
  name: 'RadioGroupStub',
  props: ['value'],
  emits: ['update:value'],
  template: '<div><slot /></div>',
})
const SelectStub = defineComponent({
  name: 'SelectStub',
  props: ['value', 'options'],
  emits: ['update:value'],
  template: '<div class="select-stub" />',
})
const TextareaStub = defineComponent({
  name: 'TextareaStub',
  props: ['value'],
  emits: ['update:value'],
  template: '<textarea />',
})
const ButtonStub = defineComponent({
  name: 'ButtonStub',
  props: { disabled: Boolean, loading: Boolean },
  emits: ['click'],
  template: '<button type="button" :disabled="disabled || loading" @click="$emit(\'click\')"><slot /></button>',
})
const AlertStub = defineComponent({
  props: ['message', 'description'],
  template: '<div>{{ message }} {{ description }}<slot name="description" /></div>',
})

const global = {
  stubs: {
    'a-card': PassThrough,
    'a-tag': PassThrough,
    'a-alert': AlertStub,
    'a-empty': PassThrough,
    'a-descriptions': PassThrough,
    'a-descriptions-item': PassThrough,
    'a-form': PassThrough,
    'a-form-item': PassThrough,
    'a-radio-group': RadioGroupStub,
    'a-radio': PassThrough,
    'a-select': SelectStub,
    'a-textarea': TextareaStub,
    'a-button': ButtonStub,
    'a-collapse': PassThrough,
    'a-collapse-panel': PassThrough,
  },
}

function task(): RiskAssessmentTask {
  return {
    id: 'risk-1',
    status: 'WAITING_REVIEW',
    agent_code: 'risk-assistant',
    business_code: 'BIZ-001',
    checkpoint_version: 2,
    versions: {},
    documents: [],
    review_events: [],
    created_at: '2026-07-20T10:00:00+08:00',
    updated_at: '2026-07-20T10:01:00+08:00',
  }
}

function fieldItem(): RiskReviewItem {
  return {
    id: 'review-1',
    target_kind: 'FIELD',
    target_code: 'goods_name',
    alternatives: ['焦炭', '焦粉'],
    sources: [],
    is_resolved: false,
  }
}

function mountPanel(overrides: Record<string, unknown> = {}) {
  return mount(RiskReviewPanel, {
    props: {
      task: task(),
      item: fieldItem(),
      auditItems: [{ field_code: 'goods_name', label: '货物名称', status: 'UNRESOLVED' }],
      submitting: false,
      ...overrides,
    },
    global,
  })
}

describe('RiskReviewPanel', () => {
  it('requires a reason and submits the selected active candidate', async () => {
    const wrapper = mountPanel()
    const button = wrapper.findComponent(ButtonStub)
    expect(button.props('disabled')).toBe(true)

    wrapper.findComponent(SelectStub).vm.$emit('update:value', '0')
    wrapper.findComponent(TextareaStub).vm.$emit('update:value', '根据销售合同品名确认')
    await nextTick()
    expect(button.props('disabled')).toBe(false)
    await button.trigger('click')

    expect(wrapper.emitted('submit')?.[0]?.[0]).toEqual({
      action: 'SELECT_VALUE',
      value: '焦炭',
      reason: '根据销售合同品名确认',
    })
  })

  it('supports manual correction and confirmed missing', async () => {
    const corrected = mountPanel()
    corrected.findComponent(RadioGroupStub).vm.$emit('update:value', 'CORRECT_VALUE')
    await nextTick()
    const correctedInputs = corrected.findAllComponents(TextareaStub)
    correctedInputs[0]!.vm.$emit('update:value', '锠铁合金')
    correctedInputs[1]!.vm.$emit('update:value', '以采购合同首页为准')
    await nextTick()
    await corrected.findComponent(ButtonStub).trigger('click')
    expect(corrected.emitted('submit')?.[0]?.[0]).toMatchObject({
      action: 'CORRECT_VALUE',
      value: '锠铁合金',
    })

    const missing = mountPanel()
    missing.findComponent(RadioGroupStub).vm.$emit('update:value', 'MARK_MISSING')
    await nextTick()
    missing.findComponent(TextareaStub).vm.$emit('update:value', '合同及附件均未明示')
    await nextTick()
    await missing.findComponent(ButtonStub).trigger('click')
    expect(missing.emitted('submit')?.[0]?.[0]).toMatchObject({ action: 'MARK_MISSING' })
  })

  it('disables duplicate submission and displays checkpoint conflict guidance', () => {
    const wrapper = mountPanel({
      submitting: true,
      conflictMessage: '该复核节点已更新，请重新确认。',
    })

    expect(wrapper.text()).toContain('该复核节点已更新')
    expect(wrapper.findComponent(ButtonStub).props('loading')).toBe(true)
    expect(wrapper.findComponent(ButtonStub).attributes('disabled')).toBeDefined()
  })
})
