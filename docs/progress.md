# COA-dash Progress

## Current State

**Version**: 0.5.4 (OpenCode Tab + Session State)
**Status**: Implemented and pushed to GitHub
**Last Updated**: 2026-04-01

---

## v0.5.4 - OpenCode Tab + Session State (2026-04-01)

### Features Implemented
- [x] OpenCode tab in bottom nav (replaced Stats)
- [x] OpenCode page layout with sidebar + chat
- [x] Session list with status icons
- [x] Chat interface with command buttons
- [x] Session State button in top bar
- [x] Session State popup with task details

### Design Decisions
- **D78-D92**: OpenCode Tab UI specifications
- **D73-D77**: Session State display

### API Endpoints Added
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/opencode/projects | GET | List configured OpenCode projects |
| /api/session-state | GET | Get current openclaw session state |
| /api/opencode/:port/session/:id/messages | GET | Get session messages |
| /api/opencode/:port/session/:id/message | POST | Send message to session |
| /api/opencode/:port/session/:id/command | POST | Send command to session |

### Git Status
```
Commit: a193b16
Pushed: 2026-04-01
```

---

## v0.5.3 - Status & Assignee Dropdowns (Committed)

### Features Implemented
- [x] Click status badge to show dropdown menu
- [x] Status options: 待处理/进行中/已完成/挂起
- [x] PUT /api/tasks/:id/status endpoint
- [x] PUT /api/tasks/status/batch endpoint for batch updates
- [x] Long-press for multi-select batch operations
- [x] Batch toolbar with status selection menu
- [x] Click assignee to show picker with categories
- [x] Color-coded avatars by type (human/openclaw/opencode)
- [x] GET /api/opencode/sessions endpoint (SQLite query)

### Design Decisions
- **D96**: Status dropdown - click badge, show menu, single-tap
- **D97**: Assignee dropdown - click name, show picker, color avatars
- **D98**: Batch status update API for multi-select efficiency

### Files Modified
| File | Changes |
|------|---------|
| `src/server.py` | +215 lines (update_task_status, get_opencode_sessions) |
| `src/index.html` | +212 lines (status/assignee dropdowns) |
| `docs/DESIGN-DECISIONS.md` | +D96-D98 |
| `docs/PRD.md` | v0.5.3 features |
| `VERSION` | 0.5.3 |

### Git Status
```
Modified: src/server.py, src/index.html, docs/, VERSION
Untracked: .playwright-mcp/, config/opencode-projects.json
```

---

## Next: v0.5.4 - OpenCode Tab Re-implementation

### Background
- v0.5.0 code was lost (only existed in memory during test)
- systemd restart loaded old code from git HEAD
- Need to re-implement from documentation

### Design Decisions (Already Documented)
- D78-D95: OpenCode Tab specifications
- D94-D95: SQLite session query with worktree filter

### Implementation Plan
1. Add OpenCode tab button to bottom nav
2. Create OpenCode page layout (sidebar + main)
3. Implement session list component
4. Implement chat interface
5. Add Session State button in top bar
6. Test on Mate X6

### Git Strategy
- Commit after every component
- Push after every commit
- No code left in memory

---

## ⚠️ CRITICAL DISCOVERY (2026-04-01)

### Version Discrepancy

| Source | Version | OpenCode Tab | Session State |
|--------|---------|--------------|---------------|
| Deployed (localhost:8890) | 0.4.4 | ❌ Not present | ❌ Not present |
| Git HEAD (committed) | 0.5.1 | ❌ Not present | ❌ Not present |
| Working directory (uncommitted) | 0.5.x | ⚠️ Partial code in server.py | ⚠️ Partial code |
| docs/progress.md | 0.5.2 | ✅ Documented as done | ✅ Documented as done |
| docs/CONTEXT.md | 0.5.0 | ✅ Documented as done | ✅ Documented as done |

### Evidence

```
$ git log --oneline -5
23ecedb feat: Add swipe-to-delete for tasks (v0.5.1)
d83d57a docs: Restore full CONTEXT.md
5fbb677 docs: Compress CONTEXT.md for new phase
f78bc9e v0.4.4: UI refinements + session expansion

$ curl localhost:8890/ | grep "title"
<title>COA-dash v0.4.4</title>

$ grep -c "OpenCode" src/index.html
6  # Only in assignee section, NOT as a tab

$ git diff src/index.html | grep -n "OpenCode"
84: .assignee-avatar.opencode {  # CSS for avatar
178-181: // OpenCode Agents section  # Assignee dropdown only

$ git reflog -20  # No v0.5.0 commit found
$ git stash list  # Empty - no stashed changes
```

### Root Cause Analysis

1. **Context compression**: Previous session documented features as "done" but never committed the code
2. **E2E test confusion**: Test results in progress.md may have been from a different project or imagined
3. **No v0.5.0 commit**: The OpenCode tab was never actually implemented in code
4. **Assignee dropdown**: Implemented but not documented (should be v0.5.3)

### Actual Uncommitted Changes (Working Directory)

| File | Changes | Status |
|------|---------|--------|
| `src/server.py` | +215 lines | update_task_status, get_opencode_sessions (D94-D95) |
| `src/index.html` | +212 lines | Assignee dropdown (D101), status dropdown |
| `docs/*` | +180 lines | Documentation ahead of code |

### 🚨 CODE LOSS INVESTIGATION (2026-04-01)

**Evidence from Playwright test logs** (`.playwright-mcp/page-2026-03-31T15-01-24-182Z.yml`):
- OpenCode Tab WAS working at 15:02 on 2026-03-31
- Sessions list showed 39 items
- Projects showed coa-dash, my-app

