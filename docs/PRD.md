# PRD: COA-dash - Agentic Dashboard

**Project**: COA-dash (Command Orchestration Agent Dashboard)  
**Version**: 0.4.4 (UI Refinements + Sessions Expansion)  
**Location**: `/home/aegis/vault/projects/coa-dash/`  
**Port**: 8890  
**Access URL**: http://100.103.186.109:8890 (Tailscale)  
**Design System**: ui-ux-pro-max (Dark Mode OLED)

---

## Vision

The best agentic dashboard - humanity's most efficient HMI for AI agent orchestration

---

## Target Device

**Primary**: Huawei Mate X6 (foldable phone)
- Folded: ~410px × 890px (vertical phone, primary use)
- Unfolded: ~890px × 1780px (expanded view, detail work)

**Design Philosophy**: Mobile-first, touch-first, progressive disclosure
- Vertical phone = compact, one-thumb navigation via bottom nav
- Unfolded = dual sidebar, desktop-like experience, bottom nav still visible

**Target Usage**:
- 10+ times per day (high-frequency tool)
- Quick glance for status (folded)
- Deep interaction for task management (unfolded)

---

## Design Constraints

### Touch-First Principles

| 约束 | 要求 |
|------|------|
| **交互方式** | 触摸屏优先，不使用键盘快捷键 |
| **触摸目标** | 最小 44px × 44px |
| **手势** | 点击/长按，无键盘依赖 |
| **反馈** | 所有操作必须有视觉反馈 |

### Forbidden Patterns

| 禁止 | 原因 |
|------|------|
| ❌ 键盘快捷键 | 触摸屏无键盘 |
| ❌ Hover 效果作为主要交互 | 触摸屏无 hover |
| ❌ 拖拽排序 | 与滚动冲突，误触率高 |
| ❌ 双击操作 | 与单击冲突，易误触 |
| ❌ 长文本输入 | 移动端键盘体验差 |
| ❌ Tab 区域滑动切换 | v0.4.0 移除顶部 Tab |

---

## Core Features

### 1. Agent Overview with Hierarchy Structure
- Live status: online, busy, idle, offline, dead, sick
- Role-based hierarchy: main → coder → opencode → complex-coding → codex
- Last activity time (from sessions)
- Session count and current session ID
- **v0.4.0**: Sorted by lastActivityAt descending (most recent first)
- **v0.4.0**: Session count visible in collapsed card (row 2)

### 2. Task Management (Enhanced)
- Parent-child tasks structure (tree view)
- Priority and status filtering
- One-click priority change
- Push notification to agent for acknowledgement
- Queue jump (work-next) feature
- **v0.4.0**: Priority badge visible in collapsed state (row 2)
- **v0.4.0**: Priority filter buttons (两行布局)
- **v0.4.0**: Priority filter applies only to parent tasks (parentId=null)

### 3. Statistics and Summary (Phase 2)
- Idle ratio and throughput
- Agent utilization metrics

### 4. Agent Chat (Phase 4)
- Direct chat to each agent
- Task integration via chat

### 5. Distribution (Phase 5)
- Installable tool (pip/npm package)
- Standalone app (Electron/Tauri)
- OpenClaw skill for native integration

---

## Architecture Overview

### Data Sources

| Source | Method | Data |
|--------|--------|------|
| Agent Status | `openclaw status --json` | Agent list, heartbeat, sessions |
| Gateway Health | `curl localhost:18789/healthz` | Gateway health status |
| Gateway Ready | `curl localhost:18789/readyz` | Dependency status |
| Tasks | `/home/aegis/vault/tasks/tasks.jsonl` | Task hierarchy |
| Sessions | `~/.openclaw/agents/*/sessions/sessions.json` | Session activity |

### Data Flow

```
1. Browser fetches /api/agents → Python reads sessions.json → sorted by lastActivityAt
2. Browser fetches /api/tasks → Python reads tasks.jsonl
3. User changes priority → Python writes tasks.jsonl
4. Python calls openclaw agent --message → Notifies agent
```

### Status Detection Logic

