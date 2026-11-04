import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const backend = process.env.DOCUMIND_BACKEND || 'http://localhost:8000';
const proxy = {
  '/api': { target: backend, changeOrigin: true },
  '/health': { target: backend, changeOrigin: true },
};

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  build: { target: 'es2022', sourcemap: false },
});
