# COA-dash Design Decisions Log

This document records every design decision made for COA-dash, including reasoning and trade-offs.

**Version**: 0.4.1  
**Last Updated**: 2026-03-31

---

## Touch-First Constraints (D1-D6)

### D1: No Keyboard Shortcuts
- **Decision**: All interactions via touch, no keyboard shortcuts
- **Reason**: Primary device is touch-screen phone
- **Trade-off**: Power users may prefer keyboard efficiency
- **Implementation**: No keydown/keyup handlers for shortcuts

### D2: 44px Minimum Touch Targets
- **Decision**: All interactive elements minimum 44px × 44px
- **Reason**: Accessibility standard, prevents mis-taps
- **Trade-off**: Slightly larger UI elements
- **Implementation**: min-height/min-width: 44px on buttons, nav items

### D3: No Drag-and-Drop
- **Decision**: Use buttons instead of drag for reordering
- **Reason**: Drag conflicts with scroll on touch screens
- **Trade-off**: Less "natural" than drag gesture
- **Mitigation**: Priority buttons [低][中][高] for quick change

### D4: No Hover-Dependent Interactions
- **Decision**: All features accessible without hover
- **Reason**: Touch screens have no hover state
- **Trade-off**: Cannot use hover previews
- **Implementation**: Use tap/long-press instead

### D5: No Double-Tap
- **Decision**: Avoid double-tap gestures
- **Reason**: Conflicts with single-tap, high error rate
- **Trade-off**: One less gesture available
- **Alternative**: Long-press for secondary actions

### D6: Minimal Text Input
- **Decision**: Avoid text input fields where possible
- **Reason**: Mobile keyboard experience is poor
- **Trade-off**: Less search flexibility
- **Mitigation**: Predefined filters + simple search

---

## Mobile-First Layout (D7-D14)

### D7: Fixed Top Bar (48px height)
- **Decision**: Always-visible header with logo, gateway status, refresh
- **Reason**: Users need gateway status context at all times
- **Trade-off**: Takes 48px of vertical space
- **Folded Mode**: Height 48px
- **Unfolded Mode**: Height 56px

### D8: ~~Tabs with Click + Swipe~~ REMOVED in v0.4.0
- **Original Decision**: Tabs for navigation with click + swipe support
- **v0.4.0 Change**: **Removed entirely** (see D46)
- **Reason for Removal**: Redundant with bottom nav, saves 44px vertical space
- **New Navigation**: Bottom nav only (see D39)

### D9: Full-Width Cards
- **Decision**: Each agent/task displayed as full-width card
- **Reason**: Easy to scan, tap-friendly, maximizes use of narrow screen
- **Trade-off**: More vertical scrolling required
- **Folded Mode**: Width 100%, margin 8px, padding 12px
- **Unfolded Mode**: Width ~450px (with sidebars), margin 12px, padding 16px

### D10: Fixed Bottom Nav (56px height) - UPDATED in v0.4.0
- **Decision**: 5-icon bottom navigation bar, visible in ALL modes
- **Reason**: Thumb-friendly, always accessible, navigation consistency
- **Trade-off**: Takes 56px of vertical space
- **Icons**: Agents / Tasks / Stats / Chat / Config
- **v0.4.0 Change**: No longer hidden in unfolded mode (see D39)
- **Rationale**: Unfolded mode still benefits from consistent thumb-friendly navigation

### D11: No Sidebar (Folded Mode)
- **Decision**: Single-column layout on folded phone
- **Reason**: 410px width cannot fit sidebar + content
- **Trade-off**: More navigation clicks required
- **Mitigation**: Bottom nav + swipeable content

### D12: Dual Sidebar on Unfolded (240px + 200px) - UPDATED in v0.4.0
- **Decision**: Left + Right sidebars visible when unfolded (≥780px)
- **Reason**: Wider screen can show persistent info + statistics
- **Trade-off**: Sidebars take space from main content
- **Left Sidebar**: Agent quick-list + task summary
- **Right Sidebar (v0.4.0)**: Task statistics + agent status summary
- **v0.4.0 Change**: Added right sidebar (see D40, D45)

### D13: Responsive Breakpoints
- **Decision**: Two main breakpoints: <780px, ≥780px
- **Reason**: Clear separation between folded/unfolded states
- **Trade-off**: Less granular than 3+ breakpoints
- **Mapping**:
  - < 780px: Folded phone (Mate X6 folded)
  - ≥ 780px: Unfolded (Mate X6 unfolded + desktop)

### D14: Compact Font Sizes (Folded)
- **Decision**: Title 16px, Body 14px, Label 12px, Small 11px
- **Reason**: Readable on small screen without zooming
- **Trade-off**: Smaller than ideal for some users
- **Unfolded Mode**: +1-2px for each size

---

## Card Interaction (D15-D22)

### D15: Single Tap to Expand/Collapse
- **Decision**: Tap anywhere on card to toggle expanded state
- **Reason**: Simple, discoverable interaction
- **Trade-off**: Cannot have clickable elements in collapsed state (except badges)
- **Mitigation**: Action buttons only in expanded state

### D16: Long Press for Action Menu
- **Decision**: Long press (500ms) shows action menu
- **Reason**: Secondary actions without cluttering UI
- **Trade-off**: Hidden feature, may not be discovered
- **Mitigation**: No critical actions require long-press

### D17: Action Buttons in Expanded State Only
- **Decision**: [低][中][高], [🔔], [▶] buttons only visible when expanded
- **Reason**: Prevents accidental taps, cleaner collapsed view
- **Trade-off**: One extra tap to access actions
- **Implementation**: Buttons in .card-footer, hidden when collapsed