| Status | Detection | Threshold |
|--------|-----------|-----------|
| ONLINE | enabled=true, heartbeat running | - |
| BUSY | session updatedAt < 30s | 30 seconds |
| IDLE | session updatedAt > 5min, heartbeat running | 5 minutes |
| OFFLINE | enabled=false OR heartbeat not present | - |
| DEAD | /healthz fails OR agent not in status JSON | - |
| SICK | /readyz shows failing deps | - |

---

## Agent Hierarchy Definition

### Role-Based Hierarchy

```
MAIN (Default Agent)
├── CODER (Dev/Coding)
├── OPENCODE (Code Assistant)
├── COMPLEX-CODING (Complex Coding)
└── CODEX (Experimental)
```

---

## Design System (ui-ux-pro-max)

### Visual Style

| Property | Value |
|----------|-------|
| **Pattern** | Minimal Single Column |
| **Style** | Dark Mode (OLED) |
| **Performance** | Excellent (OLED optimized) |
| **Accessibility** | WCAG AAA |

### Color Palette

| Role | Variable | Hex | Usage |
|------|----------|-----|-------|
| Background | `--bg` | `#020617` | Main background (slate-950) |
| Primary | `--primary` | `#0F172A` | Cards, surfaces (slate-900) |
| Secondary | `--secondary` | `#1E293B` | Elevated surfaces (slate-800) |
| Accent | `--accent` | `#22C55E` | Task ID, success, CTA (green-500) |
| Text | `--text` | `#F8FAFC` | Primary text (slate-50) |
| Text Muted | `--text-muted` | `#94A3B8` | Secondary text (slate-400) |
| Border | `--border` | `#334155` | Borders (slate-700) |

### Status Colors

| Status | Hex | Variable | Badge Background |
|--------|-----|----------|------------------|
| Online | `#22C55E` | `--green` | rgba(34, 197, 94, 0.15) |
| Busy | `#FACC15` | `--yellow` | rgba(250, 204, 21, 0.15) |
| Idle | `#6366F1` | `--indigo` | rgba(99, 102, 241, 0.15) |
| Offline | `#64748B` | `--slate` | rgba(100, 116, 139, 0.15) |
| Dead | `#EF4444` | `--red` | rgba(239, 68, 68, 0.15) |
| Sick | `#F97316` | `--orange` | rgba(249, 146, 60, 0.15) |

### Typography

| Element | Font | Weights | Fallback |
|---------|------|---------|----------|
| Headings | Fira Sans | 400-700 | system-ui, sans-serif |
| Body/Code | Fira Code | 400-600 | monospace |

### Font Sizes

| Element | Folded (<780px) | Unfolded (≥780px) |
|---------|-----------------|-------------------|
| Title | 16px | 18px |
| Body | 14px | 15px |
| Label | 12px | 13px |
| Small | 11px | 12px |

### Animation

| Type | Duration | Easing |
|------|----------|--------|
| Fast | 150ms | ease-out |
| Normal | 200ms | ease-out |
| Slow | 300ms | ease-out |

### Layout Variables (v0.4.0)

| Variable | Folded | Unfolded |
|----------|--------|----------|
| `--top-bar-height` | 48px | 56px |
| `--bottom-nav-height` | 56px | 56px |
| `--sidebar-left-width` | 0 (hidden) | 240px |
| `--sidebar-right-width` | 0 (hidden) | 200px |
| `--card-margin` | 8px | 12px |
| `--card-padding` | 12px | 16px |
| `--touch-target` | 44px | 44px |
| `--tabs-height` | 0 (removed) | 0 (removed) |

---

## Mobile-First UI Design

### Device Target Matrix

| Device State | Screen Size | Layout Strategy |
|--------------|-------------|-----------------|
| Mate X6 Folded | ~410px × 890px | Single column, bottom nav only |
| Mate X6 Unfolded | ~890px × 1780px | Dual sidebar + main content + bottom nav |
| Desktop | >1024px | Full layout with dual sidebar + bottom nav |

### Layout Structure

#### Folded Phone (Primary) - v0.4.0

