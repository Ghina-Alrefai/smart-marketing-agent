import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // ملف الإعدادات مشترك مع FastAPI في جذر المشروع.
  envDir: '..',
  server: {
    // منفذ ثابت — إن كان مشغولاً يفشل بدل القفز لمنفذ آخر
    // (منفذ مختلف = origin غير مُسجَّل في Google → خطأ no registered origin)
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:8000',
      '/uploads': 'http://localhost:8000',
    },
  },
})