### D18: Priority via Buttons, Not Drag
- **Decision**: Use [低][中][高] buttons for priority change
- **Reason**: Drag conflicts with scroll on touch screens
- **Trade-off**: Less "natural" than drag reorder
- **Implementation**: Three separate buttons, tap to change

### D19: Toast for Action Feedback
- **Decision**: Show toast message after actions
- **Reason**: User needs confirmation that action succeeded
- **Trade-off**: Extra UI element to manage
- **Implementation**: Bottom-center toast, 2s auto-dismiss

### D20: No Confirmation Dialogs
- **Decision**: Actions execute immediately, toast shows result
- **Reason**: Confirmation dialogs disrupt mobile flow
- **Trade-off**: Cannot undo accidental taps
- **Mitigation**: Toast allows retry on failure

### D21: Skeleton Screen for Initial Load
- **Decision**: Show skeleton placeholders while loading
- **Reason**: Better perceived performance than blank screen
- **Trade-off**: More complex loading logic
- **Implementation**: Gray animated bars matching card structure

### D22: Spinner for Actions
- **Decision**: Show spinner on button during action
- **Reason**: Feedback that action is in progress
- **Trade-off**: Button temporarily disabled
- **Implementation**: Replace button content with spinner

---

## Visual Design (D23-D31)

### D23: Dark Mode OLED Color Scheme
- **Decision**: Use #020617 (slate-950) as main background
- **Reason**: Eye-friendly, OLED power efficient
- **Trade-off**: Not suitable for bright environments
- **Colors**: Background #020617, Primary #0F172A, Secondary #1E293B

### D24: Green Accent for Positive Actions
- **Decision**: Use #22C55E (green-500) as primary accent
- **Reason**: Positive connotation for "online/success" states
- **Trade-off**: Different from typical blue/purple dashboards
- **Usage**: Task ID, CTA buttons, online status, success toasts

### D25: 6 Status Colors
- **Decision**: Distinct color for each status
- **Reason**: Clear visual distinction between states
- **Trade-off**: More colors to learn
- **Colors**: Online(green), Busy(yellow), Idle(indigo), Offline(slate), Dead(red), Sick(orange)

### D26: Fira Code / Fira Sans Typography
- **Decision**: Fira Code for body, Fira Sans for headings
- **Reason**: Technical/dashboard aesthetic, excellent readability
- **Trade-off**: External font dependency (Google Fonts)
- **Fallback**: system-ui, monospace

### D27: 200ms Default Transition
- **Decision**: Use 200ms ease-out as default transition
- **Reason**: Smooth, responsive feel without lag
- **Trade-off**: Slightly slower than instant
- **Values**: Fast 150ms, Normal 200ms, Slow 300ms

### D28: Minimal Glow Effect
- **Decision**: Subtle text-shadow on status indicators
- **Reason**: Visual polish, draws attention to status
- **CSS**: text-shadow: 0 0 10px rgba(34, 197, 94, 0.3)
- **Trade-off**: Minor performance cost (negligible)

### D29: prefers-reduced-motion Support
- **Decision**: Respect user's motion preferences
- **Reason**: Accessibility requirement, motion sickness prevention
- **CSS**: @media (prefers-reduced-motion: reduce)
- **Trade-off**: Less polished animation for some users

### D30: Error Banner for Gateway Offline
- **Decision**: Show persistent banner when gateway offline
- **Reason**: Critical status needs visibility
- **Trade-off**: Takes screen space
- **Implementation**: Fixed below top bar, red background

### D31: Coming Soon Placeholder
- **Decision**: Stats/Chat tabs show "Coming Soon" page
- **Reason**: Clear communication about feature availability
- **Trade-off**: Dead-end UI
- **Implementation**: Center icon + text + description

---

## Data & API (D32-D38)

### D32: Fallback Data Sources
- **Decision**: Multiple data source priority
- **Reason**: Graceful degradation when openclaw CLI unavailable
- **Priority**: openclaw status → sessions.json → gateway health only
- **Trade-off**: May have stale data

### D33: 60s Auto-Refresh
- **Decision**: Auto-refresh data every 60 seconds
- **Reason**: Balance between freshness and performance
- **Trade-off**: May miss rapid changes
- **Mitigation**: Manual refresh button

### D34: Read-Only Config Page
- **Decision**: Config tab shows settings, no editing
- **Reason**: Prevent accidental misconfiguration
- **Trade-off**: Requires config file edit for changes
- **Future**: Phase 2 may add editing

### D35: Task Stats in API Response
- **Decision**: Include stats object in /api/tasks response
- **Reason**: Avoid extra API call
- **Trade-off**: Slightly larger response
- **Stats**: total, completed, pending, inProgress, blocked

### D36: Error Field in All Responses
- **Decision**: Every API response includes `error` field
- **Reason**: Consistent error handling
- **Trade-off**: Extra field when successful
- **Implementation**: `error: null` on success

### D37: Notification via openclaw CLI
- **Decision**: Use `openclaw agent --message` for notifications
- **Reason**: Direct integration with user's existing setup
- **Trade-off**: Requires CLI available
- **Fallback**: Show error toast if CLI unavailable

### D38: Task Write Directly to JSONL
- **Decision**: Priority/status changes write directly to tasks.jsonl
- **Reason**: Single source of truth
- **Trade-off**: No transaction/rollback
- **Mitigation**: Backup before write, error handling

---

## v0.4.0 UI Enhancements (D39-D46)

