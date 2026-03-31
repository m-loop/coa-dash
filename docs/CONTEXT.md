# COA-dash Context

**Version**: 0.4.4 | **Repo**: https://github.com/m-loop/coa-dash | **Port**: 8890

---

## Project Overview

Mobile-first, touch-first dashboard for AI agent orchestration. Optimized for Huawei Mate X6 foldable.

**Tech Stack**: Python HTTP server + vanilla HTML/CSS/JS (zero dependencies)

---

## Current Features

| Page | Content |
|------|---------|
| **Agents** | Sessions (24h), flat format `agentId/channel`, expandable with model/job/duration |
| **Tasks** | Parent-child tree, priority filtering, expand/collapse |
| **Stats** | Task stats + agent status counts |
| **Config** | Dashboard/gateway settings |

---

## Key Design Decisions

| ID | Decision |
|----|----------|
| D72-D75 | Bottom nav: `[Agents][Tasks][Stats][Config]`, Sessions merged into Agents |
| D76 | Expand button: circular + SVG chevron + rotation |
| D77 | Priority badge: parent tasks only |
| D78-D79 | Session expansion: model, jobName, duration, chatType |
| D80 | Bell button: documented for future fix |

---

## Data Sources

| Source | Path |
|--------|------|
| Agent config | `~/.openclaw/openclaw.json` (agents.list) |
| Sessions | `~/.openclaw/agents/*/sessions/sessions.json` |
| Tasks | `/home/aegis/vault/tasks/tasks.jsonl` |

---

## Known Issues

| Issue | Status |
|-------|--------|
| Bell button "发送失败" | Documented in PRD, needs CLI debugging |

---

## Next Phase Ideas

- [ ] Fix bell button notification
- [ ] WebSocket for live updates
- [ ] Cron jobs page (Phase 2)
- [ ] Agent chat interface
- [ ] Change model feature for sessions