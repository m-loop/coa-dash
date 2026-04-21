# Changelog

All notable changes to COA-dash will be documented in this file.

## [0.7.2] - 2026-04-21

### Security
- **P0**: `inject_to_terminal` now sanitizes control chars and caps payload at 8KB, closing a PTY injection vector that allowed arbitrary terminal control sequences to be written to `/dev/pts/X` (`src/server.py`).

### Fixed
- **P0**: `send_message_async` / `send_message` no longer hold `session._lock` across the full `proc.stdout` iteration — the lock now scopes only to `self.messages` mutation, removing a multi-minute deadlock that blocked `FileWatcher` and status broadcasts (`src/server.py`).
- **P0**: Dead-code tail after `return False` in `ClaudeSession.is_live()` removed (`src/server.py`).
- **P0**: Feishu bridge `stop()` previously referenced `subprocess.run` with no module-level import, raising `NameError` at shutdown and leaving orphan Claude processes; `import subprocess` now lives at module top (`src/feishu-bridge.py`).

### Docs
- Added `docs/AUDIT-2026-04-21.md` — full P0/P1/P2 audit with remediation owners.
- Synced version strings across VERSION / README / CLAUDE.md / DESIGN-DECISIONS.md.

## [0.7.1] - 2026-04-15

### Fixed
- Session stuck in "working" status from terminal activity detection

## [0.7.0] - 2026-04-15

### Added
- **Feishu-Claude Bridge** (`src/feishu-bridge.py`)
  - WebSocket-based real-time message bridge between Feishu chats and Claude Code sessions
  - Supports DM and group chats (no @bot filtering required)
  - Reaction-based status indicator with cycling replacement (⌨️ Typing → 🤔 Thinking → 🔧 Tool → ✅ Done)
  - Commands: `/link`, `/new`, `/unlink`, `/stop`, `/list`, `/status`, `/sessions`, `/help`
  - `/link` supports fuzzy matching by session ID prefix, project name, or title
  - `/new` auto-creates project directory with git init
  - `/stop` kills running Claude process for current session
  - Deduplicated response delivery via polling (2s while working, 6s idle)
  - Systemd service (`systemd/feishu-bridge.service`)
- **MCP Server** (`src/coa-dash-mcp.py`)
  - FastMCP-based stdio server exposing 5 tools for OpenClaw agent integration
  - `claude_session_create`, `claude_session_list`, `claude_chat`, `claude_session_history`, `claude_session_delete`
  - Synchronous `claude_chat` with polling until response
- **Claude Code Sessions** in dashboard
  - Session management via `--resume --print --output-format stream-json`
  - SSE streaming for real-time updates
  - File watcher for imported sessions
  - Session persistence across server restarts (`~/.claude/coa-dash-sessions.json`)
  - Live session protection (rejects messages when active Claude process detected via `fuser`)
  - Import existing Claude sessions from disk
- **Feishu indicators** in dashboard UI (💬 badge on linked sessions)
- Agent notification endpoint (`POST /api/agents/:id/notify`)

### Changed
- Session limit changed from 20 total to 20 concurrent **working** sessions
- Session timeout removed (`timeout=None`) — supports hours-long tasks
- All coa-dash sessions use `--dangerously-skip-permissions` for non-interactive operation

### Fixed
- `ClaudeSession.__init__` fields lost when `is_live()` method was added
- Session persistence: sessions restored even without buffer file on disk
- Polling baseline tracking uses `messageCount` from session info (not unreliable `total` from history)
- Duplicate response filtering with content deduplication (`text[:200]` key)
- MCP `claude_chat` uses `pre_send_count` for reliable response extraction
- MCP `claude_session_list` sorts by status health (idle > starting > working > error)

## [0.6.0] - 2026-04-12

### Added
- Statistics page with agent utilization, task throughput, session activity
- Security fixes for API endpoints

## [0.5.5] - 2026-04-01

### Added
- Task execute feature with agent selection (⚡ button)
- `POST /api/tasks/:id/execute` endpoint

## [0.5.4] - 2026-04-01

### Added
- OpenCode tab with sidebar + chat interface
- Session State button in top bar
- `GET /api/opencode/sessions` (SQLite query)
- `GET /api/opencode/projects`

## [0.5.3] - 2026-04-01

### Added
- Status dropdown (click badge to change)
- Assignee picker with color-coded avatars
- Batch status update (`PUT /api/tasks/status/batch`)
- Long-press multi-select for batch operations

## [0.5.1] - 2026-04-01

### Added
- Swipe-to-delete on mobile tasks
- `DELETE /api/tasks/:id` endpoint

## [0.5.0] - 2026-03-31

### Added
- Session State display (D72-D77)
- OpenCode tab with multi-project support (D78-D95)
- API proxy with port whitelist security (D99)

## [0.4.4] - 2026-03-30

### Changed
- UI refinements and session expansion

## [0.4.0] - 2026-03-30

### Added
- Mobile-first redesign with bottom navigation
- Agent hierarchy visualization
- Dark mode OLED theme

## [0.3.0] - 2026-03-29

### Added
- Task management with parent-child tree
- Agent notification via `openclaw agent --message`

## [0.2.0] - 2026-03-28

### Added
- Agent status monitoring
- Live sessions display

## [0.1.0] - 2026-03-27

### Added
- Initial release
- Basic dashboard with agent overview