### D39: Bottom Nav in ALL Modes
- **Decision**: Bottom navigation visible in both folded and unfolded modes
- **Reason**: Navigation consistency; no learning curve when switching modes; thumb-friendly in both
- **Trade-off**: Takes 56px vertical space in unfolded mode
- **Previous Behavior**: Hidden in unfolded mode (sidebar assumed navigation)
- **Implementation**: Remove `@media .bottom-nav { display: none }` CSS rule
- **Impact**: Unfolded layout: 240px left + auto main + 200px right + 56px bottom nav

### D40: Right Sidebar = Statistics Only
- **Decision**: Right sidebar contains only statistics, no filters
- **Reason**: Avoid duplicate filters (main content already has filter bar); statistics as dashboard overview
- **Trade-off**: Less interactive right sidebar
- **Contents**:
  - Task Statistics: total, completed, pending, inProgress, blocked
  - Agent Status Summary: online, busy, idle, offline counts
- **Implementation**: Static display, updates with data refresh

### D41: Card Collapsed = Two Rows
- **Decision**: Collapsed card shows info in two rows
- **Reason**: Solves long title overflow; unified layout for Agent/Task; all key info visible
- **Trade-off**: Taller collapsed cards (~60px vs ~44px)
- **Layout**:
  - Row 1: ID (green, bold) + Title/Name
  - Row 2: Status badge + Priority/Session badge
- **Implementation**: CSS flexbox with flex-wrap or explicit two div rows

### D42: Filter Bar = Two Rows
- **Decision**: Status filters on row 1, Priority filters on row 2
- **Reason**: 10 filter buttons need space on 410px screen; clear visual separation between filter types
- **Trade-off**: Takes more vertical space (~72px vs ~44px)
- **Layout**:
  - Row 1: `[All] [进行中] [待处理] [已完成] [挂起]`
  - Row 2: `Priority: [All] [高] [中] [低] [待定]`
- **Implementation**: Two `.filter-bar-row` divs or flex-wrap with visual separator

### D43: Priority Filter = Parent-Only
- **Decision**: Priority filter only applies to tasks with parentId=null
- **Reason**: Logical hierarchy filtering; children follow parent visibility; matches task tree mental model
- **Trade-off**: Cannot filter children independently
- **Logic**:
  - Parent matches filter → Show parent + all children
  - Parent doesn't match → Hide parent + all children
  - Children's priority ignored for filtering
- **Implementation**: Check `task.parentId === null` before matching priority filter

### D44: Agent Sort = lastActivityAt Descending
- **Decision**: Agents sorted by most recent activity first
- **Reason**: Most relevant agents at top; unused agents naturally at bottom; no extra UI needed
- **Trade-off**: Static sort, user cannot reorder
- **Sort Key**: `lastActivityAt` (timestamp, null = never)
- **Order**: Descending (newest first, null/never last)
- **Implementation**: `agents.sort((a, b) => (b.lastActivityAt || 0) - (a.lastActivityAt || 0))`

### D45: Right Sidebar Width = 200px
- **Decision**: Right sidebar fixed at 200px width
- **Reason**: Fits ~890px unfolded screen; 240px left + ~450px main + 200px right ≈ 890px; balanced layout
- **Trade-off**: Less space for main content on narrow unfolded screens
- **CSS**: `--sidebar-right-width: 200px`
- **Responsive**: Hidden below 780px breakpoint

### D46: Remove Top Tabs
- **Decision**: Remove top tabs section entirely (44px saved)
- **Reason**: Redundant with bottom nav; bottom nav provides all navigation needed; saves vertical space
- **Trade-off**: Lost horizontal swipe gesture for tab switching (not critical)
- **Implementation**:
  - Delete `.tabs` CSS and HTML
  - Delete `--tabs-height` variable (set to 0)
  - Update `main-content` height calc: `100vh - 48px - 56px = 100vh - 104px`
  - Remove tab swipe handler JavaScript

---

## v0.4.1 UI Refinements (D47-D54)

### D47: Subtasks Collapsed by Default
- **Decision**: Child tasks hidden by default, expand button on parent to show
- **User Feedback**: "tasks默认子任务收起"
- **Reason**: Reduces visual clutter; parent tasks are primary focus; user chooses to drill down
- **Trade-off**: Extra tap to see subtasks
- **Implementation**:
  - Add expand/collapse button (▼/▶) on parent task cards
  - Subtasks container starts with `display: none`
  - Toggle visibility on button tap

### D48: Priority Dropdown Instead of Inline Buttons
- **Decision**: Click priority badge to show dropdown menu; remove inline [低][中][高] buttons
- **User Feedback**: "task展开式优先级平铺好几个，并且不显示当前优先级，交互非常奇怪"
- **Reason**: Cleaner UI; standard touch pattern; shows current priority clearly
- **Trade-off**: Two taps to change priority (tap badge → tap option)
- **Implementation**:
  - Priority badge becomes tappable
  - Dropdown appears on tap with options: 高/中/低/待定
  - Current priority highlighted in dropdown
  - Toast confirms: "优先级已更新为 高"

### D49: Gateway Status Shows Active Agents
- **Decision**: Show "N agents active" when sessions.json is readable, not "Offline"
- **User Feedback**: "gateway session 显然是live的，你是不是用 gateway status更好？"
- **Reason**: If sessions.json has data, gateway is functioning; "Offline" is misleading
- **Trade-off**: Less precise than actual health check endpoint
- **Implementation**:
  - Backend: If `sessions.json` returns agents, set `gateway.healthy = true`
  - Frontend: Show "N agents active" or "Gateway OK"
  - Top bar: Display active agent count instead of generic "Offline"

