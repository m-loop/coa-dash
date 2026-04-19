# Test Case Design - COA-dash Dashboard (Web UI)

**Version**: 0.5.5
**Date**: 2026-04-01
**Status**: Superseded for dashboard; see `test-cases-feishu-bridge.md` for bridge tests

> **Note**: This document covers the COA-dash web dashboard UI tests (Agents/Tasks/OpenCode/Config tabs).
> For Feishu bridge E2E tests (commands, card buttons, message forwarding, resilience), see [test-cases-feishu-bridge.md](test-cases-feishu-bridge.md).

---

## 1. 测试范围 (Test Scope)

### 功能测试范围
- OpenCode Tab 功能 (D78-D95)
- Session State 按钮功能 (D72-D77)
- Status Dropdown 功能 (D96)
- Assignee Dropdown 功能 (D97)
- Batch Status Update 功能 (D98)
- Priority Dropdown 功能 (D48)
- Task Card 扩展功能
- Mobile 响应式布局

### 非功能测试范围
- 触摸目标尺寸验证 (44px min)
- 暗色模式 OLED 颜色验证
- 响应式断点测试 (410px / 780px)

### 排除范围
- Statistics 页面 (Phase 2)
- Agent Chat 页面 (Phase 4)
- Cron Jobs 页面 (Phase 2)

---

## 2. 测试类型 (Test Types)

| 类型 | 描述 | 覆盖率目标 |
|------|------|-----------|
| API 测试 | HTTP 端点验证 | 100% |
| E2E 测试 | 用户交互流程 | 核心场景 |
| 响应式测试 | 多视口布局 | 100% |
| 触摸测试 | 触摸目标尺寸 | 100% |

---

## 3. 测试用例列表 (Test Cases)

### TC-001: 页面加载验证

**优先级**: P0

**业务场景**:
- 作为用户
- 我想要打开 COA-dash
- 以便于查看系统状态

**前置条件**:
- COA-dash 服务运行中 (port 8890)
- 数据库存在且有数据

**测试步骤**:
1. 导航到 http://localhost:8890
2. 检查页面标题

**预期结果**:
- 页面标题显示 "COA-dash v0.5.4"
- 底部导航显示 4 个标签: Agents, Tasks, OpenCode, Config
- Session State 按钮显示在顶部栏

**测试数据**:
- 输入: URL http://localhost:8890
- 输出: 页面正常加载

---

### TC-002: Session State 按钮功能

**优先级**: P0

**业务场景**:
- 作为用户
- 我想要查看当前 openclaw session 状态
- 以便于了解 agent 工作状态

**前置条件**:
- session-state.json 文件存在
- 页面已加载

**测试步骤**:
1. 查看顶部栏 Session State 按钮
2. 点击按钮打开 popup
3. 检查 popup 内容
4. 点击 X 关闭 popup

**预期结果**:
- 按钮显示状态图标 (💤/🔄/⏳/❓)
- 点击后显示 popup
- Popup 包含 Agent Status, Model 信息
- 点击 X 后 popup 关闭

**测试数据**:
- 输入: 点击 Session State 按钮
- 输出: Popup 显示状态信息

---

### TC-003: OpenCode Tab 导航

**优先级**: P0

**业务场景**:
- 作为用户
- 我想要切换到 OpenCode 页面
- 以便于查看 OpenCode sessions

**前置条件**:
- 页面已加载
- opencode.db 数据库存在

**测试步骤**:
1. 点击底部导航的 "OpenCode" 标签
2. 检查页面布局

**预期结果**:
- OpenCode 标签高亮显示
- 左侧显示 session 列表
- 右侧显示聊天界面
- 显示项目选择下拉框

**测试数据**:
- 输入: 点击 OpenCode 标签
- 输出: OpenCode 页面显示

---

### TC-004: OpenCode Session 列表

**优先级**: P0

**业务场景**:
- 作为用户
- 我想要查看 OpenCode sessions 列表
- 以便于选择要交互的 session

**前置条件**:
- OpenCode 页面已打开
- opencode.db 有 sessions 数据

**测试步骤**:
1. 查看 session 列表
2. 检查 session 项目显示

**预期结果**:
- 显示 sessions 列表
- 每个 session 显示状态图标 (🔵/🟡/🔴/✅)
- 显示 session 标题
- 显示相对时间

**测试数据**:
- 输入: 打开 OpenCode 页面
- 输出: 显示 sessions 列表 (当前应有 3 个)

---

### TC-005: Tasks 页面优先级下拉

**优先级**: P0

**业务场景**:
- 作为用户
- 我想要修改任务优先级
- 以便于调整任务重要性

**前置条件**:
- Tasks 页面已打开
- 有任务数据

**测试步骤**:
1. 点击任务卡片的优先级徽章 (如 "中 ▾")
2. 选择新优先级 (如 "高")
3. 等待更新完成

**预期结果**:
- 点击后显示下拉菜单
- 菜单显示 4 个选项: 高/中/低/待定
- 选择后优先级更新
- 显示 toast 提示

**测试数据**:
- 输入: 选择 "高" 优先级
- 输出: 任务优先级变为 "高"

---

### TC-006: Tasks 页面状态下拉

**优先级**: P0

**业务场景**:
- 作为用户
- 我想要修改任务状态
- 以便于跟踪任务进度

**前置条件**:
- Tasks 页面已打开
- 有任务数据

**测试步骤**:
1. 点击任务卡片的状态徽章
2. 选择新状态
3. 等待更新完成