```
+----------------------------------+
|         TOP BAR (48px)           |
|   🦞 COA-dash  ● Gateway OK  [↻] |
+----------------------------------+
|                                  |
|      MAIN CONTENT                |
|      (Scrollable)                |
|      calc(100vh - 104px)         |
|                                  |
|                                  |
+----------------------------------+
|       BOTTOM NAV (56px)          |
|   🏠    📋    📊    💬    ⚙️    |
|  Agents Tasks Stats Chat Config  |
+----------------------------------+

Height: 48px + (100vh - 104px) + 56px = 100vh
Content: ~786px usable on 890px screen
```

**v0.4.0 Changes**:
- ❌ Removed top tabs (saved 44px vertical space)
- ✅ Bottom nav only for navigation
- ❌ No sidebars (not enough width)

#### Unfolded Phone (Secondary) - v0.4.0

```
+----------+-----------------------+----------+
|          |      TOP BAR (56px)   |          |
| LEFT     +-----------------------+ RIGHT    |
| SIDEBAR  |                       | SIDEBAR  |
| (240px)  |    MAIN CONTENT       | (200px)  |
|          |    (Scrollable)       |          |
|          |                       |          |
| Agents   |    ~450px usable      | Stats    |
| Summary  |                       | Summary  |
+----------+-----------------------+----------+
|              BOTTOM NAV (56px)             |
|   🏠    📋    📊    💬    ⚙️               |
|  Agents Tasks Stats Chat Config           |
+-------------------------------------------+

Width: 240px + ~450px + 200px ≈ 890px
Height: 56px + (100vh - 112px) + 56px = 100vh
```

**v0.4.0 Changes**:
- ✅ Added right sidebar (200px) for statistics
- ✅ Bottom nav remains visible (not hidden)
- ✅ Left sidebar: Agent quick list + Task summary
- ✅ Right sidebar: Task statistics + Agent status summary

### Responsive Breakpoints

| Breakpoint | Layout | Left Sidebar | Right Sidebar | Bottom Nav |
|------------|--------|--------------|---------------|------------|
| < 500px | Folded phone | Hidden | Hidden | Visible |
| 500-780px | Transition | Hidden | Hidden | Visible |
| ≥ 780px | Unfolded | Visible (240px) | Visible (200px) | Visible |
| > 1024px | Desktop | Visible (280px) | Visible (220px) | Visible |

---

## Interaction Design

### Touch Interactions

| 交互 | 行为 | 反馈 |
|------|------|------|
| **单击 Card** | 展开/收起详情 | 内容滑入/滑出 |
| **长按 Card** (500ms) | 显示操作菜单 | 菜单弹出 |
| **点击 Bottom Nav** | 切换页面 | Nav 高亮 + 内容切换 |
| **下拉刷新** | 重新加载数据 | Spinner + Toast |
| **点击刷新按钮** | 重新加载数据 | Spinner + Toast |
| **点击优先级按钮** | 直接切换优先级 | Toast "优先级已更新" |
| **点击通知按钮** | 发送通知 | Toast "通知已发送" |
| **点击插队按钮** | 设置为下一个任务 | Toast "已设置为下一个任务" |
| **点击过滤器按钮** | 过滤列表 | 列表立即更新 |

### Long Press Menu (长按菜单)

**触发条件**: 长按 500ms

**Task Card 菜单项**:
- [调整优先级]
- [发送通知]
- [插队处理]

**Agent Card 菜单项**:
- [查看详情]
- [发送消息]

---

## UI Components

### 1. Top Bar (48px folded / 56px unfolded)

```
┌─────────────────────────────────────┐
│ 🦞 COA-dash    ● Gateway OK    [↻] │
└─────────────────────────────────────┘
```

| 元素 | 说明 |
|------|------|
| Logo | "🦞 COA-dash" 左侧 |
| Gateway 状态 | 中间，● 绿色(OK) / ● 红色(离线) |
| 刷新按钮 | 右侧，点击刷新所有数据 |

### 2. Bottom Navigation (v0.4.0 - All Modes)

```
┌─────────────────────────────────────┐
│   🏠    📋    📊    💬    ⚙️       │
│  Agents Tasks Stats Chat Config   │
└─────────────────────────────────────┘
```