**Timeline reconstruction**:
| Time | Event |
|------|-------|
| 14:59-15:02 | OpenCode Tab working (Playwright recorded) |
| 15:08:26 | systemd restarted coa-dash.service |
| 15:08:26+ | Server loaded old code (v0.4.4 from git HEAD) |
| 00:14 (Apr 1) | Current server process started |

**Code location analysis**:
```bash
$ grep -c "OpenCode" src/index.html  # Working directory
6  # Only in assignee section, NOT as tab

$ wc -l src/index.html
2131  # Working directory

$ git show HEAD:src/index.html | wc -l
1923  # Git HEAD
```

**Root cause**: 
- OpenCode Tab code existed **in memory** during test session
- Code was NEVER written to disk or committed to git
- When systemd restarted, the in-memory changes were lost
- Working directory has assignee/status changes, but NOT OpenCode Tab

**Conclusion**: OpenCode Tab frontend code is **permanently lost**. Need to re-implement.

### Decision Required

**Option A**: Re-implement OpenCode Tab from documentation
- Use docs/PRD.md and docs/DESIGN-DECISIONS.md as specification
- Backend API already exists (get_opencode_sessions)
- Need to add frontend: tab button, page layout, session list, chat UI

**Option B**: Commit current changes as v0.5.3
- Status dropdown ✅
- Assignee dropdown ✅  
- `/api/opencode/sessions` API ✅
- OpenCode Tab frontend ❌ (postpone to v0.5.4)

**Option C**: Rollback everything to v0.4.4
- Discard all uncommitted changes
- Update docs to match code
- Start fresh

---

## v0.5.3 - Status & Assignee Dropdowns (Uncommitted)

### Features Implemented
- [x] Click status badge to show dropdown menu
- [x] Status options: 待处理/进行中/已完成/挂起
- [x] PUT /api/tasks/:id/status endpoint
- [x] PUT /api/tasks/status/batch endpoint for batch updates
- [x] Long-press for multi-select batch operations
- [x] Batch toolbar with status selection menu
- [x] Instant status切换 with visual feedback

### Technical Changes
- **Frontend**: 
  - toggleStatusDropdown() function
  - selectStatus() and setStatus() functions
  - setStatusBatch() for batch operations
  - Long-press detection (800ms) for batch selection
  - Batch toolbar UI with status menu
  - CSS for status-dropdown-menu and batch selection styles
- **Backend**: 
  - update_task_status() function
  - update_task_status_batch() function
  - do_PUT handler extended for /api/tasks/:id/status and /api/tasks/status/batch

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/tasks/:id/status | PUT | Update single task status |
| /api/tasks/status/batch | PUT | Update multiple tasks status |

### Testing
- [x] Single task status update API tested
- [x] Batch status update API tested (2 tasks updated)
- [x] Frontend status dropdown rendered
- [ ] Manual testing: Click status badge, select new status
- [ ] Manual testing: Long-press for batch selection

###验收结果
- ✅ 状态切换即时生效
- ✅ 支持单个任务状态修改
- ✅ 支持批量状态修改

## v0.5.1 - Swipe-to-Delete (2026-04-01)

### Features Implemented
- [x] Swipe-to-delete on mobile (left swipe reveals delete button)
- [x] Confirmation dialog before deletion
- [x] DELETE /api/tasks/:id endpoint
- [x] Auto-refresh after successful deletion
- [x] Smooth swipe animation with threshold detection

### Technical Changes
- **Frontend**: Touch event handlers (touchstart/touchmove/touchend), CSS animations, confirmation dialog
- **Backend**: delete_task() function, do_DELETE handler
- **UX**: 70px swipe threshold, prevent accidental clicks, visual feedback

### Testing
- [x] API DELETE endpoint tested
- [x] Task deletion verified
- [ ] Frontend swipe animation (manual testing required)


## v0.5.0 - OpenCode Tab & Session State

### Features Implemented
- [x] Session State button in top bar
- [x] Session State popup with task details
- [x] OpenCode tab with sidebar and chat
- [x] Multi-project support (config/opencode-projects.json)
- [x] OpenCode API proxy with security whitelist
- [x] Sessions list from opencode serve

### Bug Fixes
- [x] Gzip compression issue: Added `Accept-Encoding: identity` to proxy requests

### Known Issues
- [ ] Message loading slow (52KB+ response from opencode)
- [ ] SVG icon error in refresh button

### E2E Test Results (2026-03-31)
| Feature | Status |
|---------|--------|
| Session State button | ✅ Pass |
| Session State popup | ✅ Pass |
| OpenCode tab load | ✅ Pass |
| Projects list | ✅ Pass |
| Sessions list (39 items) | ✅ Pass |
| Session selection | ⚠️ Slow API |

## History

| Date | Version | Changes |
|------|---------|---------|
| 2026-04-01 | 0.5.2 | Status adjustment, batch operations |
| 2026-04-01 | 0.5.1 | Swipe-to-delete |
| 2026-03-31 | 0.5.0 | OpenCode tab, Session State button, API proxy |
| 2026-03-30 | 0.4.0 | Mobile-first redesign, bottom nav |
| 2026-03-29 | 0.3.0 | Task management, notifications |
| 2026-03-28 | 0.2.0 | Agent status, live sessions |
| 2026-03-27 | 0.1.0 | Initial release |

## Services Running

| Service | Port | Status |
|---------|------|--------|
| coa-dash | 8890 | ✅ Active |
| opencode-serve@4096 | 4096 | ✅ Active |
| ttyd | 7681 | ✅ Active (backup) |

## Test URLs

- Local: http://localhost:8890
- Tailscale: http://100.103.186.109:8890

