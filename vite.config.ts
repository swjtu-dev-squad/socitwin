import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  
  return {
    plugins: [react(), tailwindcss()],
    
    define: {
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
    },
    
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    
    server: {
      host: true,                    // 允许所有主机
      port: 3000,
      strictPort: true,
      
      // 关键修复：添加Manus当前具体域名 + 通配符
      allowedHosts: [
        'all',                                           // 保留 all
        '.manus.computer',                               // 通配Manus所有子域名
        '3000-ijgxvyou3aujd04xdhd8y-99d67713.us2.manus.computer',  // 当前具体域名
        'localhost',
        '127.0.0.1'
      ],
      
      hmr: false,   // AI Studio 必须禁用
    },
    
    optimizeDeps: {
      exclude: ['torch', 'better-sqlite3'],
    },
  };
});
