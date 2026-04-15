# Dev Meeting 2026年4月15日 - 代码质量保障与功能增强

## 📋 会议主题
- 建立代码质量自动化检查体系
- 实现受控Agent动态添加功能

---

## 🎯 Action Items & Todo List

### Phase 1: 代码质量保障体系 ✅
- [x] **集成前后端静态检查工作流**
  - Issue: [#12](https://github.com/swjtu-dev-squad/socitwin/issues/12)
  - PR: [#13](https://github.com/swjtu-dev-squad/socitwin/pull/13)

- [x] **Backend 检查配置**
  - ✅ 添加 Pyright 类型检查（typeCheckingMode = "standard"）
  - ✅ 配置 Ruff 代码风格检查（硬性失败）
  - ✅ 在 `pyproject.toml` 中添加 Pyright 配置段

- [x] **Frontend 检查配置**
  - ✅ 创建 `.prettierrc` 配置文件
  - ✅ 添加 Prettier npm scripts（format, format:check）
  - ✅ 移除 ESLint 依赖，统一使用 TypeScript + Prettier
  - ✅ 添加 TypeScript + Vite Build 检查

- [x] **CI/CD 工作流**
  - ✅ 创建 `.github/workflows/backend-check.yml`
  - ✅ 创建 `.github/workflows/frontend-check.yml`
  - ✅ 配置 uv（后端）和 pnpm（前端）缓存优化
  - ✅ 所有检查均为**硬性失败**（blocking）

- [x] **代码格式规范化**
  - ✅ 修复所有后端 Python 文件的 Ruff 检查问题
  - ✅ 修复所有前端 TypeScript/TSX 文件的 Prettier 格式问题
  - ✅ 101 个文件格式调整，5,875+ 行，3,783- 行

- [x] **文档完善**
  - ✅ 添加完整的 README.md
  - ✅ 包含项目介绍、快速开始、代码风格规范章节
  - ✅ 添加本地开发工作流程建议

### Phase 2: 受控Agent功能 ✅
- [x] **实现手动添加受控Agent API**
  - Issue: [#1](https://github.com/swjtu-dev-squad/socitwin/issues/1)
  - PR: [#11](https://github.com/swjtu-dev-squad/socitwin/pull/11)

- [x] **核心功能**
  - ✅ POST `/api/sim/agents/controlled` API 端点
  - ✅ 支持批量添加 1-50 个自定义 agents
  - ✅ 可选极化率阈值检查
  - ✅ 完整的 profile 配置支持（interests, political_leaning, mbti 等）

- [x] **架构设计**
  - ✅ 独立的 `ControlledAgentsService` 类
  - ✅ 模块化三层架构（Model-Service-API）
  - ✅ 遵循 FastAPI 最佳实践
  - ✅ 正确集成 OASIS 框架

- [x] **测试验证**
  - ✅ 单个 agent 添加测试
  - ✅ 批量 agents 添加测试
  - ✅ 极化率检查（拒绝/接受）测试
  - ✅ Agent 属性验证测试
  - ✅ API 文档注册测试
  - ✅ 测试成功率：100% (6/6 场景通过)

---

## 📊 技术实现细节

### 代码质量检查工具链

**Backend:**
```bash
# 工具
- Pyright (类型检查，硬性失败)
- Ruff (代码风格检查，硬性失败)

# 配置文件
- backend/pyproject.toml

# 本地检查命令
ruff check . --ignore=E501 --fix
pyright app/
```

**Frontend:**
```bash
# 工具
- Prettier (格式检查，硬性失败)
- TypeScript + Vite Build (类型检查和构建验证，硬性失败)

# 配置文件
- frontend/.prettierrc

# 本地检查命令
pnpm run format
pnpm run build
```

### 检查规则详解

#### 🔧 Pyright 配置与检查内容

**配置文件：** `backend/pyproject.toml`

```toml
[tool.pyright]
include = ["app"]
exclude = ["**/node_modules", "**/__pycache__", "**/.venv"]
typeCheckingMode = "standard"
pythonVersion = "3.11"
stubPath = ""
ignore = ["**/oasis*"]
```

**主要检查项：**

| 检查类别         | 具体内容                       |
| ---------------- | ------------------------------ |
| **类型安全**     | 检测类型不匹配、类型注解缺失   |
| **函数返回类型** | 验证函数返回值与声明的类型一致 |
| **参数类型检查** | 确保函数参数类型正确           |
| **属性访问检查** | 检测对象上不存在的属性访问     |
| **导入检查**     | 验证导入的模块和符号存在       |

**关键配置说明：**
- `typeCheckingMode = "standard"` - 比 `basic` 更严格，比 `strict` 更宽松，适合已有项目
- `ignore = ["**/oasis*"]` - 忽略 OASIS 框架相关文件（第三方库）
- `include = ["app"]` - 只检查 `app/` 目录下的业务代码

#### 🔧 Ruff 配置与检查内容

**配置文件：** `backend/pyproject.toml`

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W"]
```

**启用的规则类别：**

| 规则代码 | 规则名称             | 检查内容                     |
| -------- | -------------------- | ---------------------------- |
| **E**    | Error                | 代码错误（语法、逻辑错误）   |
| **F**    | Pyflakes             | 未使用的导入、变量、重复定义 |
| **I**    | isort                | 导入语句排序和格式化         |
| **N**    | pep8-naming          | 命名规范（变量、函数、类名） |
| **W**    | pycodestyle warnings | 代码风格警告（缩进、空格等） |

**具体检查项详解：**

**1. E - Error（代码错误）**
- 语法错误检测
- 逻辑错误识别
- 代码中的明显问题

**2. F - Pyflakes（未使用代码）**
- ❌ 未使用的导入语句
- ❌ 未使用的变量和函数
- ❌ 重复的函数/变量定义
- ❌ 在使用前未定义的变量

**3. I - isort（导入排序）**
- 导入语句的顺序和分组
- 按标准库、第三方库、本地模块分组
- 删除重复的导入

**4. N - pep8-naming（命名规范）**
- 类名应使用 `CapWords`（驼峰命名）
- 函数和变量应使用 `snake_case`（蛇形命名）
- 常量应使用 `UPPER_CASE`
- 私有方法应使用 `_leading_underscore`

**5. W - pycodestyle warnings（代码风格）**
- 行长度超过 100 字符（CI 中忽略 E501）
- 缺少空格
- 缩进不正确
- 多余的空行

#### 🔧 前端 Prettier 配置

**配置文件：** `frontend/.prettierrc`

```json
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100,
  "arrowParens": "avoid",
  "endOfLine": "lf"
}
```

**格式化规则：**
- `semi: false` - 不使用分号
- `singleQuote: true` - 使用单引号
- `tabWidth: 2` - 缩进 2 个空格
- `trailingComma: "es5"` - ES5 兼容的尾随逗号
- `printWidth: 100` - 行长度限制 100 字符

### CI/CD 检查行为

**重要变更：** 所有检查现在都是**硬性失败**（blocking）

- ❌ Pyright 失败 → 阻断 CI
- ❌ Ruff 失败 → 阻断 CI
- ❌ Prettier 失败 → 阻断 CI
- ❌ Build 失败 → 阻断 CI

**触发条件：**
- Push 到任意分支
- 创建或更新 Pull Request

### 配置策略说明

#### 为什么这样配置？

**1. Pyright 使用 `standard` 模式**
- 比 `basic` 更严格，提供更好的类型安全
- 比 `strict` 更宽松，不会过度限制开发
- 适合已有项目，平衡严格性和实用性
- 提供类似 TypeScript 的类型检查体验

**2. Ruff 忽略 E501（行长度）**
- 在 CI 配置中使用 `--ignore=E501`
- 行长度限制在实际项目中容易造成代码可读性问题
- 100 字符是建议值，不是强制值
- 允许在必要时超出限制（如 URL、长路径等）

**3. 忽略 OASIS 框架文件**
- `ignore = ["**/oasis*"]` - OASIS 是第三方库，不需要检查
- 避免对依赖库的类型检查产生误报
- 专注检查业务代码质量

**4. 只检查 `app/` 目录**
- 专注业务代码，忽略测试和配置文件
- 提高检查速度和准确性
- 减少不必要的误报

**5. 前端移除 ESLint**
- 统一使用 TypeScript + Prettier 简化工具链
- TypeScript 已经提供了类型检查
- Prettier 专注于格式化，配置更简单
- 避免工具冲突和配置冗余

#### 检查流程总结

```
代码提交 → GitHub Actions 触发
    ↓
并行运行：
├─ Backend Check (backend-check.yml)
│  ├─ Pyright 类型检查 (硬性失败)
│  └─ Ruff 代码风格检查 (硬性失败)
└─ Frontend Check (frontend-check.yml)
   ├─ Prettier 格式检查 (硬性失败)
   └─ TypeScript + Vite Build (硬性失败)
    ↓
全部通过 → ✅ PR 可以合并
任一失败 → ❌ 阻断合并，需要修复
```

## 🔗 相关链接

### Issue & PR
- Issue #1: [Implementation Plan: 手动添加受控Agent API端点](https://github.com/swjtu-dev-squad/socitwin/issues/1)
- PR #11: [feat: 实现手动添加受控Agent API端点](https://github.com/swjtu-dev-squad/socitwin/pull/11)
- Issue #12: [[CI/CD] 集成前后端静态检查工作流](https://github.com/swjtu-dev-squad/socitwin/issues/12)
- PR #13: [[CI/CD] 集成前后端静态检查工作流](https://github.com/swjtu-dev-squad/socitwin/pull/13)

### 文档
- [README.md](../README.md) - 项目文档和代码风格指南
- [OASIS LLMs Full Documentation](../docs/oasis-llms-full.txt)

### API 文档
- 本地开发: http://localhost:8000/docs
- Swagger UI 自动生成