import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/**
 * Configuração base do Vite para o MVP web do InvestControl.
 */
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
  },
})