**预期结果**:
- 点击后显示下拉菜单
- 菜单显示 4 个选项: 待处理/进行中/已完成/挂起
- 选择后状态更新
- 显示 toast 提示

**测试数据**:
- 输入: 选择 "已完成" 状态
- 输出: 任务状态变为 "已完成"

---

### TC-007: Tasks 页面责任人下拉

**优先级**: P1

**业务场景**:
- 作为用户
- 我想要分配任务责任人
- 以便于明确任务归属

**前置条件**:
- Tasks 页面已打开
- 有任务数据
- /api/assignees 端点正常

**测试步骤**:
1. 点击任务卡片的责任人区域 (如 "@main ▾" 或 "未分配 ▾")
2. 检查下拉菜单
3. 选择新责任人

**预期结果**:
- 点击后显示下拉菜单
- 菜单分三类: 人类/OpenClaw Agent/OpenCode Agent
- 显示颜色编码头像
- 选择后责任人更新

**测试数据**:
- 输入: 选择 "Ricky"
- 输出: 任务责任人变为 "Ricky"

---

### TC-008: Mobile 响应式布局

**优先级**: P0

**业务场景**:
- 作为用户
- 我想要在手机上使用 COA-dash
- 以便于移动办公

**前置条件**:
- 页面已加载

**测试步骤**:
1. 调整视口到 410px 宽度 (Mate X6 folded)
2. 检查布局变化

**预期结果**:
- 左侧边栏隐藏
- 右侧边栏隐藏
- 底部导航始终可见
- OpenCode 页面显示汉堡菜单按钮

**测试数据**:
- 输入: 视口宽度 410px
- 输出: 移动端布局

---

### TC-009: 任务卡片展开/折叠

**优先级**: P1

**业务场景**:
- 作为用户
- 我想要查看任务详情
- 以便于了解任务完整信息

**前置条件**:
- Tasks 页面已打开
- 有父任务和子任务

**测试步骤**:
1. 点击任务卡片
2. 检查展开内容
3. 点击展开按钮查看子任务

**预期结果**:
- 点击卡片后展开详情
- 显示 Assignee, Risk, Notes
- 显示操作按钮
- 有子任务时显示展开按钮

**测试数据**:
- 输入: 点击任务 002
- 输出: 显示任务详情

---

### TC-010: API 端点验证

**优先级**: P0

**业务场景**:
- 作为系统
- 我需要验证所有 API 端点
- 以便于确保数据接口正常

**前置条件**:
- 服务运行中

**测试步骤**:
1. GET /api/agents
2. GET /api/tasks
3. GET /api/sessions
4. GET /api/opencode/projects
5. GET /api/opencode/sessions
6. GET /api/session-state
7. GET /api/assignees

**预期结果**:
- 所有端点返回 HTTP 200
- 返回有效 JSON
- 无 error 字段 (或 error 为空)

**测试数据**:
- 输入: HTTP GET 请求
- 输出: JSON 响应

---

### TC-011: 批量状态更新

**优先级**: P1

**业务场景**:
- 作为用户
- 我想要批量修改任务状态
- 以便于高效管理多任务

**前置条件**:
- Tasks 页面已打开
- 有多个任务

**测试步骤**:
1. 长按任务卡片 (800ms) 进入批量模式
2. 选择多个任务
3. 点击 "修改状态" 按钮
4. 选择新状态

**预期结果**:
- 长按后进入批量选择模式
- 选中的任务显示边框
- 显示批量操作工具栏
- 更新成功后显示 toast

**测试数据**:
- 输入: 选择 2 个任务, 状态改为 "已完成"
- 输出: 2 个任务状态更新

---

## 4. 测试数据设计 (Test Data)

### 正常数据
- 任务数量: 110 个
- Agent 数量: 2 个 (main, coder)
- OpenCode Sessions: 3 个

### 边界数据
- 空任务列表
- 空 sessions 列表
- 超长任务标题 (100+ 字符)

### 异常数据
- 数据库文件不存在
- session-state.json 不存在
- 网络超时

---

## 5. 验收标准 (Acceptance Criteria)

- P0 用例通过率: 100%
- P1 用例通过率: 80%+
- API 端点可用性: 100%
- 触摸目标尺寸: 所有 ≥ 44px
- 页面加载时间: < 2s

---

## Test Execution Summary

| Date | Version | P0 Pass | P1 Pass | Status |
|------|---------|---------|---------|--------|
| 2026-04-01 | 0.5.4 | 7/7 (100%) | 4/4 (100%) | ✅ PASS |

### Test Results

| TC ID | Name | Priority | Status |
|-------|------|----------|--------|
| TC-001 | 页面加载验证 | P0 | ✅ PASS |
| TC-002 | Session State 按钮功能 | P0 | ✅ PASS |
| TC-003 | OpenCode Tab 导航 | P0 | ✅ PASS |
| TC-004 | OpenCode Session 列表 | P0 | ✅ PASS |
| TC-005 | Tasks 页面优先级下拉 | P0 | ✅ PASS |
| TC-006 | Tasks 页面状态下拉 | P0 | ✅ PASS |
| TC-007 | Tasks 页面责任人下拉 | P1 | ✅ PASS |
| TC-008 | Mobile 响应式布局 | P0 | ✅ PASS |
| TC-009 | 任务卡片展开/折叠 | P1 | ✅ PASS |
| TC-010 | API 端点验证 | P0 | ✅ PASS |
| TC-011 | 批量状态更新 | P1 | ✅ PASS |

### Bugs Fixed During Testing

| Bug | Description | Fix |
|-----|-------------|-----|
| #1 | OpenCode sessions not loading | Added async data loading in switchTab() |