| Tab | 状态 | 内容 |
|-----|------|------|
| Agents | ✅ 实现 | Agent 列表 |
| Tasks | ✅ 实现 | Task 列表 + 过滤器 |
| Stats | 占位 | "Coming Soon" |
| Chat | 占位 | "Coming Soon" |
| Config | ✅ 实现 | 只读配置信息 |

**v0.4.0**: Bottom nav is the **sole navigation** in all modes.

### 3. Agent Card (v0.4.0 - Two Row Collapsed)

#### 收起状态 (默认显示)

```
┌─────────────────────────────────────┐
│ main                                │  ← 行1: Agent ID
│      [● Online]  Sessions: 62       │  ← 行2: Status badge + Session count
└─────────────────────────────────────┘
```

| 字段 | 位置 | 说明 |
|------|------|------|
| Agent ID | 行1 左侧 | 粗体，白色 |
| Status Badge | 行2 左侧 | 状态徽章，带背景色 |
| Session Count | 行2 右侧 | "Sessions: N"，灰色小字 |

#### 展开状态 (单击后显示)

```
┌─────────────────────────────────────┐
│ main                                │
│      [● Online]  Sessions: 62       │
├─────────────────────────────────────┤
│ Model: qwen3.5-plus                 │
│ Current: 99278de5-03b3-...         │
│ Last Activity: 5 min ago           │
│ Enabled: ✅                         │
└─────────────────────────────────────┘
```

### 4. Task Card (v0.4.0 - Two Row Collapsed)

#### 收起状态 (默认显示)

```
┌─────────────────────────────────────┐
│ 001  创建待办系统                   │  ← 行1: Task ID (绿色) + 标题
│      [已完成] [中]                  │  ← 行2: Status + Priority badges
└─────────────────────────────────────┘
```

| 字段 | 位置 | 说明 |
|------|------|------|
| Task ID | 行1 左侧 | 粗体，绿色 (`--accent`) |
| Title | 行1 紧跟 ID | 白色，标题文本 |
| Status Badge | 行2 左侧 | 状态徽章 |
| Priority Badge | 行2 右侧 | 优先级徽章 (**v0.4.0 始终可见**) |

#### 展开状态 (单击后显示)

```
┌─────────────────────────────────────┐
│ 001  创建待办系统                   │
│      [已完成] [中]                  │
├─────────────────────────────────────┤
│ Assignee: Ricky                     │
│ Risk: 高                            │
│ Notes: 目标实现...                  │
├─────────────────────────────────────┤
│ Priority: [低] [中] [高]            │
│ Actions:  [🔔 通知] [▶ 插队]        │
└─────────────────────────────────────┘
```

### 5. Filter Bar (v0.4.0 - Two Rows)

```
┌───────────────────────────────────────────────────┐
│ [All] [进行中] [待处理] [已完成] [挂起]            │  ← Row 1: Status filters
│ Priority: [All] [高] [中] [低] [待定]              │  ← Row 2: Priority filters
└───────────────────────────────────────────────────┘
```

**v0.4.0 过滤逻辑**:

| 过滤器 | 作用范围 | 逻辑 |
|--------|----------|------|
| Status | 所有任务 | 匹配所有 task.status (父 + 子) |
| Priority | 仅父任务 | 只匹配 parentId === null 的 task.priority |
| 组合 | AND 逻辑 | Status AND Priority 同时生效 |

**Priority 过滤规则 (D39)**:
- 父任务匹配 → 显示父任务 + 所有子任务
- 父任务不匹配 → 隐藏父任务 + 所有子任务
- 子任务的 priority 不影响可见性

### 6. Left Sidebar (Unfolded ≥780px)

```
┌────────────────────┐
│ AGENTS             │  ← Section title
│ ├─ main   [●]      │  ← Sorted by activity
│ ├─ coder  [●]      │
│ ├─ complex [○]     │
│ ├─ opencode [○]    │  ← Never used, at bottom
│ ├─ codex  [○]      │
│ └─ acp-cc  [○]     │
├────────────────────┤
│ TASK SUMMARY       │
│ Total: 87          │
│ Pending: 15        │
│ In Progress: 6     │
│ Completed: 61      │
│ Blocked: 5         │
└────────────────────┘
```

