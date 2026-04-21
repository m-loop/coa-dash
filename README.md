# COA-dash

**Command Orchestration Agent Dashboard**

Mobile-first, touch-first dashboard for AI agent orchestration. Optimized for Huawei Mate X6 foldable.

**Version**: 0.7.2

## Features

- **Claude Code Sessions**: Create, manage, and chat with Claude Code sessions from the dashboard
- **Feishu Bridge**: Chat with Claude from Feishu DMs and groups with live status reactions
- **MCP Server**: Structured tool interface for OpenClaw agents to delegate tasks to Claude Code
- **Agent Overview**: Live status (online/busy/idle/offline), hierarchy visualization
- **Task Management**: Parent-child tree, priority ranking, one-click execute
- **OpenCode Integration**: Browse and interact with OpenCode sessions
- **Mobile-First Touch UI**: Dark OLED theme, 44px touch targets, responsive layout

## Architecture

```
                    ┌─── Feishu users ←→ feishu-bridge ───┐
                    │                                       │
Dashboard UI ←──────┤─── coa-dash API (:8890) ─────────────┤──→ Claude Code
                    │                                       │    (--resume --print)
                    └─── OpenClaw agents ←─ MCP server ────┘
                                         (stdio)
```

## Quick Start

```bash
# Start the dashboard
python3 src/server.py

# Or via systemd
systemctl --user start coa-dash
systemctl --user start feishu-bridge

# Access via browser
# Local: http://localhost:8890
# Tailscale: http://100.103.186.109:8890
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| coa-dash | 8890 | Dashboard + API server |
| feishu-bridge | - | Feishu-Claude WebSocket bridge |

## API Endpoints

### Agent & Task Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/agents` | Agent list with status |
| GET | `/api/gateway/status` | Gateway health check |
| GET | `/api/tasks` | Task tree with stats |
| PUT | `/api/tasks/:id/priority` | Update task priority |
| PUT | `/api/tasks/:id/status` | Update task status |
| PUT | `/api/tasks/:id/assignee` | Update task assignee |
| POST | `/api/tasks/:id/notify` | Send notification to agent |
| POST | `/api/tasks/:id/execute` | Execute task immediately |
| DELETE | `/api/tasks/:id` | Delete task |

### Claude Code Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/claudecode/sessions` | List all sessions |
| POST | `/api/claudecode/sessions` | Create new session |
| GET | `/api/claudecode/sessions/:id` | Session info |
| GET | `/api/claudecode/sessions/:id/history` | Conversation history |
| POST | `/api/claudecode/sessions/:id/message` | Send message |
| GET | `/api/claudecode/sessions/:id/stream` | SSE real-time updates |
| DELETE | `/api/claudecode/sessions/:id` | Delete session |
| GET | `/api/claudecode/available` | List disk sessions for import |
| POST | `/api/claudecode/import` | Import existing session |

### OpenCode & Feishu

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/opencode/sessions` | OpenCode sessions from SQLite |
| GET | `/api/opencode/projects` | OpenCode project config |
| GET | `/api/feishu/topics` | Feishu-Claude bridge mappings |
| GET | `/api/session-state` | Current openclaw session state |

## Feishu Bridge

Chat with Claude Code from Feishu. Supports DM and group chats.

### Commands

| Command | Description |
|---------|-------------|
| `/new <project> [cwd]` | Create session (auto mkdir + git init) |
| `/link <id\|name>` | Link chat to session (fuzzy match) |
| `/unlink` | Remove link |
| `/stop` | Stop running Claude task |
| `/status` | Current session status |
| `/sessions` | List available sessions |
| `/help` | Show commands |

### Status Reactions

Reactions cycle on your message to show live status:

| Stage | Reaction |
|-------|----------|
| Received | ⌨️ Typing |
| Thinking | 🤔 |
| Tool: Bash | 💣 |
| Tool: Edit | 🔥 |
| Done | ✅ |
| Busy | ⏰ |
| Error | ❌ |

## MCP Server

Exposes Claude Code session management as MCP tools for OpenClaw agents.

```bash
# Test standalone
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python3 src/coa-dash-mcp.py

# Register in openclaw.json
"mcp": { "servers": { "coa-dash": { "command": "python3", "args": ["src/coa-dash-mcp.py"] } } }
```

**Tools**: `claude_session_create`, `claude_session_list`, `claude_chat`, `claude_session_history`, `claude_session_delete`

## Project Structure

```
coa-dash/
├── config/
│   ├── config.json              # Dashboard config
│   ├── feishu-bridge.json       # Bridge credentials
│   └── feishu-persistence.json  # Session mappings (auto)
├── docs/
│   ├── PRD.md                   # Product requirements
│   ├── DESIGN-DECISIONS.md      # Design decisions log
│   └── MOBILE-UI-SPEC.md        # CSS specification
├── src/
│   ├── server.py                # HTTP server + session manager
│   ├── feishu-bridge.py         # Feishu-Claude bridge
│   ├── coa-dash-mcp.py          # MCP server for OpenClaw
│   └── index.html               # Dashboard UI
├── systemd/
│   ├── coa-dash.service         # Dashboard service
│   └── feishu-bridge.service    # Bridge service
└── scripts/
    ├── install.sh               # Install services
    └── check-pending.sh         # Check pending messages
```

## Service Management

```bash
systemctl --user status coa-dash feishu-bridge
systemctl --user restart coa-dash feishu-bridge
journalctl --user -u feishu-bridge -f
```

## Tech Stack

- **Backend**: Pure Python 3 (BaseHTTPRequestHandler), zero frameworks
- **Frontend**: Vanilla HTML/CSS/JS, no build step
- **Bridge**: lark-oapi SDK (Feishu WebSocket), polling-based response delivery
- **MCP**: FastMCP (stdio transport)
- **Data**: JSON/JSONL files + SQLite (no database server)

## License

MIT