### D50: Agent Card Shows Last Active in Collapsed State
- **Decision**: Show "Last: X min ago" in collapsed agent card row 2
- **User Feedback**: "agent卡片收起时显示一下last active：x min ago"
- **Reason**: Activity recency is key info for agent usefulness; quickly identify active agents
- **Trade-off**: Slightly more text in collapsed card
- **Implementation**:
  - Add `lastActivityAgo` to card-row in collapsed state
  - Format: "Last: 5 min ago" or "Last: never"

### D51: Task Card Shows Owner in Collapsed State
- **Decision**: Show assignee/owner in collapsed task card row 2
- **User Feedback**: "task卡片收起时最好也能显示owner"
- **Reason**: Ownership is critical for task management; identify responsible party quickly
- **Trade-off**: More info in collapsed card, potential for long names
- **Implementation**:
  - Add assignee to card-row in collapsed state
  - Format: "Owner: Ricky" or just "@Ricky"
  - Truncate long names if needed

### D52: Session Count → Last Activity
- **Decision**: Replace "Sessions: N" with more meaningful activity indicator
- **User Feedback**: "agent卡片显示sessions：xx没意义，不如recent sessions?"
- **Reason**: Total session count doesn't indicate current state; last activity is more actionable
- **Trade-off**: Lose historical session count in collapsed view (can show in expanded)
- **Implementation**:
  - Collapsed card: Show "Last: X min ago" instead of session count
  - Expanded card: Still show session count as secondary info
  - Future: Consider "Recent sessions" count (last 24h/7d)

### D53: Agent Card Shows Current Activity (Channel)
- **Decision**: Display agent's current activity channel from `lastChannel` field
- **User Feedback**: "想知道 agent 在做什么" (e.g., "在飞书对话", "在 WebChat")
- **Reason**: Shows where agent is actively working; helps identify agent context
- **Data Source**: `sessions.json` contains `lastChannel` field (e.g., "webchat", "feishu")
- **Display Format**:
  - "webchat" → "在 WebChat"
  - "feishu" → "在飞书对话"
  - Other/unknown → "在线交互"
- **Trade-off**: Only shows channel, not specific action (would require parsing .jsonl)
- **Implementation**:
  - Backend: Add `lastChannel` and `currentActivity` to agent response in `get_session_info()`
  - Frontend: Show activity in collapsed card row 2
  - Format: "在飞书对话" or "WebChat"

### D54: Priority Dropdown Z-index Fix (overflow: visible)
- **Decision**: Change `.card` CSS from `overflow: hidden` to `overflow: visible`
- **User Feedback**: "Priority dropdown 被裁剪" (dropdown menu clipped when card not expanded)
- **Problem Analysis**:
  - `.card { overflow: hidden }` clips dropdown menu
  - `.priority-dropdown-menu { z-index: 200 }` still clipped by parent overflow
- **Reason**: Dropdown needs to extend beyond card boundaries
- **Trade-off**: May affect card rounded corners visual
- **Implementation**:
  - CSS Change: `.card { overflow: visible }`
  - Ensure `.card-header` has `overflow: hidden` for text truncation if needed

---

## v0.4.2 Agent Config Source Optimization (D55-D62)

### D55: Agent Configuration from openclaw.json
- **Decision**: Read agent list from `~/.openclaw/openclaw.json` → `agents.list`
- **User Feedback**: "complex-coding 早就不存在了，为什么还显示 idle？"
- **Reason**: File system scan shows historical agents; openclaw.json is authoritative config source
- **Data Source**: `~/.openclaw/openclaw.json` → `agents.list[].id`
- **Trade-off**: Depends on openclaw config structure; need to adapt if structure changes
- **Implementation**:
  - Add `AgentConfigCache` class to read openclaw.json
  - `get_agents()` iterates configured agent list instead of scanning file system
  - Unconfigured agents with sessions.json are no longer shown

### D56: Agent Config Cache Strategy (Lazy TTL)
- **Decision**: openclaw.json uses 60s lazy cache; sessions.json fresh read every time
- **Reason**: Balance config change awareness and I/O performance
- **Cache Strategy**:
  | Data Source | Cache Strategy | TTL | Reason |
  |-------------|----------------|-----|--------|
  | openclaw.json | Lazy cache | 60s | Stable config, sync with UI refresh |
  | sessions.json | Fresh read | None | Real-time status, user needs latest |
- **Performance**: I/O reduced from 3600/hour to 660/hour (82% ↓)
- **Implementation**:
  - Add `AgentConfigCache` class with `_agents_list`, `_last_read`, `_ttl`
  - Check TTL on each request, refresh if expired
  - `get_session_info()` remains fresh read

### D57: Two-Level Fallback Strategy
- **Decision**: Simplified fallback: openclaw.json → empty list + error
- **User Feedback**: "如果是空的，那么 openclaw 肯定也挂了，报错是好的"
- **Reason**: Removed whitelist (double config burden); openclaw.json should be authoritative
- **Fallback Chain**:
  ```
  openclaw.json (authoritative config)
      ↓ (read fails / file not found)
  Empty list + error message
  ```
- **Trade-off**: No fallback if openclaw.json fails; user sees empty list
- **Implementation**:
  - If openclaw.json read fails, return `{"agents": [], "error": "..."}`
  - No filesystem scan fallback

### D58: API Response Shows Config Source
- **Decision**: Add `meta.configSource` field to API response
- **Reason**: Debugging value; user knows which data source is active
- **Implementation**:
  ```json
  {
    "agents": [...],
    "meta": {
      "configSource": "openclaw.json",
      "agentCount": 2,
      "cached": false
    }
  }
  ```

