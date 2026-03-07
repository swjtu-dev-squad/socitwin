# OASIS Dashboard 安装与配置手册

## 目录

1. [系统概述](#系统概述)
2. [环境要求](#环境要求)
3. [快速开始](#快速开始)
4. [详细安装步骤](#详细安装步骤)
5. [配置说明](#配置说明)
6. [故障排查](#故障排查)

---

## 系统概述

OASIS Dashboard 是一个用于实时监控和控制 OASIS (Open-ended Autonomous Social Intelligence Simulation) 引擎的 Web 应用程序。系统采用前后端分离架构，支持基于本地大语言模型的真实社会模拟。

### 系统架构

```
┌─────────────────┐
│   前端 (React)   │ ← 用户界面
└────────┬────────┘
         │ HTTP/WebSocket
┌────────▼────────┐
│  后端 (Express)  │ ← API 服务器
└────────┬────────┘
         │ Python API
┌────────▼────────┐
│  OASIS 引擎      │ ← 模拟引擎
│  (Python)       │
└────────┬────────┘
         │
┌────────▼────────┐
│  Ollama + Qwen  │ ← 本地 LLM
└─────────────────┘
```

---

## 环境要求

### 硬件要求

| 组件 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核 |
| 内存 | 8 GB | 16 GB |
| 硬盘 | 40 GB | 100 GB |
| 网络 | 1 Mbps | 10 Mbps |

### 软件要求

| 软件 | 版本要求 |
|------|---------|
| 操作系统 | Ubuntu 22.04 LTS (推荐) |
| Node.js | 20.x 或更高 |
| Python | 3.11 或更高 |
| Ollama | 最新版本 |
| Nginx | 1.18 或更高 (生产环境) |

---

## 快速开始

### 一、克隆仓库

```bash
git clone https://github.com/SWJTU-AI-Lab/oasis-dashboard.git
cd oasis-dashboard
```

### 二、安装依赖

```bash
# 安装 Node.js 依赖
pnpm install

# 安装 Python 依赖
uv sync
```

### 三、配置本地模型

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 下载 Qwen2.5-3B 模型
ollama pull qwen2.5:3b
```

### 四、启动后端服务器（生产模式）

```bash
# v1.1.0 推荐使用生产模式启动
NODE_ENV=production npx tsx server.ts
```

### 五、访问应用

- 前端: http://localhost:5173
- 后端: http://localhost:3000

---

## 详细安装步骤

### 步骤 1：系统准备

更新系统并安装基础软件：

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git nginx python3 python3-pip python3-venv build-essential
```

### 步骤 2：安装 Node.js

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v  # 验证安装
```

### 步骤 3：安装 Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl status ollama  # 验证服务状态
```

### 步骤 4：下载 Qwen2.5-3B 模型

```bash
ollama pull qwen2.5:3b
ollama list  # 验证模型已下载
```

### 步骤 5：克隆项目并安装依赖

```bash
git clone https://github.com/SWJTU-AI-Lab/oasis-dashboard.git
cd oasis-dashboard
pnpm install
uv sync
```

### 步骤 6：构建前端

```bash
npm run build
```

### 步骤 7：配置 Nginx (生产环境)

创建 Nginx 配置文件：

```bash
sudo nano /etc/nginx/sites-available/oasis-dashboard
```

添加以下内容：

```nginx
server {
    listen 80;
    server_name your_domain_or_ip;

    # 前端静态文件
    location / {
        root /var/www/html;
        try_files $uri $uri/ /index.html;
    }

    # API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:3000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # WebSocket 支持
    location /socket.io/ {
        proxy_pass http://127.0.0.1:3000/socket.io/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

启用配置并重启 Nginx：

```bash
sudo ln -s /etc/nginx/sites-available/oasis-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 步骤 8：部署前端到 Nginx

```bash
sudo rm -rf /var/www/html/*
sudo cp -r dist/* /var/www/html/
```

### 步骤 9：启动后端服务

使用 PM2 管理后端进程：

```bash
sudo npm install -g pm2
pm2 start "pnpm dev" --name oasis-backend
pm2 startup
pm2 save
```

---

## 配置说明

### 环境变量

创建 `.env` 文件（可选）：

```bash
# Ollama 配置
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b

# 数据库配置
OASIS_DB_PATH=./oasis_simulation.db

# 服务器配置
PORT=3000
```

### API 配置

前端 API 配置文件：`src/lib/api.ts`

```typescript
const api = axios.create({
  baseURL: '/api',  // 生产环境使用相对路径
  timeout: 60000,
});
```

---

## 故障排查

### 问题 1：Ollama 服务未启动

**症状**：后端报错 "Connection refused to Ollama"

**解决方案**：

```bash
sudo systemctl start ollama
sudo systemctl status ollama
```

### 问题 2：端口被占用

**症状**：启动服务时报错 "Address already in use"

**解决方案**：

```bash
# 查找占用端口的进程
sudo lsof -i :3000

# 终止进程
sudo kill -9 <PID>
```

### 问题 3：前端白屏

**症状**：访问前端显示白屏

**解决方案**：

1. 检查浏览器控制台错误
2. 确认后端 API 是否正常运行
3. 检查 Nginx 配置是否正确
4. 清除浏览器缓存并强制刷新 (Ctrl+Shift+R)

### 问题 4：模型下载失败

**症状**：`ollama pull` 命令失败

**解决方案**：

```bash
# 检查网络连接
ping ollama.com

# 重试下载
ollama pull qwen2.5:3b

# 或使用代理
export https_proxy=http://your_proxy:port
ollama pull qwen2.5:3b
```

---

## 常见问题

**Q: 是否支持其他 LLM 模型？**

A: 是的，可以通过修改 `oasis_engine.py` 中的模型配置来使用其他模型（如 GPT-4、Gemini 等）。

**Q: 如何增加智能体数量？**

A: 在控制中心页面调整"智能体数量"参数，或修改 `oasis_engine.py` 中的 `agent_count` 参数。

**Q: 数据存储在哪里？**

A: 模拟数据存储在 SQLite 数据库文件中（默认路径：`./oasis_simulation.db`）。

---

**文档版本**: v1.1.0  
**最后更新**: 2026年2月25日

---

## v1.1.0 更新说明

### 新增功能

1. **真实 Qwen2.5-3B LLM 调用**
   - 完全移除 ManualAction
   - 使用真实 LLMAction + Qwen2.5-3B 本地模型
   - 每个 agent 的决策都由真实 LLM 生成

2. **性能优化**
   - Qwen2.5-3B 加载时间：0.26 秒
   - Step 执行时间：0.14-1.08 秒
   - 保持 30 秒超时限制

3. **启动方式变更**
   - **推荐**: 使用 `NODE_ENV=production npx tsx server.ts` 启动后端
   - **原因**: 避免 Vite 文件监控问题（ENOSPC 错误）

### 配置变更

**新增环境变量**:
```bash
# 解决 torch 加载慢的问题
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

**新增文件**:
- `real_oasis_engine_v3.py` - 真实 OASIS 引擎（Qwen2.5-3B + LLMAction）
- `verification_summary.md` - v1.1.0 性能验证报告
- `CHANGELOG_v1.1.0.md` - 版本更新日志
