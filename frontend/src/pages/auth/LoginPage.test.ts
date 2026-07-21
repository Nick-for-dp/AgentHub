// @vitest-environment happy-dom

import { defineComponent } from 'vue'
import { shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  replace: vi.fn(),
  login: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ replace: mocks.replace }),
}))

vi.mock('../../stores/auth', () => ({
  useAuthStore: () => ({
    login: mocks.login,
    defaultHomePath: '/chat',
  }),
}))

import LoginPage from './LoginPage.vue'

const PassThrough = defineComponent({ template: '<div><slot /></div>' })

describe('LoginPage', () => {
  it('renders the current deployment presentation without changing the login form', () => {
    const wrapper = shallowMount(LoginPage, {
      global: {
        stubs: {
          'a-form': PassThrough,
          'a-form-item': PassThrough,
          'a-input': PassThrough,
          'a-input-password': PassThrough,
          'a-button': PassThrough,
          'a-alert': PassThrough,
        },
      },
    })

    expect(wrapper.text()).toContain('AgentHub 营销智能体')
    expect(wrapper.text()).toContain('产品咨询与营销问答服务')
    expect(wrapper.text()).toContain('外部服务')
  })
})