**v0.4.0 Agent 排序 (D40)**: 按 `lastActivityAt` 降序
- 最活跃在前 (最近有 session)
- 未使用在底 (sessionCount=0, lastActivityAgo="never")

### 7. Right Sidebar (v0.4.0 - Unfolded ≥780px)

```
┌────────────────────┐
│ TASK STATISTICS    │
│ ├─ Total: 87       │
│ ├─ Completed: 61   │
│ ├─ Pending: 15     │
│ ├─ In Progress: 6  │
│ └─ Blocked: 5      │
├────────────────────┤
│ AGENT STATUS       │
│ ├─ Online: 2       │
│ ├─ Busy: 1         │
│ ├─ Idle: 0         │
│ └─ Offline: 3      │
└────────────────────┘
```

**v0.4.0 (D36)**: 右侧栏仅统计数据，不包含过滤器。

### 8. Toast

```
┌──────────────────────────┐
│      优先级已更新        │
└──────────────────────────┘
         ↑ 底部居中 (距底部 80px)
```

| 属性 | 值 |
|------|---|
| 位置 | 底部居中，距底部 80px (避开 bottom nav) |
| 背景 | rgba(0, 0, 0, 0.85) |
| 文字 | 白色，14px |
| 圆角 | 8px |
| 时长 | 2 秒后自动消失 |
| 动画 | fade-in 200ms, fade-out 150ms |

### 9. Loading States

#### Skeleton Screen (首次加载)

```
┌─────────────────────────────────────┐
│ ████████████████████                │  ← Row 1 skeleton
│ ███████████████████████████████████ │  ← Row 2 skeleton
└─────────────────────────────────────┘
```

- 灰色条块，pulse 动画
- 替代 Card 占位，提升感知性能

#### Spinner (操作等待)

- 刷新按钮旋转动画 (1s linear infinite)
- 按钮内小型 spinner

### 10. Empty States

```
┌─────────────────────────────────────┐
│                                     │
│           📭                        │
│      未找到匹配的任务               │
│                                     │
└─────────────────────────────────────┘
```

| 场景 | 图标 | 文案 |
|------|------|------|
| 无任务 | 📭 | 暂无任务 |
| 无 Agent | 🤖 | 无可用 Agent |
| 过滤无结果 | 🔍 | 未找到匹配的任务 |

### 11. Error Banner

```
┌─────────────────────────────────────┐
│ ⚠️ Gateway 离线，部分功能不可用     │
└─────────────────────────────────────┘
         ↑ 固定在 Top Bar 下方
```

- 红色背景 (rgba(239, 68, 68, 0.9))
- 固定在 Top Bar 下方
- 可点击关闭

### 12. Coming Soon Page

```
┌─────────────────────────────────────┐
│                                     │
│           🚧                        │
│      Coming Soon                    │
│                                     │
│   此功能将在下一版本中推出          │
│                                     │
└─────────────────────────────────────┘
```

---

## API Specification

### GET /api/agents

**v0.4.0**: Agents sorted by `lastActivityAt` descending.  
**v0.4.1**: Added `lastChannel` and `currentActivity` fields (D53).  
**v0.4.2**: Agent list from openclaw.json config, 60s cache, `?force=true` bypass.

**Query Parameters:**
- `force`: If `true`, bypass cache and re-read openclaw.json (D61)

**Data Source:** `~/.openclaw/openclaw.json` → `agents.list` (D55)

**Cache Strategy:**
- openclaw.json: 60s lazy cache (D56)
- sessions.json: Fresh read every request

