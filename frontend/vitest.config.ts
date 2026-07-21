import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  define: {
    __INTERNAL_BUILD__: JSON.stringify(true),
  },
  test: {
    environment: 'node',
  },
})
