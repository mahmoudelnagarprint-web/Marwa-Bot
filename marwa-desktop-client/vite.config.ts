import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// منفذ 1420 = العرف الثابت لـ Tauri (يُحدَّث في src-tauri/tauri.conf.json)
export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: true, // يسمح بالوصول من الشبكة (الموبايل) للمعاينة
  },
  build: {
    target: 'es2022',
    outDir: 'dist',
  },
})
