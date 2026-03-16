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

      hmr: true,   // 启用热模块替换

      // 严格限制文件监视范围，避免监视 venv 目录
      fs: {
        allow: [
          path.resolve(__dirname, './src'),
          path.resolve(__dirname, './public'),
          path.resolve(__dirname, './node_modules'),
          path.resolve(__dirname),  // 项目根目录（用于 index.html）
        ],
      },
      watch: {
        // 显式忽略这些目录和文件
        ignored: [
          '**/venv/**',
          '**/.venv/**',
          '**/env/**',
          '**/__pycache__/**',
          '**/*.pyc',
          '**/*.db',
          '**/*.db-shm',
          '**/*.db-wal',
          '**/oasis_simulation.db*',
          '**/dev-logs/**',
        ],
      },
    },

    optimizeDeps: {
      exclude: ['torch', 'better-sqlite3'],
    },

    // 忽略不需要监听的目录
    ignore: [
      '**/venv/**',
      '**/.venv/**',
      '**/env/**',
      '**/node_modules/**',
    ],
  };
});
