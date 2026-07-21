<template>
  <main class="login-page">
    <div class="login-card">
      <div class="login-header">
        <span class="profile-label">{{ deploymentPresentation.environmentLabel }}</span>
        <h1>{{ deploymentPresentation.productName }}</h1>
        <p>{{ deploymentPresentation.subtitle }}</p>
      </div>

      <a-form
        :model="form"
        layout="vertical"
        autocomplete="off"
        @finish="handleLogin"
      >
        <a-form-item label="手机号" name="phone" :rules="[{ required: true, message: '请输入手机号' }]">
          <a-input
            v-model:value="form.phone"
            placeholder="请输入手机号"
            size="large"
            :disabled="submitting"
          />
        </a-form-item>

        <a-form-item label="密码" name="password" :rules="[{ required: true, message: '请输入密码' }]">
          <a-input-password
            v-model:value="form.password"
            placeholder="请输入密码"
            size="large"
            :disabled="submitting"
          />
        </a-form-item>

        <a-form-item>
          <a-button
            type="primary"
            html-type="submit"
            size="large"
            :loading="submitting"
            block
          >
            登录
          </a-button>
        </a-form-item>
      </a-form>

      <a-alert
        v-if="errorMsg"
        type="error"
        show-icon
        closable
        :message="errorMsg"
        @close="errorMsg = ''"
      />
    </div>
  </main>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { deploymentPresentation } from '../../config/deploymentProfile'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const form = reactive({ phone: '', password: '' })
const submitting = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  submitting.value = true
  errorMsg.value = ''
  try {
    await auth.login(form.phone, form.password)
    router.replace(auth.defaultHomePath)
  } catch (err: unknown) {
    const e = err as { response?: { status?: number; data?: { message?: string } } }
    if (e.response?.status === 401) {
      errorMsg.value = '手机号或密码错误'
    } else {
      errorMsg.value = e.response?.data?.message || '登录失败，请稍后重试'
    }
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: var(--color-bg-page);
  padding: 24px;
}

.login-card {
  width: min(400px, calc(100% - 32px));
  background: var(--color-bg-white);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 40px 32px 32px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.login-header {
  text-align: center;
  margin-bottom: 32px;
}

.login-header h1 {
  margin: 8px 0 0;
  font-size: 26px;
  line-height: 1.25;
  color: var(--color-primary);
}

.login-header p {
  margin: 4px 0 0;
  color: var(--color-text-secondary);
  font-size: 14px;
}

.profile-label {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 10px;
  border: 1px solid var(--color-primary-border);
  border-radius: 999px;
  background: var(--color-primary-bg);
  color: var(--color-primary-hover);
  font-size: 12px;
  font-weight: 600;
}

.login-card :deep(.ant-input),
.login-card :deep(.ant-input-affix-wrapper) {
  height: 48px;
  min-height: 48px;
  padding: 0 16px;
  display: flex;
  align-items: center;
}

.login-card :deep(.ant-input-affix-wrapper .ant-input) {
  height: auto;
  min-height: 0;
  padding: 0;
}

.login-card :deep(.ant-input-password-icon) {
  display: inline-flex;
  align-items: center;
  font-size: 18px;
}

@media (max-width: 480px) {
  .login-page {
    padding: 16px;
  }

  .login-card {
    width: 100%;
    padding: 32px 24px 28px;
  }

  .login-header h1 {
    font-size: 22px;
  }
}
</style>
