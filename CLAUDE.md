# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

COA-dash (Command Orchestration Agent Dashboard) - A mobile-first, touch-first dashboard for AI agent orchestration. Targets Huawei Mate X6 foldable phone as primary device.

**Current Version**: 0.5.5

## Commands

### Start the server
```bash
# Foreground (for development)
python3 src/server.py

# Or via systemd user service
systemctl --user start coa-dash
systemctl --user status coa-dash
systemctl --user restart coa-dash
journalctl --user -u coa-dash -f  # View logs
```

### Install as systemd service
```bash
./scripts/install.sh
```

### Test API endpoints
```bash
curl -s localhost:8890/api/agents
curl -s localhost:8890/api/tasks
curl -s localhost:8890/api/sessions
curl -s localhost:8890/api/opencode/sessions
curl -s localhost:8890/api/session-state
curl -s localhost:8890/api/assignees
curl -s localhost:8890/api/config
```

### Run E2E tests
Tests are run via Playwright MCP. See `docs/test-cases.md` for test design and `docs/TEST-REPORT.md` for results.

## Architecture

### Tech Stack
- **Backend**: Pure Python 3 HTTP server (BaseHTTPRequestHandler), no frameworks
- **Frontend**: Vanilla HTML/CSS/JS single file (`src/index.html` ~90KB), no build step
- **Data Sources**: JSON/JSONL files + SQLite database (no traditional database)

### Key Data Sources

| Source | Path | Purpose |
|--------|------|---------|
| Config | `config/config.json` | Dashboard settings, gateway, tasks path, agent hierarchy |
| OpenClaw config | `~/.openclaw/openclaw.json` | Agent list configuration |
| Sessions | `~/.openclaw/agents/{agent}/sessions/sessions.json` | Agent session data |
| Tasks | `/home/aegis/vault/tasks/tasks.jsonl` | Task management (JSONL format) |
| OpenCode DB | `~/.local/share/opencode/opencode.db` | OpenCode session data (SQLite) |
| OpenCode projects | `config/opencode-projects.json` | OpenCode project mappings |

### HTTP Server (`src/server.py`)

The server handles all API endpoints and serves the static frontend:
- **GET handlers**: `/api/agents`, `/api/tasks`, `/api/sessions`, `/api/opencode/*`, `/api/session-state`, `/api/assignees`, `/api/config`
- **PUT handlers**: Task priority, status, assignee updates
- **POST handlers**: Task notifications, execute task, OpenCode proxy
- **DELETE handlers**: Task deletion

Key patterns:
- `AgentConfigCache` class with TTL caching for openclaw.json reads
- JSONL file parsing for tasks (line-by-line JSON)
- SQLite queries for OpenCode session data
- `subprocess.Popen` for async task execution (detached from HTTP response)

### Frontend (`src/index.html`)

Single-file SPA with embedded CSS and JS. Key patterns:
- CSS variables for theming (`--bg: #020617` dark OLED theme)
- Bottom navigation (4 tabs: Agents, Tasks, OpenCode, Config)
- Responsive breakpoints: <780px (folded), ≥780px (unfolded with sidebars)
- Touch-first: 44px minimum touch targets, no keyboard shortcuts

## Design Constraints (from PRD)

Critical constraints from `docs/PRD.md` and `docs/DESIGN-DECISIONS.md`:

### Touch-First (Must Follow)
- **No keyboard shortcuts** - primary device is touch-screen phone
- **44px minimum touch targets** - all interactive elements
- **No hover-dependent interactions** - touch screens have no hover
- **No drag-and-drop** - conflicts with scroll
- **No double-tap** - conflicts with single-tap
- **Minimal text input** - mobile keyboard experience is poor

### Mobile-First Layout
- Fixed top bar (48px folded, 56px unfolded)
- Fixed bottom nav (56px, always visible)
- Full-width cards
- Dual sidebar on unfolded (≥780px): left 240px, right 200px

## Configuration

### Dashboard Config (`config/config.json`)
```json
{
  "dashboard": { "port": 8890, "host": "0.0.0.0" },
  "gateway": { "port": 18789, "healthz": "...", "readyz": "..." },
  "tasks": { "path": "/home/aegis/vault/tasks/tasks.jsonl" },
  "agents": { "sessionsPath": "~/.openclaw/agents", "hierarchy": {...} },
  "status": { "busyThresholdSeconds": 30, "idleThresholdMinutes": 5 }
}
```

### OpenCode Projects (`config/opencode-projects.json`)
Maps project names to paths and ports for OpenCode session filtering.

## Documentation

Key documents in `docs/`:
- `PRD.md` - Product requirements, design constraints, feature specs
- `DESIGN-DECISIONS.md` - 38+ design decisions with reasoning (D1-D98)
- `MOBILE-UI-SPEC.md` - Complete CSS specification
- `test-cases.md` - E2E test case design
- `TEST-REPORT.md` - Test execution results

## Service Details

- **Port**: 8890
- **Access**: `http://localhost:8890` or `http://100.103.186.109:8890` (Tailscale)
- **Service file**: `systemd/coa-dash.service`

## API Endpoints Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/agents` | Agent list with status |
| GET | `/api/gateway/status` | Gateway health check |
| GET | `/api/tasks` | Task tree with stats |
| PUT | `/api/tasks/:id/priority` | Update task priority |
| PUT | `/api/tasks/:id/status` | Update task status |
| PUT | `/api/tasks/:id/assignee` | Update task assignee |
| PUT | `/api/tasks/status/batch` | Batch status update |
| POST | `/api/tasks/:id/notify` | Send notification to agent |
| POST | `/api/tasks/:id/execute` | Execute task immediately |
| DELETE | `/api/tasks/:id` | Delete task |
| GET | `/api/sessions` | Live sessions list |
| GET | `/api/opencode/sessions` | OpenCode sessions from SQLite |
| GET | `/api/opencode/projects` | OpenCode project config |
| GET | `/api/session-state` | Current openclaw session state |
| GET | `/api/assignees` | Available assignees (humans + agents) |