**Response:**
```json
{
  "agents": [
    {
      "id": "main",
      "displayName": "Main",
      "status": "online",
      "enabled": true,
      "lastActivityAt": 1774929862781,
      "lastActivityAgo": "5 min ago",
      "model": "qwen3.5-plus",
      "sessionCount": 62,
      "currentSessionId": "99278de5-03b3-4503-b746-1ad171908c02",
      "lastChannel": "feishu",
      "currentActivity": "在飞书对话"
    },
    {
      "id": "coder",
      "displayName": "Coder",
      "status": "idle",
      "enabled": true,
      "lastActivityAt": 1774900000000,
      "lastActivityAgo": "1 hr ago",
      "model": "qwen3.5-plus",
      "sessionCount": 41,
      "currentSessionId": "",
      "lastChannel": "webchat",
      "currentActivity": "在 WebChat"
    }
  ],
  "gateway": {
    "healthy": true,
    "activeAgents": 2,
    "lastChecked": 1774929900000
  },
  "meta": {
    "configSource": "openclaw.json",
    "agentCount": 2,
    "cached": false
  },
  "error": null
}
```

**Error Response** (openclaw.json not found):
```json
{
  "agents": [],
  "gateway": { "healthy": false, "activeAgents": 0 },
  "meta": { "configSource": null, "agentCount": 0, "cached": false },
  "error": "openclaw.json not found"
}
```

**排序结果**: main → coder (只显示配置的 agent，废弃 agent 不显示)

### GET /api/gateway/status

**Response:**
```json
{
  "healthy": true,
  "ready": true,
  "healthz": {
    "status": "ok",
    "timestamp": 1774929900000
  },
  "readyz": {
    "status": "ok",
    "checks": []
  }
}
```

### GET /api/tasks

**Query Parameters:**
- `status`: Filter by status (已完成, 待处理, 进行中, 挂起) - applies to all tasks
- `priority`: Filter by priority (高, 中, 低, 待定) - **v0.4.0**: only applies to parent tasks (parentId=null)
- `search`: Search in title/notes

**Response:**
```json
{
  "tasks": [
    {
      "taskId": "001",
      "title": "创建待办系统",
      "status": "已完成",
      "priority": "中",
      "assignee": "Ricky",
      "parentId": null,
      "level": "L1",
      "riskLevel": "高",
      "notes": "目标实现...",
      "children": [
        {
          "taskId": "001-01",
          "title": "子任务",
          "status": "待处理",
          "priority": "高",
          "parentId": "001"
        }
      ]
    }
  ],
  "stats": {
    "total": 87,
    "completed": 61,
    "pending": 15,
    "inProgress": 6,
    "blocked": 5
  }
}
```

### PUT /api/tasks/:id/priority

**Request:**
```json
{
  "priority": "高"
}
```

**Response:**
```json
{
  "success": true,
  "task": {
    "taskId": "001",
    "priority": "高"
  }
}
```

### POST /api/tasks/:id/notify

**Request:**
```json
{
  "agentId": "main",
  "type": "PRIORITY_UP"
}
```

**Response:**
```json
{
  "success": true,
  "message": "通知已发送"
}
```

> **⚠️ Known Issue (D80)**: The notification bell button (🔔) currently shows "发送失败" on some systems. Requires debugging openclaw CLI path/config. Planned fix for v0.5.0. The openclaw CLI exists but the notification delivery may fail due to channel/config issues.

### POST /api/tasks/:id/work-next

**Request:**
```json
{
  "agentId": "main"
}
```

**Response:**
```json
{
  "success": true,
  "message": "已设置为下一个任务"
}
```

### GET /api/config

**Response:**
```json
{
  "dashboard": {
    "name": "COA-dash",
    "port": 8890,
    "refreshInterval": 60
  },
  "gateway": {
    "port": 18789,
    "healthy": true
  },
  "status": {
    "busyThresholdSeconds": 30,
    "idleThresholdMinutes": 5
  }
}
```

---

## Error Handling

### Error Types

| 场景 | 处理 | UI 反馈 |
|------|------|---------|
| Gateway 离线 | 显示离线状态 | Error Banner + 状态变红 |
| tasks.jsonl 读取失败 | 返回空列表 | Toast "无法读取任务列表" |
| openclaw CLI 不可用 | 使用备用数据源 | 从 sessions.json 解析 |
| 通知发送失败 | 返回 error | Toast "发送失败" |
| 优先级更新失败 | 返回 error | Toast "更新失败" |

### Fallback Strategy

```
Priority 1: openclaw status --json
       ↓ (失败)
Priority 2: ~/.openclaw/agents/*/sessions/sessions.json
       ↓ (失败)
Priority 3: Gateway health check only
```