### D59: Individual Agent Failure Isolation
- **Decision**: Single agent sessions.json failure doesn't affect other agents
- **Reason**: Robustness; one bad agent shouldn't break the whole list
- **Implementation**:
  - Wrap `get_session_info()` in try-except for each agent
  - Log warning for failed agent
  - Still add offline agent to list

### D60: Cache Preload on Service Start
- **Decision**: Initialize and preload cache when service starts
- **Reason**: Better first request experience; discover config errors early
- **Implementation**:
  ```python
  if __name__ == "__main__":
      agent_cache = AgentConfigCache()
      agent_cache.get_agents_list()  # Preload
      COADashHandler.agent_cache = agent_cache
  ```

### D61: Refresh Button Bypasses Cache
- **Decision**: Refresh button sends `?force=true` to bypass cache
- **User Feedback**: "用户手动刷新右上角按钮时能刷新下 agent 列表"
- **Reason**: User expects immediate refresh after config changes
- **Implementation**:
  - Frontend: `fetch('/api/agents?force=true')`
  - Backend: `if force: agent_cache.invalidate()`

### D62: Removed Whitelist Config
- **Decision**: Deleted `agents.whitelist` from design (was D59 in draft)
- **User Feedback**: "我们真的需要 whitelist 吗？"
- **Reason**: Double config burden; openclaw.json should be authoritative; deprecated agents should be removed from openclaw.json
- **Result**: Simplified from 3-level to 2-level fallback

---

## v0.4.2 UI Filter Refinement (D63)

### D63: Completed Tasks Toggle Instead of Filter Button
- **Decision**: Replace "已完成" filter button with Toggle switch
- **User Feedback**: "已完成应该换成某种显示已完成的显隐开关，默认已完成的不显示"
- **Reason**: Completed tasks are not a status filter but a visibility control; most task apps hide completed by default
- **Implementation**:
  - Remove "已完成" button from filter row 1
  - Add Toggle switch at end of row 1: `☑ 已完成`
  - Default: `showCompletedTasks = false` (hidden)
  - Toggle active: Show all completed tasks
  - Status filter only applies to non-completed tasks
- **UX Pattern**: Similar to Todoist, Microsoft To Do, Things 3
- **Code Changes**:
  - CSS: `.toggle-switch` with `.toggle-dot` indicator
  - HTML: `<span class="toggle-switch" id="showCompletedToggle">`
  - JS: `showCompletedTasks` state variable + click handler
  - Filter logic: `if (t.status === '已完成') return showCompletedTasks;`

---

## v0.4.3 Sessions Feature Design (D64-D71)

### D64: Sessions 独立标签页
- **Decision**: 新增 Sessions 标签页，显示 Live Sessions（活跃对话）
- **User Feedback**: "agent页面是不是应该显示 session"
- **Reason**: Agent 可以有多个 session，用户需要看到活跃的对话和工作
- **Implementation**:
  - 底部导航添加 Sessions 标签页
  - 显示有 `lastChannel` 且 7 天内更新的 session
  - 默认按 `updatedAt` 降序排列

### D65: Live Session 定义
- **Decision**: Live Session 必须有 `lastChannel` 且 7 天内更新
- **Reason**: 过滤掉 cron 等后台任务，只显示用户真正参与的对话
- **判断逻辑**:
  ```python
  def is_live_session(session):
      channel = session.get('lastChannel')
      updated_at = session.get('updatedAt', 0)
      
      # 必须有 channel（排除后台任务）
      if not channel:
          return False
      
      # 7 天内更新
      if (now - updated_at) < 7 * 24 * 3600000:
          return True
      
      return False
  ```
- **状态指示**:
  - 🟢 在线：最近 1 小时更新
  - 🟡 空闲：1-24 小时更新
  - ⚪ 离线：>1 天更新

### D66: Cron Jobs 独立标签页（未来实现）
- **Decision**: 新增 Cron Jobs 标签页，显示后台定时任务
- **User Feedback**: "单独拉一个 cron 列表，而不是和 live session 混在一起"
- **Reason**: Cron session 数量大且用户关心程度低，需要分离显示
- **Implementation**:
  - 底部导航添加 Cron 标签页
  - 显示无 `lastChannel` 的 session（后台任务）
  - 默认只显示 Running 状态，失效的不显示
  - 未来可添加显隐开关
- **Status**: Phase 2（后续实现）

### D67: Cron Session 活跃定义
- **Decision**: Cron 默认只显示 Running 状态（`endedAt == null`）
- **User Feedback**: "cron 里边也有很多假的一过性或失效的 setting"
- **Reason**: 很多 `status=running` 的 cron 实际已有 `endedAt`，是假运行状态
- **判断逻辑**:
  ```python
  def is_active_cron(session):
      ended_at = session.get('endedAt')
      updated_at = session.get('updatedAt', 0)
      
      # 无 endedAt 且最近 24 小时更新
      if not ended_at and (now - updated_at) < 24 * 3600000:
          return True
      
      return False
  ```

### D68: 底部导航重新设计
- **Decision**: 新导航顺序 `[Agents] [Tasks] [Sessions] [Cron] [Config]`
- **User Feedback**: "agent/session 留一个页面就够，合并一下"
- **变更**:
  - 移除 Stats 标签页（Coming Soon，暂无用）
  - 移除 Chat 标签页（Coming Soon，暂无用）
  - 添加 Sessions 标签页
  - 添加 Cron 标签页（Phase 2）
