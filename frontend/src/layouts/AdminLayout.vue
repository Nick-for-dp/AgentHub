<template>
  <a-layout class="page-shell">
    <a-layout-sider
      width="220"
      breakpoint="lg"
      collapsed-width="0"
      theme="light"
      collapsible
      :trigger="null"
    >
      <div class="brand">AgentHub</div>
      <a-menu mode="inline" :selected-keys="[selectedKey]">
        <a-menu-item key="/admin/agents">
          <template #icon><RobotOutlined /></template>
          <router-link to="/admin/agents">智能体</router-link>
        </a-menu-item>
        <a-menu-item key="/admin/knowledge-bases">
          <template #icon><BookOutlined /></template>
          <router-link to="/admin/knowledge-bases">知识库</router-link>
        </a-menu-item>
        <a-menu-item key="/admin/api-keys">
          <template #icon><KeyOutlined /></template>
          <router-link to="/admin/api-keys">API Key</router-link>
        </a-menu-item>
        <a-menu-item key="/admin/invocation-records">
          <template #icon><HistoryOutlined /></template>
          <router-link to="/admin/invocation-records">调用记录</router-link>
        </a-menu-item>
        <a-menu-item key="/admin/leads">
          <template #icon><SolutionOutlined /></template>
          <router-link to="/admin/leads">线索记录</router-link>
        </a-menu-item>
        <a-menu-item key="/admin/analytics">
          <template #icon><BarChartOutlined /></template>
          <router-link to="/admin/analytics">数据分析</router-link>
        </a-menu-item>
      </a-menu>
    </a-layout-sider>
    <a-layout>
      <a-layout-header class="admin-header">
        <span class="header-title">AgentHub 管理控制台</span>
        <div class="header-key-area">
          <template v-if="auth.isLoggedIn && auth.currentUser">
            <a-dropdown trigger="click" placement="bottomRight">
              <button type="button" class="admin-avatar-button" :title="auth.currentUser.name">
                <span class="admin-avatar">{{ getUserInitial(auth.currentUser.name) }}</span>
              </button>
              <template #overlay>
                <a-menu>
                  <a-menu-item key="user" disabled>
                    {{ auth.currentUser.name }}
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item key="logout" @click="handleLogout">
                    退出登录
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </template>
        </div>
      </a-layout-header>
      <a-layout-content class="page-content admin-content">
        <router-view />
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { BarChartOutlined, BookOutlined, HistoryOutlined, KeyOutlined, RobotOutlined, SolutionOutlined } from '@ant-design/icons-vue'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const selectedKey = computed(() => route.path)

async function handleLogout() {
  await auth.doLogout()
  router.push('/login')
}

function getUserInitial(name: string): string {
  return name.trim().slice(0, 1).toUpperCase() || '管'
}
</script>

<style scoped>
.brand {
  height: 56px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-primary);
  border-bottom: 1px solid var(--color-primary-border);
  background: linear-gradient(90deg, rgba(234, 245, 255, 0.9) 0%, rgba(255, 255, 255, 1) 100%);
}

:deep(.ant-layout-sider) {
  border-right: 1px solid var(--color-border);
}

:deep(.ant-menu-item a) {
  color: inherit;
}

.admin-header {
  height: 56px;
  padding: 0 24px;
  background:
    linear-gradient(90deg, rgba(223, 241, 255, 0.92) 0%, rgba(255, 255, 255, 0.98) 44%, rgba(255, 255, 255, 0.98) 100%);
  color: var(--color-text-primary);
  font-weight: 600;
  line-height: 56px;
  border-bottom: 1px solid var(--color-border);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-title {
  font-size: 15px;
}

.header-key-area {
  display: flex;
  align-items: center;
  gap: 8px;
}

.admin-avatar-button {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
}

.admin-avatar-button:focus-visible {
  outline: 3px solid rgba(0, 122, 204, 0.16);
  outline-offset: 2px;
}

.admin-avatar {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #ffffff;
  border-radius: 999px;
  background: linear-gradient(135deg, #0098ff 0%, #13c2c2 100%);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 8px 18px rgba(0, 122, 204, 0.22);
}

.admin-content {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 24px 20px;
  overflow-x: hidden;
}

:deep(.page-toolbar h3) {
  color: #0f172a;
  font-size: 18px;
  font-weight: 700;
}

:deep(.filter-card),
:deep(.issue-card) {
  border: 1px solid rgba(187, 223, 255, 0.72);
  border-radius: var(--radius-lg);
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

:deep(.ant-table-wrapper) {
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
}

:deep(.ant-table-thead > tr > th) {
  background: linear-gradient(180deg, #f8fbff 0%, #eef7ff 100%);
  color: #0f172a;
  font-weight: 700;
}

:deep(.ant-form-inline .ant-form-item) {
  margin-bottom: 10px;
}

:deep(.ant-input),
:deep(.ant-picker),
:deep(.ant-select:not(.ant-select-customize-input) .ant-select-selector),
:deep(.ant-btn) {
  min-height: 34px;
}

:deep(.ant-pagination .ant-pagination-item),
:deep(.ant-pagination .ant-pagination-prev),
:deep(.ant-pagination .ant-pagination-next),
:deep(.ant-pagination .ant-select-selector) {
  min-height: 32px !important;
  height: 32px !important;
  border-radius: var(--radius);
}

:deep(.ant-pagination .ant-select-single) {
  height: 32px;
}

:deep(.ant-pagination .ant-select-selection-item) {
  line-height: 30px;
}

</style>