---

## Implementation Phases

### Phase 1: MVP (v0.3.0) - ✅ Complete

| 功能 | 状态 |
|------|------|
| Agent List Page | ✅ |
| Task Management Page | ✅ |
| Agent Notification | ✅ |
| systemd service | ✅ |
| Top tabs (44px) | ✅ (will be removed in v0.4.0) |

### Phase 1.5: UI Enhancements (v0.4.0) - 📝 Pending Implementation

| 功能 | 状态 | 决策 ID |
|------|------|----------|
| Remove top tabs | 📝 | D42 |
| Bottom nav in ALL modes | 📝 | D35 |
| Right sidebar (statistics) | 📝 | D36, D41 |
| Priority badge in collapsed cards | 📝 | D37 |
| Two-row filter layout | 📝 | D38 |
| Priority filter parent-only logic | 📝 | D39 |
| Agent sort by lastActivityAt | 📝 | D40 |
| Card two-row collapsed layout | 📝 | D37 |

### Phase 2: Enhanced (Future)

| 功能 | 状态 |
|------|------|
| Statistics Page (detailed) | 📅 |
| WebSocket Integration | 📅 |
| Agent utilization metrics | 📅 |

### Phase 3: Advanced (Future)

| 功能 | 状态 |
|------|------|
| Live Status Refinement | 📅 |
| Session Details View | 📅 |
| Activity Timeline | 📅 |

### Phase 4: Chat (Future)

| 功能 | 状态 |
|------|------|
| Agent Chat Backend | 📅 |
| Chat Frontend | 📅 |

### Phase 5: Distribution (Future)

| 功能 | 状态 |
|------|------|
| pip/npm package | 📅 |
| Standalone app | 📅 |
| OpenClaw skill | 📅 |

---

## Configuration File

**Location**: `config/config.json`

```json
{
  "dashboard": {
    "name": "COA-dash",
    "emoji": "🦞",
    "port": 8890,
    "host": "127.0.0.1",
    "refreshInterval": 60
  },
  "gateway": {
    "port": 18789,
    "token": "10045d1aa3d9cd254674814105ec9236eb781fce11969d61"
  },
  "tasks": {
    "path": "/home/aegis/vault/tasks/tasks.jsonl",
    "defaultAgent": "main"
  },
  "status": {
    "busyThresholdSeconds": 30,
    "idleThresholdMinutes": 5
  },
  "agents": {
    "hierarchy": {
      "main": ["coder", "opencode", "complex-coding", "codex"]
    }
  },
  "ui": {
    "theme": "dark-oled",
    "fonts": {
      "heading": "Fira Sans",
      "body": "Fira Code"
    }
  }
}
```

---

## Design Decisions Log

### v0.3.0 Decisions (MVP)

| ID | Decision | Reason |
|----|----------|--------|
| D1 | Fixed Top Bar (48px) | Always visible context |
| D2 | Full-Width Cards | Easy to scan, tap-friendly |
| D3 | Fixed Bottom Nav (56px) | Thumb-friendly |
| D4 | No Sidebar (Folded) | 410px cannot fit sidebar |
| D5 | Touch Gestures Only | Touch-first, no keyboard |
| D6 | Compact Fonts | Readable on small screen |
| D7 | Sidebar on Unfolded | 890px supports sidebar |
| D8 | Python + HTML | Simple, maintainable |
| D9 | Role-Based Agent Hierarchy | main → coder structure |
| D10 | Arbitrary Status Thresholds | No native status from OpenClaw |
| D11 | Push Notification via CLI | MVP uses openclaw agent --message |
| D12 | Dark Mode OLED | Eye-friendly, power efficient |
| D13 | Fira Fonts | Technical/dashboard aesthetic |
| D14 | Green Accent | Task ID, status indicators, CTA |
| D15 | 200ms Transitions | Smooth, responsive |
| D16 | 44px Touch Targets | Accessibility standard |
| D17 | Single Tap to Expand | Simple, discoverable |
| D18 | Long Press for Actions | Power user feature |
| D19 | Button-based Priority | Drag conflicts with scroll |
| D20 | Toast Feedback | Visual confirmation |
| D21 | Skeleton Loading | Better perceived performance |
| D22 | Error Banner | Gateway status visibility |
| D23 | 6 Status Colors | Complete status distinction |

