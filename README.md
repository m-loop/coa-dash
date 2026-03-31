# COA-dash

**Command Orchestration Agent Dashboard**

The best agentic dashboard - humanity's most efficient HMI for AI agent orchestration.

## Status: MVP Complete ✅

**Version**: 0.4.4

## Features

- **Agent Overview**: Live status (online/busy/idle/offline/dead/sick), hierarchy visualization
- **Task Management**: Parent-child tree, priority ranking, one-click queue jump
- **Agent Notification**: Push task changes to agents via `openclaw agent --message`
- **Mobile-First Touch UI**: Optimized for Huawei Mate X6 (folded + unfolded)
- **Statistics**: Idle ratio, throughput metrics (Phase 2)
- **Agent Chat**: Direct chat to each agent (Phase 4)

## Quick Start

```bash
# Start the dashboard (foreground)
cd /home/aegis/vault/projects/coa-dash
python3 src/server.py

# Or install as systemd service
./scripts/install.sh

# Access via browser
# Local: http://localhost:8890
# Tailscale: http://100.103.186.109:8890
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/agents` | Agent list with status |
| GET | `/api/gateway/status` | Gateway health check |
| GET | `/api/tasks` | Task tree with stats |
| PUT | `/api/tasks/:id/priority` | Update task priority |
| POST | `/api/tasks/:id/notify` | Send notification to agent |
| GET | `/api/config` | Read-only configuration |

## Project Structure

```
coa-dash/
├── config/
│   └── config.json       # Configuration
├── docs/
│   ├── PRD.md           # Product Requirements (v0.3.0)
│   ├── DESIGN-DECISIONS.md  # 38 design decisions
│   ├── MOBILE-UI-SPEC.md    # Complete CSS spec
│   └── CONTEXT.md       # Runtime context
├── src/
│   ├── server.py        # HTTP server (350 lines)
│   └── index.html       # Mobile UI (800 lines)
├── scripts/
│   ├── install.sh       # Install systemd service
│   └── start.sh         # Quick start
├── systemd/
│   └── coa-dash.service # Service definition
├── task-viewer/         # Port 8888
├── openclaw-dashboard/  # Port 8889
├── README.md
└── VERSION
```

## Documentation

- [PRD.md](docs/PRD.md) - Product Requirements Document v0.3.0
- [DESIGN-DECISIONS.md](docs/DESIGN-DECISIONS.md) - 38 design decisions
- [MOBILE-UI-SPEC.md](docs/MOBILE-UI-SPEC.md) - Complete CSS specification
- [CONTEXT.md](docs/CONTEXT.md) - Runtime context & session history

## Design Highlights

- **Touch-First**: 44px touch targets, tap to expand, long-press for actions
- **Dark Mode OLED**: Background `#020617`, optimized for eye comfort
- **Responsive**: Single column (folded) → Sidebar layout (unfolded)
- **Zero Dependency**: Pure Python + vanilla HTML/CSS/JS

## Service Management

```bash
systemctl --user status coa-dash
systemctl --user restart coa-dash
systemctl --user stop coa-dash
journalctl --user -u coa-dash -f
```

## License

MIT