- **未来考虑**: Agent 和 Sessions 合并到一个页面

### D69: Session 卡片交互设计（未来实现）
- **Decision**: Session 卡片支持查看对话和 chat 交互
- **User Feedback**: "未来应该让 session 列表用小图标列在左侧可以拉开，然后可以进入各个对话直接 chat"
- **当前实现**: [查看对话] 按钮（Phase 1）
- **未来实现**:
  - 左侧：Session 列表（小图标）
  - 右侧：Chat 界面（类似 AI chat app）
  - 支持直接在 session 中对话

### D70: Sessions API 端点
- **Decision**: 新增 `/api/sessions` 和 `/api/cron` 端点
- **Endpoints**:
  ```
  GET /api/sessions?agent=all&type=all
  GET /api/cron?agent=all&status=running&limit=20  (Phase 2)
  ```
- **响应结构**:
  ```json
  {
    "sessions": [
      {
        "sessionId": "ca179c9f-...",
        "agentId": "main",
        "type": "feishu",
        "channel": "feishu",
        "status": "active",
        "updatedAt": 1774945936957,
        "updatedAtAgo": "2hr ago",
        "lastChannel": "feishu",
        "endedAt": null
      }
    ],
    "counts": {
      "total": 3,
      "feishu": 2,
      "webchat": 1
    },
    "error": null
  }
  ```

### D71: 实现优先级
- **Decision**: Phase 1: Sessions 标签页 / Phase 2: Cron 标签页
- **Reason**: 渐进实现，优先显示活跃对话
- **Status**: Phase 1 完成

---

## v0.5.0 Session State + OpenCode Tab (D72-D92)

### D72: Session State Data Source
- **Decision**: Read from `~/.openclaw/workspace/session-state.json`
- **Reason**: Contains current task, waiting events, model info
- **Trade-off**: Depends on openclaw agent to update file

### D73: Session State Position
- **Decision**: Top bar, right side (before refresh button)
- **Reason**: 不遮挡主内容，始终可见
- **Trade-off**: Takes space in top bar

### D74: Session State Polling Interval
- **Decision**: 30 seconds
- **Reason**: 平衡实时性和性能
- **Trade-off**: Not real-time, acceptable for status display

### D75: Session State Icons
- **Decision**: 💤 idle / 🔄 working / ⏳ waiting / ❓ offline
- **Reason**: 直观易懂，emoji 通用
- **Trade-off**: Uses emoji instead of SVG

### D76: Session State Task Enrichment
- **Decision**: Merge session-state.json + tasks.jsonl
- **Reason**: 显示完整任务标题、优先级、状态
- **Implementation**: `/api/session-state` endpoint enriches current_task

### D77: Session State Popup
- **Decision**: Click to expand popup with details
- **Reason**: Show more info without cluttering top bar
- **Trade-off**: Requires tap to see details

### D78: OpenCode UI Approach
- **Decision**: Chat interface + command buttons, NOT terminal emulator
- **Reason**: 触屏友好，手机无键盘
- **Trade-off**: Less flexible than raw terminal

### D79: OpenCode Multi-Project
- **Decision**: Multiple opencode serve instances (4096-4098)
- **Reason**: 独立隔离，每个项目一个端口
- **Trade-off**: 资源占用较高

### D80: OpenCode API Access
- **Decision**: Proxy through coa-dash (`/api/opencode/*`)
- **Reason**: 安全可控，统一入口，可加认证
- **Trade-off**: Additional hop, slightly slower

### D81: OpenCode Proxy Security
- **Decision**: Whitelist allowed API paths
- **Reason**: Prevent SSRF, path traversal attacks
- **Implementation**: Only `/session`, `/agent`, `/config` etc allowed

### D82: OpenCode Session Status Icons
- **Decision**: 🔵 idle / 🟡 busy (animated) / 🔴 waiting / ✅ done
- **Reason**: 进度可见，动画表示 busy 状态
- **Implementation**: CSS animation for progress bar

### D83: OpenCode Mobile Sidebar
- **Decision**: Hidden by default, hamburger menu or swipe to open
- **Reason**: 移动端屏幕空间有限
- **Implementation**: Slide-over panel with overlay

### D84: OpenCode Command Buttons
- **Decision**: 44px min height, 8px gap, scrollable row
- **Reason**: 触屏友好，符合 accessibility 标准
- **Trade-off**: Takes space at bottom

### D85: OpenCode Command Button Actions
- **Decision**: `/model` → picker, `/agent` → picker, `/clear` → immediate, `/compact` → immediate
- **Reason**: 频繁操作一键触达
- **Implementation**: Dropdown pickers for model/agent

### D86: OpenCode Push Notifications
- **Decision**: On session done, when tab not focused
- **Reason**: 任务完成提醒
- **Implementation**: Notification API, request permission after first task

### D87: OpenCode SSE Connection Management
- **Decision**: Cleanup on page unload, reconnect on error
- **Reason**: 防止资源泄漏
- **Implementation**: `beforeunload` event closes EventSource

### D88: OpenCode Projects Configuration
- **Decision**: JSON file `config/opencode-projects.json`
- **Reason**: 用户可编辑，声明式配置
- **Trade-off**: Requires config file, no auto-discovery

### D89: OpenCode systemd Service Template
- **Decision**: Template service `opencode-serve@.service`
- **Reason**: 支持多实例，端口作为参数
- **Implementation**: `systemctl --user start opencode-serve@4096`

### D90: OpenCode ttyd Retention
- **Decision**: Keep existing ttyd service on port 7681
- **Reason**: 备用终端访问方式
- **Trade-off**: Two services running