### v0.4.0 Decisions (UI Enhancements)

| ID | Decision | Reason |
|----|----------|--------|
| **D35** | Bottom Nav in ALL modes | Navigation consistency; no learning curve when switching folded/unfolded; thumb-friendly in both modes |
| **D36** | Right Sidebar = Statistics only | Avoid duplicate filters; statistics as dashboard overview; keep sidebar focused |
| **D37** | Card collapsed = two rows | Row1: ID+title, Row2: badges; solves long title overflow; unified layout for Agent/Task |
| **D38** | Filter bar = two rows | Status row + Priority row; 10 buttons need space on 410px; clear visual separation |
| **D39** | Priority filter = parent-only | Logical hierarchy filtering; children follow parent visibility; matches task tree mental model |
| **D40** | Agent sort = lastActivityAt desc | Most relevant agents first; unused naturally at bottom; no extra UI needed |
| **D41** | Right sidebar width = 200px | Fits ~890px unfolded screen; 240+auto+200 ≈ 890; balanced layout |
| **D42** | Remove top tabs | Redundant with bottom nav; saves 44px vertical space; simplifies navigation |

### v0.4.1 Decisions (UI Refinements)

| ID | Decision | Reason |
|----|----------|--------|
| **D47** | Subtasks collapsed by default | Reduces clutter; parent tasks are focus; user chooses to drill down |
| **D48** | Priority dropdown from badge | Cleaner UI; standard touch pattern; shows current priority |
| **D49** | Gateway shows active agents | "Offline" misleading when sessions.json works; show "N agents active" |
| **D50** | Agent shows last active | Activity recency is key for agent usefulness |
| **D51** | Task shows owner | Ownership critical for task management |
| **D52** | Session count → last activity | Total count not actionable; last activity more useful |

---

## Success Criteria

### Phase 1 MVP (v0.3.0) - ✅ Complete

- [x] Dashboard running on port 8890
- [x] Agent list with status displayed
- [x] Task tree with priority control
- [x] Agent notification working
- [x] Touch interactions working (tap, long-press)
- [x] Toast feedback showing
- [x] Error states handling
- [x] systemd service running

### Phase 1.5 UI Enhancements (v0.4.0) - ✅ Complete

- [x] Top tabs removed from CSS and HTML
- [x] Bottom nav visible in folded AND unfolded modes
- [x] Right sidebar (200px) showing task stats + agent status summary
- [x] Task cards: priority badge in row 2 of collapsed state
- [x] Agent cards: session count in row 2 of collapsed state
- [x] Two-row filter layout (Status row + Priority row with "Priority:" label)
- [x] Priority filter only affects parent tasks (parentId=null check)
- [x] Agents sorted by lastActivityAt descending

### Phase 1.6 UI Refinements (v0.4.1) - 📝 Pending

- [ ] Subtasks collapsed by default, expand button on parent (D47)
- [ ] Priority dropdown on badge tap (D48)
- [ ] Gateway status shows "N agents active" (D49)
- [ ] Agent card shows "Last: X min ago" in collapsed (D50)
- [ ] Task card shows owner in collapsed (D51)
- [ ] Replace "Sessions: N" with "Last: X min ago" (D52)

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-03-31 | Initial PRD |
| 0.2.0 | 2026-03-31 | Added ui-ux-pro-max design system |
| 0.3.0 | 2026-03-31 | Complete touch-first interaction design, API specs, UI components, MVP implementation |
| 0.4.0 | 2026-03-31 | UI enhancements: remove top tabs (D42), bottom nav all modes (D35), dual sidebar (D36/D41), priority visible (D37), two-row filters (D38), parent-only priority filter (D39), agent sorting (D40) |
| 0.4.1 | 2026-03-31 | UI refinements: subtasks collapsed (D47), priority dropdown (D48), gateway shows active agents (D49), agent last active (D50), task owner in collapsed (D51), session→activity (D52) |

**END OF PRD**