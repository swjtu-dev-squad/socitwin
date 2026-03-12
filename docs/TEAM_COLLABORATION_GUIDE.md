# 👥 团队协作与开发指南

> **更新时间**：2026-03-13
> **文档版本**：v2.0
> **项目仓库**：https://github.com/swjtu-dev-squad/oasis-dashboard

---

## 📑 目录

- [💻 开发最佳实践](#-开发最佳实践)
  - [开发环境推荐](#-开发环境推荐)
  - [使用 AI 辅助开发](#-使用-ai-辅助开发以-claude-code-为例)
  - [测试与调试技巧](#️⃣-测试与调试技巧)
- [🌿 分支管理策略](#-分支管理策略)
  - [个人分支规范](#1️⃣-个人分支规范)
  - [代码同步流程](#2️⃣-代码同步流程)
- [📤 提交代码与 Pull Request](#-提交代码与-pull-request)
  - [Commit 规范](#-commit-规范)
  - [Pull Request 流程](#-pull-request-流程)
  - [GitHub Actions 自动检查](#-github-actions-自动检查)
- [📋 Issue 与看板管理](#-issue-与看板管理)
  - [工作流程](#-工作流程)
  - [创建 Issue](#-创建-issue提出任务)
  - [Kanban 看板使用](#-kanban-看板使用)
- [⚠️ 常见问题](#-常见问题)

---

## 💻 开发最佳实践

### 🪟 开发环境推荐

#### Windows 用户：强烈推荐使用 WSL2

> 接近原生的 Linux 体验，少走 90% 弯路

**安装步骤**：
1. 打开 PowerShell（管理员）运行：`wsl --install`
2. 推荐安装 **Ubuntu 最新 LTS 版本**
3. 安装完成后，在 WSL2 中设置开发环境

**优势**：
- ✅ 原生 Linux 工具链支持
- ✅ 更好的文件系统性能
- ✅ Docker 完美支持
- ✅ 避免路径和权限问题

**还有疑问**？
> 可以询问任何 LLM：`"如何在 Windows 上安装 WSL2"`

---

### 🤖 使用 AI 辅助开发（以 Claude Code 为例）

#### 1️⃣ 利用项目文档减少 AI 幻觉

在开发 OASIS 相关功能时，让 AI 索引官方文档以获得更准确的上下文：

**已下载文档位置**：`docs/oasis-llms-full.txt`

**使用方式**：
```markdown
请参考 docs/oasis-llms-full.txt 中的 OASIS 官方文档，
帮我实现一个新的 agent 行为模式
```

**优势**：
- ✅ 减少 AI 幻觉率
- ✅ 代码实现更符合框架规范
- ✅ 避免与现有架构冲突

#### 2️⃣ 开发日志记录技巧

将开发服务器输出重定向到带时间戳的日志文件：

```bash
# 前端开发服务器
pnpm run dev 2>&1 | tee "dev-logs/dev-$(date +%Y%m%d-%H%M).log"

# 后端服务器
node server.ts 2>&1 | tee "dev-logs/server-$(date +%Y%m%d-%H%M).log"

# Python 服务
uv run python server.py 2>&1 | tee "dev-logs/python-$(date +%Y%m%d-%H%M).log"
```

**优势**：
- ✅ 便于 AI 分析错误日志
- ✅ 可追溯历史运行状态
- ✅ 方便问题复现和调试
- ✅ 支持多进程日志分离

**日志管理**：
```bash
# 查看 7 天内的日志
ls -lt dev-logs/*.log | head -7

# 清理 7 天前的日志
find dev-logs/ -name "*.log" -mtime +7 -delete

# 查看最新的错误日志
grep -i "error" dev-logs/dev-$(ls -t dev-logs/ | head -1)
```

#### 3️⃣ AI 交互最佳实践

**🎯 清晰的需求描述**：
```markdown
❌ "帮我修复这个 bug"

✅ "在 src/components/AgentCard.tsx 中，点击删除按钮时报错
   'Cannot read property of undefined'，错误日志见 dev-logs/dev-20260308.log"
```

**📚 提供上下文**：
```markdown
我正在实现 OASIS 的评论功能，根据官方文档（docs/oasis-llms-full.txt
第 123-150 行），需要继承 CommentAction 类。帮我生成一个基础的评论
行为模板
```

**🔄 逐步迭代**：
```markdown
1. "先帮我设计数据结构"
2. "基于上面的设计，实现 Type definitions"
3. "添加 React 组件"
4. "接入后端 API"
```

**✅ 先 plan，后实施**：
涉及到一个较大的改动的时候，先切换到 plan 模式，AI 会创建一个 todo-list.md 追踪更改，不容易遗忘上下文

**💡 让 AI 读取代码**：
```markdown
# 主动让 AI 读取相关文件
"请先阅读 src/components/AgentCard.tsx 和 src/types/agent.ts，
然后帮我添加一个新的属性"
```

#### 4️⃣ 测试与调试技巧

**🧪 用脚本验证功能**

如果你不确定 AI 修改的 feature 是否正常工作，最好的办法是让 AI 写一个测试脚本：

```bash
# 示例：让 AI 写一个 Node.js 测试脚本
"写一个 Node.js 脚本，测试刚添加的登录功能是否正常工作，
包括成功和失败两种情况"
```

**优势**：
- ✅ 快速验证功能，无需手动操作 UI
- ✅ 可以重复执行，方便回归测试
- ✅ 留下测试记录，方便后续排查
- ✅ AI 生成的测试代码往往能发现边界情况

**🔍 用缩小范围的方式定位 Bug**

当出现问题时，不要一次性修改大段代码。用逐步缩小的脚本锁定 bug：

```bash
# 第一步：写一个最小复现脚本
"写一个最简单的脚本，复现这个 bug，
只需要包含核心逻辑，不需要 UI 和其他复杂部分"

# 第二步：逐步排除
"在上面的脚本基础上，逐步添加功能，
看看在哪一步开始出现 bug"

# 第三步：定位具体问题
"现在我们知道问题出在数据处理这一步，
帮我写一个脚本只测试数据解析逻辑"
```

**推荐的调试流程**：
```
发现 bug
    ↓
让 AI 写最小复现脚本（10-20 行）
    ↓
运行脚本确认问题
    ↓
逐步添加代码，缩小问题范围
    ↓
定位到具体函数/变量
    ↓
修复后，用同一脚本验证
```

**示例脚本类型**：
```bash
# Node.js 脚本
node test-login.js

# Python 脚本
python test-api.py

# Bash 脚本（测试 API 或命令）
bash test-endpoint.sh
```

---

## 🌿 分支管理策略

```
main (生产分支)
  ├── lzn（个人开发分支，推荐用自己名字首字母命名，自己可以随便折腾）
  ├── feature/user-auth (功能分支)
  ├── bugfix/login-error (修复分支)
  ├── refactor/database-optimization (重构分支)
  └── docs/update-readme (文档分支)
```

### 1️⃣ 个人分支规范

```bash
# 从 main 创建个人分支
git checkout main
git pull origin main
git checkout -b feature/your-feature-name

# 分支命名规范
feature/功能描述    # 新功能开发
bugfix/问题描述     # Bug 修复
refactor/重构内容   # 代码重构
docs/文档内容       # 文档更新
hotfix/紧急修复     # 生产环境紧急修复
```

### 2️⃣ 代码同步流程

```bash
# 定期从 main 拉取最新代码
git fetch origin
git pull origin/main

# 如有冲突，手动解决后：
git add .
git commit -m "resolve merge conflicts"
```

---

## 📤 提交代码与 Pull Request

### Commit 规范

**推荐做法**：让 AI 读取工作区更改，自动生成 commit message

```bash
# 使用 Claude Code 等工具
"读取工作区的更改，帮我写一份英文的 commit message，然后提交"
```

> ⚠️ **重要提示**：Commit 和 PR 信息尽量使用英文，避免在某些情况下出现乱码

### Pull Request 流程

- ❌ **禁止**直接 push 到 `main` 分支
- ✅ **必须**通过 Pull Request 合并代码
- ✅ **必须**添加项目维护者作为 reviewer
- ✅ **必须**通过 code review 方可合并

**如何写 Pull Request 描述**：
```bash
# 以 lzn -> main 为例
"帮我查看 lzn 领先了 main 哪些 commit，读取这些 commit 的信息，帮我写一个 PR 描述"
```

### 🔍 GitHub Actions 自动检查

#### 什么是 GitHub Actions？

GitHub Actions 是 GitHub 提供的 CI/CD（持续集成/持续部署）自动化工具。当你的代码发生变化时（如提交或创建 PR），它会自动运行一系列预定义的任务来验证代码质量。

#### 为什么必要？

- ✅ **自动发现错误** - 在代码合并前自动运行测试、构建、检查，避免把 bug 带入主分支
- ✅ **统一代码标准** - 自动检查代码格式、语法、类型错误，确保代码质量
- ✅ **节省人工时间** - 无需手动运行测试，系统自动完成
- ✅ **提升团队效率** - 减少代码 review 时的来回修改

#### 如何确保 Check 通过？

**1️⃣ 提交前本地自检**

在推送代码前，先在本地运行相同的检查：

```bash
# 运行构建
pnpm run build

# 运行测试
pnpm run test

# 代码格式检查
pnpm run lint

# 类型检查
pnpm run type-check
```

**2️⃣ 提交后查看 CI 结果**

- 创建 PR 后，GitHub 会自动运行 Actions
- 在 PR 页面底部可以看到检查状态：
  - ✅ **绿色** - 所有检查通过，可以合并
  - ❌ **红色** - 有检查失败，必须修复

**3️⃣ 处理失败的 Check**

当检查失败时：

```bash
# 第一步：点击失败的 Check 查看详细日志
# 找到具体的错误信息和行号

# 第二步：让 AI 帮助修复
"我的 GitHub Actions 检查失败了，错误信息如下：
[粘贴错误日志]
帮我修复这个问题"

# 第三步：修复后重新提交
git add .
git commit -m "fix: resolve CI check failures"
git push
```

**4️⃣ 禁止跳过检查**

- ❌ **不要**在检查失败时强制合并 PR
- ✅ **必须**等到所有检查都通过才能合并
- ⚠️ **注意**：某些检查可能需要几分钟才能完成，请耐心等待

**常见的检查类型**：

| 检查类型 | 目的 | 本地命令 |
|---------|------|---------|
| Build | 确保代码能成功构建 | `pnpm run build` |
| Lint | 检查代码风格和格式 | `pnpm run lint` |
| Test | 运行单元测试 | `pnpm run test` |
| Type Check | 检查类型错误 | `pnpm run type-check` |

**最佳实践**：
```
写代码 → 本地运行检查 → 修复错误 → 提交推送
                                      ↓
                              GitHub Actions 自动运行
                                      ↓
                              ✅ 通过 → 等待 Review
                              ❌ 失败 → 修复后重新推送
```

---

## 📋 Issue 与看板管理

### 🎯 工作流程

**任何要做的事情，都先提 Issue，然后放到 Kanban 看板里跟踪进度。**

```
┌─────────────────────────────────────────────────────┐
│  你发现了一个 bug 或想做个新功能                     │
└──────────────────┬──────────────────────────────────┘
                   ↓
         创建一个 Issue 描述清楚
                   ↓
      把 Issue 添加到 Kanban 的 Backlog
                   ↓
        开始做 → 拖到 Processing
                   ↓
            完成后 → 拖到 Done
                   ↓
            🎉 任务完成！
```

### 创建 Issue（提出任务）

#### 1. 找到 Issues 页面
- 进入仓库：https://github.com/swjtu-dev-squad/oasis-dashboard
- 点击顶部导航栏的 **Issues** 标签

#### 2. 点击 "New Issue"
- 点击绿色的 **"New issue"** 按钮

#### 3. 填写 Issue 信息

**标题（Title）**：简短描述任务
```
❌ 不好：修复bug
✅ 好：修复登录页面在移动端显示错位的问题
```

**描述（Description）**：详细说明
```markdown
### 📝 问题描述
[清晰描述要解决的问题或要实现的功能]

### ✅ 预期行为
[描述期望的结果]

### ❌ 实际行为（仅 Bug）
[描述当前的实际行为]

### 🔍 复现步骤
1. 步骤一
2. 步骤二
3. 步骤三

### 💻 环境信息
- OS: [例如 Ubuntu 22.04 / Windows 11 + WSL2]
- Node.js 版本: [例如 v18.17.0]
- Python 版本: [例如 3.11.0]

### 📌 优先级
- [ ] 🔴 高（阻塞性 bug / 核心功能）
- [ ] 🟡 中（影响体验 / 重要功能）
- [ ] 🟢 低（优化项 / 次要功能）
```

#### 4. 创建 Issue
- 点击右下角的 **"Submit new issue"** 按钮
- ✅ Issue 创建成功！会得到一个编号（如 #1, #2）

---

### Kanban 看板使用

#### 1. 进入 Project
- 访问看板：https://github.com/orgs/swjtu-dev-squad/projects/1

#### 2. 把 Issue 添加进来
- 找到 **"Backlog"** 列（准备做）
- 点击右边的 **+** 号或 **"Add item"**
- 搜索你的 Issue 标题或编号
- 点击添加

#### 3. 移动卡片跟踪进度
- 卡片可以在不同列之间拖动：
  - **Backlog** → 待办事项（想做还没开始）
  - **Processing** → 正在做
  - **Done** → 已完成

---

## ⚠️ 常见问题

### Q: 能不能直接做，不提 Issue？
❌ **不行！** 所有任务都要先提 Issue，方便大家知道你在做什么

### Q: Issue 标题怎么写？
✅ 用动宾结构，清晰简洁：
- "修复登录按钮点击无响应"
- "添加用户头像上传功能"
- "更新 README 文档"

### Q: 卡片可以跨列移动吗？
✅ **可以！** 随时根据实际进度拖动卡片：
- Backlog ←→ Processing ←→ Done

### Q: 别人可以动我的 Issue 吗？
✅ **可以！** 团队协作，任何人都可以：
- 评论你的 Issue
- 移动你创建的卡片
- 帮你完成任务

### Q: 任务很小的改动也要提 Issue 吗？
✅ **建议都提！** 即使是小改动，Issue 能留下记录，方便回顾

---

## 💡 小贴士

1. **提 Issue = 告诉大家你要做什么**
2. **移动卡片 = 更新任务进度**
3. **常看 Kanban = 了解团队整体进度**
4. **不确定怎么做？先提 Issue 问清楚再做**

---

## 🔗 快速链接

- [仓库主页](https://github.com/swjtu-dev-squad/oasis-dashboard)
- [Issues 列表](https://github.com/swjtu-dev-squad/oasis-dashboard/issues)
- [Kanban 看板](https://github.com/orgs/swjtu-dev-squad/projects/1)
