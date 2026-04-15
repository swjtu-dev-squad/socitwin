# Dev Meeting 2026年4月12日- 项目重构与工具升级同步

## 📋 会议主题
- 项目架构重构与仓库迁移
- Agent Skills 工具引入与使用指南
---

## 🎯 Action Items & Todo List

### Phase 1: 项目重构与仓库迁移 ✅
- [x] 创建新仓库 `socitwin` (社交孪生)
  - 旧仓库: https://github.com/swjtu-dev-squad/oasis-dashboard
  - 新仓库: https://github.com/swjtu-dev-squad/socitwin
  
- [x] **架构升级完成**
  - ❌ 旧架构: React前端 + Express后端 + Python引擎 + RPC调用
    - 问题: 耦合度高、文件长、维护困难
  - ✅ 新架构: React前端 + FastAPI后端 + 模块化设计
    - 优势: 工程化更清晰、模块解耦、易于维护

### Phase 2: API 文档与端点规范
- [x] **API 文档访问**
  - 本地开发: http://localhost:8000/docs
  
- [x] **API 规范化任务**
  - [x] 确保所有端点都有完整的 OpenAPI 文档
  - [x] 添加请求/响应示例
  - [x] 统一错误码规范
  - [x] 添加 API 版本控制策略

### Phase 3: Agent Skills 工具引入 🚀
- [x] **目标**: 让 vibe coding 也能写出健壮、专业的代码，减少”AI味”
- [x] **已安装 Skills**: 查看 [skills-lock.json](skills-lock.json)

- [x] **Skills 推广与培训**

- [x] **常用 Skills 实践**
  - [x] **代码质量类**
    - [x] `vercel-react-best-practices` - React/Next.js 最佳实践
    - [x] `vercel-composition-patterns` - 组件组合模式
  
  - [x] **UI/UX 类**
    - [x] `ui-ux-pro-max` - UI/UX 设计规范
    - [x] `ckm-ui-styling` - 组件样式规范
    - [x] `web-design-guidelines` - Web 界面规范审查
  
  - [x] **后端开发类**
    - [x] `fastapi-templates` - FastAPI 项目模板