### D91: OpenCode Default Project
- **Decision**: First project in config is default
- **Reason**: 用户打开 OpenCode tab 时有初始选择
- **Implementation**: Auto-select on tab open

### D92: OpenCode Message History Limit
- **Decision**: No limit for MVP, virtualize later
- **Reason**: 简化实现，后续优化
- **Trade-off**: Long conversations may slow down

### D93: OpenCode Proxy Gzip Handling
- **Decision**: Add `Accept-Encoding: identity` header to proxy requests
- **Reason**: OpenCode serve returns gzip-compressed responses by default; Python's urllib doesn't auto-decompress
- **Trade-off**: Slightly larger network transfer, but simpler implementation
- **Implementation**: Modified `proxy_opencode_request()` in server.py

### D94: OpenCode Session Source - SQLite vs HTTP API
- **Decision**: Query SQLite database directly instead of HTTP API
- **Reason**: 
  - HTTP API `/session` only returns `projectID="global"` sessions (filtered)
  - Project-specific sessions (coa-dash, opencode-coa, etc.) are NOT returned
  - Database contains all sessions including non-global ones
- **Trade-off**: Direct DB access vs API abstraction
- **Implementation**: `get_opencode_sessions()` function reads from `~/.local/share/opencode/opencode.db`

### D95: OpenCode Session Filter by Worktree
- **Decision**: Filter sessions by `project.worktree LIKE '%vault/projects%'`
- **Reason**: 
  - Show only sessions from user's project folders
  - Exclude generic sessions in `~/.openclaw/workspace`, `/tmp`, etc.
  - Future projects in `vault/projects/` automatically appear
- **Result**: Shows 3 sessions (coa-dash, opencode-coa, claude-code)
- **Implementation**: SQL JOIN session↔project, filter by worktree path

### D96: Status Dropdown Design
- **Decision**: Click status badge to show dropdown menu with 4 options
- **Reason**: Single-tap interaction, no keyboard, mobile-friendly
- **Options**: 待处理 / 进行中 / 已完成 / 挂起
- **Implementation**: `toggleStatusDropdown()`, `selectStatus()`, `setStatus()` functions
- **API**: `PUT /api/tasks/:id/status`

### D97: Assignee Dropdown Design
- **Decision**: Click assignee name to show picker with categories
- **Reason**: Same pattern as status dropdown, consistent UX
- **Categories**: Humans (Ricky), OpenClaw Agents (main, coder), OpenCode
- **Implementation**: `toggleAssigneeDropdown()`, `loadAssignees()`, avatar display by type
- **API**: `PUT /api/tasks/:id/assignee`
- **Visual**: Color-coded avatars (human=green, openclaw=blue, opencode=orange)

### D98: Batch Status Update API
- **Decision**: Single API call to update multiple tasks
- **Reason**: Efficiency for multi-select batch operations
- **Implementation**: `PUT /api/tasks/status/batch` with `{"task_ids": [...], "status": "..."}`
- **Response**: `{"success": true, "updated": N}`
- **Frontend**: Long-press (800ms) to enter batch selection mode

---

## Decision Summary

| Category | IDs | Status |
|----------|-----|--------|
| Touch-First Constraints | D1-D6 | Active |
| Mobile-First Layout | D7-D14 | D8 removed, D10/D12 updated |
| Card Interaction | D15-D22 | Active, D17/D18 updated in v0.4.1 |
| Visual Design | D23-D31 | Active |
| Data & API | D32-D38 | Active |
| v0.4.0 UI Enhancements | D39-D46 | Implemented |
| v0.4.1 UI Refinements | D47-D54 | Implemented |
| v0.4.2 Agent Config Optimization | D55-D62 | Implemented |
| v0.4.2 UI Filter Refinement | D63 | Implemented |
| v0.4.3 Sessions Feature | D64-D71 | Phase 1 complete |
| v0.5.0 Session State | D72-D77 | Implemented |
| v0.5.0 OpenCode Tab | D78-D95 | Planned (code lost, needs re-implementation) |
| v0.5.3 Status/Assignee | D96-D98 | Implemented (uncommitted) |
| v0.7.0 Claude Code & Feishu | D99-D115 | Implemented |
| **Total Active Decisions** | **115** | (D8 removed) |

---

## Decision Changes Log

| Version | Change | Description |
|---------|--------|-------------|
| 0.3.0 → 0.4.0 | D8 Removed | Top tabs removed, bottom nav sole navigation |
| 0.3.0 → 0.4.0 | D10 Updated | Bottom nav now visible in ALL modes |
| 0.3.0 → 0.4.0 | D12 Updated | Added right sidebar (200px) |
| 0.4.0 | D39-D46 Added | UI enhancement decisions |
| 0.4.0 → 0.4.1 | D17 Updated | Priority buttons replaced with dropdown (D48) |
| 0.4.0 → 0.4.1 | D18 Updated | Inline buttons removed, badge dropdown added |
| 0.4.1 | D47-D52 Added | UI refinement decisions from user testing feedback |
| 0.4.1 | D53 Added | Agent current activity display from lastChannel |
| 0.4.1 | D54 Added | Priority dropdown overflow fix |
| 0.4.2 | D55-D62 Added | Agent config source optimization (openclaw.json + cache) |
| 0.4.2 | D63 Added | Completed tasks toggle switch (visibility control) |
| 0.4.3 | D64-D71 Added | Sessions feature design (live sessions + cron separation) |
| 0.5.0 | D72-D77 Added | Session State display in top bar |
| 0.5.0 | D78-D92 Added | OpenCode tab with chat interface |
| 0.5.0 | D93 Added | Gzip handling fix for OpenCode proxy |
| 0.5.0 | D94-D95 Added | SQLite session query with worktree filter |
| 0.7.0 | D99-D115 Added | Claude Code sessions, Feishu bridge, MCP server |

