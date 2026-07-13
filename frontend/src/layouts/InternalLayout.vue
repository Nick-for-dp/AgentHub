<template>
  <a-layout class="internal-shell">
    <a-layout-header class="internal-header">
      <router-link class="internal-brand" to="/internal/contract-review" aria-label="返回合同审查工作台">
        <FileProtectOutlined class="brand-icon" />
        <span>AgentHub 合同审查</span>
      </router-link>
      <div class="header-actions">
        <a-tag color="blue">内部环境</a-tag>
        <a-dropdown v-if="auth.currentUser" trigger="click" placement="bottomRight">
          <button type="button" class="user-button" :aria-label="`当前用户 ${auth.currentUser.name}`">
            <span class="user-avatar">{{ getUserInitial(auth.currentUser.name) }}</span>
            <span class="user-name">{{ auth.currentUser.name }}</span>
            <DownOutlined class="down-icon" />
          </button>
          <template #overlay>
            <a-menu>
              <a-menu-item key="identity" disabled>{{ auth.currentUser.name }}</a-menu-item>
              <a-menu-divider />
              <a-menu-item key="logout" @click="handleLogout">
                <LogoutOutlined />
                退出登录
              </a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </div>
    </a-layout-header>
    <a-layout-content class="internal-content">
      <router-view />
    </a-layout-content>
  </a-layout>
</template>

<script setup lang="ts">
import { DownOutlined, FileProtectOutlined, LogoutOutlined } from '@ant-design/icons-vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function handleLogout(): Promise<void> {
  await auth.doLogout()
  await router.push('/login')
}

function getUserInitial(name: string): string {
  return name.trim().slice(0, 1).toUpperCase() || '用'
}
</script>

<style scoped>
.internal-shell {
  min-height: 100vh;
  background: var(--color-bg-page);
}

.internal-header {
  position: sticky;
  top: 0;
  z-index: 20;
  height: 58px;
  padding: 0 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(255, 255, 255, 0.96);
  border-bottom: 1px solid var(--color-border);
  box-shadow: 0 1px 6px rgba(15, 23, 42, 0.05);
  line-height: 1;
  backdrop-filter: blur(12px);
}

.internal-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--color-text-primary);
  font-size: 17px;
  font-weight: 700;
}

.internal-brand:hover {
  color: var(--color-primary);
}

.brand-icon {
  color: var(--color-primary);
  font-size: 22px;
}

.header-actions,
.user-button {
  display: flex;
  align-items: center;
}

.header-actions {
  gap: 12px;
}

.user-button {
  gap: 8px;
  min-height: 38px;
  padding: 3px 7px 3px 3px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--color-text-primary);
  cursor: pointer;
}

.user-button:hover,
.user-button:focus-visible {
  border-color: var(--color-primary-border);
  background: var(--color-primary-bg);
}

.user-button:focus-visible {
  outline: 3px solid rgba(0, 122, 204, 0.16);
  outline-offset: 2px;
}

.user-avatar {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--color-primary);
  color: #ffffff;
  font-weight: 700;
}

.user-name {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.down-icon {
  color: var(--color-text-secondary);
  font-size: 10px;
}

.internal-content {
  width: 100%;
  padding: 24px 28px 32px;
}

@media (max-width: 640px) {
  .internal-header {
    padding: 0 16px;
  }

  .internal-content {
    padding: 16px 12px 24px;
  }

  .user-name,
  .header-actions :deep(.ant-tag) {
    display: none;
  }
}
</style>
