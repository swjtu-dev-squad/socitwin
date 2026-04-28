# E2E测试自动化完整指南

## 📋 方案概述

**目标**：在代码merge到main分支后，能够在AutoDL云服务器上自动运行E2E测试（需要调用本地模型）

**挑战**：AutoDL按小时计费，无法7x24运行

**解决方案**：GitHub Actions智能检测 + SSH远程执行

- ✅ **自动触发**：代码push到main时自动尝试运行
- ✅ **智能检测**：AutoDL在线时自动测试，离线时优雅跳过
- ✅ **手动触发**：任何时候都可以手动运行测试

---

## 🎯 工作流程

### 场景1：AutoDL在线（完全自动化）

```
代码push到main
   ↓
GitHub Actions自动触发
   ↓
检测SSH连接 → ✅ 成功
   ↓
自动运行E2E测试（quick模式）
   ↓
显示测试结果
```

### 场景2：AutoDL离线（优雅提醒）

```
代码push到main
   ↓
GitHub Actions自动触发
   ↓
检测SSH连接 → ❌ 失败
   ↓
显示友好提示：
   ⚠️ AutoDL 服务器未在线
   📋 要运行测试，请：
      1. 开启 AutoDL
      2. 手动触发 workflow
   ↓
Workflow标记为成功（skipped状态）
```

### 场景3：手动触发（任何时候）

```
访问GitHub Actions页面
   ↓
点击 "E2E Test" → "Run workflow"
   ↓
选择参数（test_mode/platform/agent_count）
   ↓
运行测试并返回结果
```

---

## 📝 实施步骤

### 步骤1：生成SSH密钥（在本地执行）

在**你的本地机器**上运行以下命令：

```bash
# 生成SSH密钥对
ssh-keygen -t ed25519 -C "github-actions-e2e" -f ~/.ssh/github_actions_e2e
```

输出示例：
```
Generating public/private ed25519 key pair.
Enter passphrase (empty for no passphrase): [直接回车，不设置密码]
Enter same passphrase again: [直接回车]
Your identification has been saved in /home/youruser/.ssh/github_actions_e2e
Your public key has been saved in /home/youruser/.ssh/github_actions_e2e.pub
```

#### 查看私钥（用于GitHub配置）

```bash
cat ~/.ssh/github_actions_e2e
```

**复制整个输出**（包括 `-----BEGIN OPENSSH PRIVATE KEY-----` 和 `-----END OPENSSH PRIVATE KEY-----`），保存到剪贴板。

#### 查看公钥（用于AutoDL配置）

```bash
cat ~/.ssh/github_actions_e2e.pub
```

复制公钥内容（类似 `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIxxx github-actions-e2e`）。

---

### 步骤2：配置AutoDL服务器

#### 2.1 开启AutoDL实例