---

## v0.7.0 — Claude Code Sessions & Feishu Bridge (D99-D115)

### D99: Claude Code session management via CLI subprocess
**Decision**: Use `claude --resume --print --output-format stream-json --dangerously-skip-permissions` to manage sessions. Each message spawns a subprocess, not a persistent process.
**Why**: Claude Code's built-in `--resume` flag provides session persistence. No need to manage long-running processes.
**Trade-off**: Each message has subprocess startup overhead (~2s), but gains reliability (no process crashes to handle).

### D100: Session limit by working count, not total
**Decision**: Limit to 20 concurrent **working** sessions, not 20 total. Idle sessions don't count.
**Why**: Idle sessions only consume memory (message history in dict). Limiting working sessions prevents resource contention from parallel Claude processes.

### D101: No timeout for Claude tasks
**Decision**: `proc.communicate(timeout=None)` — no time limit on Claude task execution.
**Why**: Complex tasks (codebase refactoring, multi-file edits) can take hours. User can use `/stop` to manually kill long-running tasks.

### D102: Live session protection via fuser
**Decision**: Before sending a message, check if a live Claude process has the session file open using `fuser`. Reject if busy.
**Why**: Sending a message while Claude is actively processing would cause context corruption in the session file.
**Trade-off**: `fuser` check adds ~1s latency. Worth it for safety.

### D103: Session persistence across server restarts
**Decision**: Save session metadata to `~/.claude/coa-dash-sessions.json`. Restore on startup, even if buffer file doesn't exist.
**Why**: Server restarts (systemctl restart, crash recovery) should not lose session mappings. Previously, new sessions without buffer files were lost.

### D104: Feishu bridge uses WebSocket (not webhook)
**Decision**: Use lark-oapi SDK WebSocket connection for real-time events, not HTTP webhook.
**Why**: WebSocket is simpler (no public endpoint, no signature verification), works behind NAT/firewall, and provides instant message delivery.

### D105: No @bot filtering for group chats
**Decision**: All messages in linked groups are forwarded to Claude, without requiring @bot prefix.
**Why**: User's groups are personal (only user + bot). Requiring @bot every time is tedious. User explicitly requested: "不要自作主张加@bot过滤".

### D106: Reaction-based status indicator (not message updates)
**Decision**: Show session status via cycling emoji reactions on the user's message, not by sending/updating progress messages.
**Why**: Feishu PatchMessage only works on card messages, not plain text. Sending multiple status messages would spam the chat. Reactions are non-intrusive and can be replaced in-place.
**Implementation**: Delete old reaction by reaction_id, add new reaction. `CreateMessageReaction` returns `reaction_id`, `DeleteMessageReactionRequest` uses it.

### D107: Feishu emoji_type is case-sensitive
**Decision**: Use exact case from Feishu docs. `Typing` not `TYPING`, `Fire` not `FIRE`, `CheckMark` not `CHECK`.
**Why**: Feishu API returns `231001 reaction type is invalid` for wrong case. Full list at https://open.feishu.cn/document/server-docs/im-v1/message-reaction/emojis-introduce

### D108: Polling-based response delivery (not webhook)
**Decision**: Bridge polls coa-dash API every 2s (working) / 6s (idle) to detect new Claude responses.
**Why**: No webhook infrastructure for Claude→Feishu direction. Polling is simple and reliable. 2s latency is acceptable for chat.

### D109: Response deduplication with text[:200] key
**Decision**: Deduplicate assistant responses using first 200 chars as key, in a `seen` set.
**Why**: `--resume` replays old messages in the JSONL file. Without dedup, old content appears as "new" and gets sent multiple times.

### D110: MCP server wraps coa-dash HTTP API
**Decision**: MCP server (`coa-dash-mcp.py`) calls coa-dash REST API, doesn't duplicate session management logic.
**Why**: Single source of truth. Any improvements to the API (persistence, protection, limits) automatically benefit MCP clients.

### D111: MCP claude_chat is synchronous with polling
**Decision**: `claude_chat` tool blocks until Claude responds, polling status every 2s.
**Why**: OpenClaw agents need the response to decide next action. Async would require complex callback flow that MCP doesn't support.

### D112: /link supports fuzzy matching
**Decision**: `/link <query>` matches against session ID prefix, shortId, project name, name, and title. Returns most recent match.
**Why**: Feishu users can't easily type full session IDs on mobile. Typing project name is more natural.

### D113: /new auto-creates project directory
**Decision**: `/new <project>` creates `/home/aegis/vault/projects/<project>` if not exists, runs `git init`, creates session, and auto-links.
**Why**: Reduces friction for starting new projects from Feishu. One command instead of mkdir + git init + create session + link.

### D114: Bridge persistence via JSON file
**Decision**: Chat-session mappings saved to `config/feishu-persistence.json` on every change.
**Why**: Bridge restarts should preserve mappings. In-memory state would require re-linking every chat.

### D115: /stop kills Claude process
**Decision**: `/stop` finds and kills Claude processes matching the session, using `pgrep -f "claude.*--resume.*<id>"`.
**Why**: No timeout on tasks means users need a manual escape hatch for stuck or unwanted long-running tasks.

---

**END OF DESIGN DECISIONS**

**END OF DESIGN DECISIONS**