登录 [AutoDL控制台](https://www.autodl.com/)，启动你的实例。

#### 2.2 获取服务器信息

在AutoDL控制台找到SSH连接信息，通常显示为：
```
ssh -p 42946 root@connect.westb.seetacloud.com
```

你需要记录：
- **主机地址**：`connect.westb.seetacloud.com`
- **SSH端口**：`42946`（不是默认的22）
- **用户名**：`root`
- **密码**：控制台显示的密码

#### 2.3 连接到AutoDL

```bash
# 使用AutoDL提供的密码连接
ssh -p 42946 root@connect.westb.seetacloud.com

# 输入AutoDL控制台显示的密码
```

#### 2.4 添加GitHub Actions公钥到AutoDL

在AutoDL服务器上运行：

```bash
# 创建.ssh目录（如果不存在）
mkdir -p ~/.ssh
chmod 700 ~/.ssh

# 添加公钥（将步骤1中复制的公钥粘贴到这里）
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIxxx github-actions-e2e" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### 2.5 在AutoDL上克隆项目

```bash
# 安装git（如果没有）
apt update && apt install -y git

# 克隆项目
git clone https://github.com/swjtu-dev-squad/socitwin.git
cd socitwin

# 记录项目路径（用于GitHub配置）
pwd  # 通常是 /root/socitwin
```

#### 2.6 安装项目依赖

```bash
cd socitwin/backend

# 安装uv包管理器
pip install uv

# 安装项目依赖
uv sync --dev

# 测试本地运行（可选）
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

按 `Ctrl+C` 停止服务器。

#### 2.7 测试SSH连接（从本地测试）

回到**本地机器**，测试SSH连接：

```bash
ssh -i ~/.ssh/github_actions_e2e -p 42946 root@connect.westb.seetacloud.com
```

如果连接成功，你应该能看到AutoDL的shell提示符。输入 `exit` 退出。

---

### 步骤3：配置GitHub Secrets

#### 3.1 打开GitHub Secrets设置

1. 访问：https://github.com/swjtu-dev-squad/socitwin
2. 点击 **Settings**（设置）
3. 左侧菜单找到 **Secrets and variables** → **Actions**
4. 点击 **New repository secret**

#### 3.2 添加以下3个Secrets

点击 **New repository secret**，逐个添加：

| Name | Secret | 说明 |
|------|--------|------|
| `SSH_PRIVATE_KEY` | 私钥完整内容 | 步骤1中 `cat ~/.ssh/github_actions_e2e` 的输出 |
| `SSH_HOST` | AutoDL主机地址 | 例如：`connect.westb.seetacloud.com` |
| `SSH_PORT` | SSH端口号 | 例如：`42946` |

**重要提示**：
- `SSH_PRIVATE_KEY` 必须包含完整的密钥内容（包括BEGIN/END行）
- `SSH_HOST` 填写AutoDL提供的主机地址（不是IP）
- `SSH_PORT` 填写SSH端口号（在AutoDL控制台显示）

**注意**：以下值已硬编码在workflow中，无需配置：
- `SSH_USER`: `root`
- `PROJECT_PATH`: `/root/socitwin`

添加完成后，Secrets列表应该显示：
```
✓ SSH_PRIVATE_KEY
✓ SSH_HOST
✓ SSH_PORT
```

---

### 步骤4：测试完整流程

#### 4.1 提交workflow文件到GitHub

```bash
# 在本地项目目录
git add .github/workflows/e2e-test.yml docs/e2e-test-automation-guide.md
git commit -m "feat: add E2E test automation workflow"
git push origin <your-branch>
```

#### 4.2 开启AutoDL服务器

确保AutoDL实例正在运行。

#### 4.3 手动触发Workflow

1. 访问：https://github.com/swjtu-dev-squad/socitwin/actions
2. 左侧点击 **"E2E Test"**
3. 右侧点击 **"Run workflow"**
4. 选择参数：
   - **test_mode**: `quick`（第一次建议用quick）
   - **platform**: `twitter`
   - **agent_count**: `3`
5. 点击绿色的 **"Run workflow"** 按钮

#### 4.4 监控执行

点击运行中的workflow，实时查看日志输出。

#### 4.5 验证结果

成功的话，你会看到：
```
✅ All tests passed!
✅ E2E tests completed successfully!
```

---

## 🚀 日常使用

### 自动触发（AutoDL在线时）

```bash
# 你只需要正常push代码
git add .
git commit -m "feat: new feature"
git push origin main

# GitHub Actions会自动运行E2E测试（如果AutoDL在线）
```

### 手动触发（任何时候）

1. 开启AutoDL服务器
2. 访问 GitHub Actions 页面
3. 点击 "E2E Test" → "Run workflow"
4. 选择参数并运行
5. 等待测试完成（2-5分钟quick模式）
6. 查看测试结果
7. 关闭AutoDL（可选，节省费用）

---

## 🔧 故障排查

### 问题1：SSH连接失败

**症状**：`Permission denied (publickey)`

**解决方案**：
```bash
# 确认公钥已添加
ssh -i ~/.ssh/github_actions_e2e root@<AutoDL-IP> "cat ~/.ssh/authorized_keys"

# 应该看到你的公钥，如果没有，重新添加
ssh-copy-id -i ~/.ssh/github_actions_e2e.pub root@<AutoDL-IP>
```

### 问题2：后端服务器启动失败

**症状**：Workflow日志显示 `Server failed to start`

**解决方案**：
```bash
# SSH到AutoDL查看日志
ssh -i ~/.ssh/github_actions_e2e root@<AutoDL-IP>
tail -100 /tmp/server.log

# 或手动启动测试
cd /root/socitwin/backend
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### 问题3：测试超时

**症状**：Workflow运行超过30分钟

**解决方案**：
- 使用 `quick` 模式
- 减少 `agent_count`
- 检查AutoDL网络连接

### 问题4：依赖安装失败

**症状**：`uv sync` 失败

**解决方案**：
```bash
# 在AutoDL上手动安装依赖
cd /root/socitwin/backend
uv sync --dev --reinstall
```

---

## 💰 成本优化建议

1. **按需开启**：只在需要运行E2E测试时开启AutoDL
2. **快速测试**：默认使用quick模式（3个agent，3步）
3. **批量测试**：如果有多处改动，merge后统一测试一次
4. **本地预测试**：在本地先运行快速测试验证

---

## 📊 测试策略

### Quick Test（日常使用）
- 3个agents
- 3步交互
- 预计耗时：2-5分钟
- 适用场景：日常开发、小改动验证

### Full Test（发布前）
- 10个agents
- 50步交互
- 预计耗时：15-30分钟
- 适用场景：发布前验证、重要功能测试

---

## ✅ 配置完成检查清单

- [ ] 本地生成SSH密钥对
- [ ] 私钥已保存（用于GitHub配置）
- [ ] 公钥已添加到AutoDL的 `~/.ssh/authorized_keys`
- [ ] 从本地能SSH连接到AutoDL（使用正确的端口）
- [ ] AutoDL上已克隆项目到 `/root/socitwin`
- [ ] AutoDL上已安装依赖（`uv sync --dev`）
- [ ] GitHub配置了3个Secrets（`SSH_PRIVATE_KEY`、`SSH_HOST`、`SSH_PORT`）
- [ ] Workflow文件已提交到GitHub
- [ ] 成功触发第一次测试
- [ ] 测试结果验证通过

---

## 🔄 后续改进

- [ ] 添加测试结果通知（钉钉/微信）
- [ ] 集成测试覆盖率报告
- [ ] 添加性能基准测试
- [ ] 自动生成测试报告文档
- [ ] 支持多版本模型测试

---

## 📚 相关文档

- [GitHub Actions文档](https://docs.github.com/en/actions)
- [AutoDL使用指南](https://www.autodl.com/docs/)
- [E2E测试代码](../backend/tests/e2e/)
- [Workflow配置文件](../.github/workflows/e2e-test.yml)
