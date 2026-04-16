# Feishu-Claude Bridge: Design & Audit Document

**Date:** 2026-04-16
**Status:** Active — P1/P2/P9 fixed, 6 critical + 7 medium issues remain
**Scope:** feishu-bridge.py, server.py (ClaudeSession), config files, runtime state

---

## 1. System Architecture

```
Feishu User  ←→  Feishu Platform (WebSocket)  ←→  feishu-bridge.py  ←→  coa-dash server.py  ←→  Claude CLI
                       (open.feishu.cn)              (poll + commands)      (HTTP API)           (--print --resume)
```

### Component Responsibilities

| Component | Role | Process |
|-----------|------|---------|
| **feishu-bridge.py** | Feishu↔Claude bridge: WS listener, commands, poll loops, reactions, cards | systemd: feishu-bridge.service |
| **server.py** | Session management: create/delete/send, subprocess spawn, history, SSE | systemd: coa-dash.service |
| **Claude CLI** | Code execution via `--print --output-format stream-json` | subprocess per message |
| **Feishu Platform** | Message delivery via WebSocket + REST API (lark_oapi SDK) | External |

### Data Flow: Message Send → Response

```
1. User sends text in Feishu DM/group
2. Feishu WS pushes event to bridge (_on_message_receive)
3. Bridge adds ⌨️ reaction, records msg_id in _pending_reactions
4. Bridge POSTs to coa-dash /api/claudecode/sessions/{id}/message
5. coa-dash spawns Claude CLI with --resume (background thread)
6. Claude streams JSON to stdout → server parses line-by-line
   - Updates session.status, current_activity in real-time
   - Broadcasts SSE events to dashboard
7. Bridge poll loop (2s interval) detects:
   a. Activity changes → updates blue "working" card via PatchMessage
   b. Reaction emoji cycles (Typing→Thinking→SMART→OPEN_BOOK)
   c. messageCount increase → fetches history, extracts assistant text
8. On completion:
   a. Sends green card with full response
   b. Replaces reaction with ✅ CheckMark
   c. Updates forward_baselines, saves persistence
```

---

## 2. State Model

### Persisted State (survives restart)

| File | Contents | Writer |
|------|----------|--------|
| `config/feishu-bridge.json` | Static config: app_id, app_secret, mode, coa_dash_url | Manual |
| `config/feishu-persistence.json` | Runtime: chat_session_map, forward_baselines, mode | bridge |
| `~/.claude/coa-dash-sessions.json` | Session metadata: id, name, cwd, claude_session_id | server |
| `/tmp/claude-session-{id}.jsonl` | Message buffer (Claude stream-json output) | server |

### In-Memory State (lost on restart)

| Variable | Purpose | Recovery |
|----------|---------|----------|
| `_pending_reactions` | session→Feishu msg_id for reactions | None (orphaned) |
| `_current_reactions` | session→reaction_id for replacement | None |
| `_response_cards` | session→card msg_id for PatchMessage | None (new card sent) |
| `_last_delivered_hash` | session→MD5 of last response (dedup) | None (may re-deliver once) |
| `_forward_baselines` | session→messageCount watermark | Loaded from persistence |
| `claude_sessions[].messages` | Full message list in memory | Recovered from buffer file |

### Thread Model

| Thread | Count | Trigger |
|--------|-------|---------|
| WS listener | 1 | Bridge startup |
| Poll loops | 1 per linked session | /link or /new |
| Claude subprocess | 1 per active message | send_message_async() |
| HTTP handlers | 1 per request | ThreadingHTTPServer |
| SSE handlers | 1 per dashboard connection | Browser connect |
| FileWatchers | 0-1 per session | SSE subscriber |

### Timers & Thresholds

| Timer | Value | Purpose |
|-------|-------|---------|
| Poll interval (idle) | 6s | Check for new messages |
| Poll interval (working) | 2s | Faster status tracking |
| Stale detection | 300s (5 min) | Kill dead-process sessions |
| Card update throttle | Per activity change | Avoid API spam |
| Forward timeout | 120s | POST message to coa-dash |
| Compact timeout | 120s | Claude /compact operation |
| MAX_SESSIONS | 20 | Concurrent working limit |

---

## 3. Command Reference

| Command | Handler | API Calls |
|---------|---------|-----------|
| `/link <id\|name>` | `_cmd_link()` | GET session info, optional session list |
| `/new <project> [cwd]` | `_cmd_new()` | os.makedirs, git init, POST create session |
| `/unlink` | `_cmd_unlink()` | Stop poll, save persistence |
| `/stop` | `_cmd_stop()` | pgrep + kill Claude processes |
| `/compact` | `_cmd_compact()` | claude --resume subprocess |
| `/sessions` | `_cmd_sessions()` | GET session list (sorted by lastUsedAt) |
| `/status` | `_cmd_status()` | GET session info |
| `/list` | `_cmd_list()` | GET session info per mapping |
| `/ls [path]` | `_cmd_ls()` | os.listdir (restricted to /home/aegis/vault/projects) |
| `/help` | inline | Static text |

---

## 4. Card Message Protocol

### Card Types

| Phase | Header Color | Title | Content | Update Method |
|-------|-------------|-------|---------|---------------|
| Working | Blue | "Claude (working)" | `**{activity}**` | PatchMessage |
| Working (partial text) | Blue | "Claude (working...)" | Partial response text | PatchMessage |
| Done | Green | "Claude" | Full response text | New card |
| Error | Red | "Claude" | Error message | New card |

### Reaction Protocol

| Phase | Emoji | Meaning |
|-------|-------|---------|
| Received | ⌨️ Typing | Message accepted |
| Processing | 🧠 THINKING | Claude thinking |
| Tool use | 💡 SMART | Tool: Grep/Search |
| Reading | 📖 OPEN_BOOK | Tool: Read |
| Writing | ✏️ PENCIL | Tool: Write/Edit |
| Done | ✅ CheckMark | Response delivered |
| Busy | ⏰ Alarm | Session busy, message rejected |
| Error | ❌ CrossMark | Error occurred |
| Stale | ❌ CrossMark | Session stuck, auto-reset |

---

## 5. Poll Loop State Machine

```
START → Load baseline from persistence
  │
  ├─ No baseline? → Set to current count, sleep 6s, loop
  │
  ├─ GET session info
  │   ├─ Connection error → Sync baseline, sleep 6s, loop
  │   └─ Success → Extract status, activity, messageCount
  │
  ├─ Is working?
  │   ├─ Stale check: same activity >5min + process dead?
  │   │   └─ YES → Reset session, notify user, loop
  │   ├─ Activity changed? → Update reaction, update card
  │   └─ Update working_since timer
  │
  ├─ messageCount > baseline?
  │   └─ NO → Sleep 2s (working) or 6s (idle), loop
  │
  ├─ YES → Fetch history, extract last assistant text
  │   ├─ No text found? → Sleep, loop
  │   ├─ Still working? → Update card with partial text, sleep 2s
  │   └─ Done?
  │       ├─ Content hash == last delivered? → Skip (dedup), update baseline
  │       └─ New content → ✅ reaction, send green card, update baseline, save
  │
  └─ loop
```

---

## 6. Issue Registry

### Fixed (2026-04-16)

| ID | Category | Description | Fix |
|----|----------|-------------|-----|
| P1 | Concurrency | Two concurrent messages to same session spawn two Claude processes | status="working" set inside lock atomically |
| P2 | Deadlock | stderr=PIPE causes deadlock when Claude writes >64KB stderr | stderr=DEVNULL in all subprocess calls |
| P9 | Thread Safety | save_sessions_metadata() iterates dict without lock | Lock→RLock, function acquires lock |
| REG | Regression | send_message_async success path was killing process + setting "Timeout" | Corrected try/except structure |
| DEDUP | Data Integrity | coa-dash restart recalculates messageCount, bridge re-delivers old content | MD5 content hash dedup |
| SORT | UX | /sessions returned unsorted, can't find recent sessions | Sort by lastUsedAt descending |
| NAME | Bug | PUT status handler used `sessions` instead of `claude_sessions` | Fixed variable name |

### Critical — Not Fixed (🔴)

| ID | Category | Description | Impact | Fix Plan |
|----|----------|-------------|--------|----------|
| S3 | UX | Busy session silently drops message, only ⏰ reaction | User thinks message queued, actually lost | Return text "会话忙碌，请稍后重试" |
| S11 | Process | coa-dash restart leaves Claude subprocess orphan | Process writes to nobody, may hang | Store proc ref on session, kill in stop() |
| S12 | Data | Forward succeeds but baseline not saved before crash | Restart replays all history | Set baseline before POST /message |
| S17 | Security | No user auth — anyone in Feishu group can execute code | Arbitrary code execution via --dangerously-skip-permissions | Whitelist chat_id in config |
| S18 | Security | /new accepts arbitrary cwd paths | Session created in sensitive directories | Validate cwd prefix |
| S15 | Platform | WS disconnect loses messages silently | User doesn't know message was lost | Heartbeat logging + reconnect notification |

### Medium — Not Fixed (🟡)

| ID | Category | Description |
|----|----------|-------------|
| S4 | UX | Long responses truncated to 3500 chars with no indication |
| S5 | UX | Code blocks render poorly in Feishu card markdown |
| S6 | State | Bridge restart loses _response_cards, blue cards stuck at "working" forever |
| S7 | State | /link to new session doesn't update old working card to done |
| S8 | Logic | Two chats can link to same session, both poll threads deliver duplicates |
| S9 | Logic | Session deleted via dashboard but bridge poll continues with 404 loop |
| S13 | Command | /compact may not work in --dangerously-skip-permissions interactive mode |
| S14 | State | /stop kills process but doesn't reset coa-dash session status |
| S19 | Security | app_secret stored in plaintext in feishu-bridge.json |
| MEM | Resource | messages list grows unbounded (11000+ entries), eventual OOM risk |

### Low — Not Fixed (🟢)

| ID | Category | Description |
|----|----------|-------------|
| S1 | UX | No onboarding prompt after /new (user doesn't know to send a message) |
| S2 | Logic | /new with same project name creates second session, old becomes orphan |
| S10 | Data | Corrupted JSON in buffer file silently skipped, message lost |
| P4 | State | Reaction state (_pending_reactions, _current_reactions) lost on bridge restart |
| P8 | State | Card IDs lost on bridge restart |
| P15 | Code | Dead code in is_live() lines 154-160 (unreachable, would break lock) |
| P16 | Code | is_live() path encoding missing .replace("~", "-") |

---

## 7. Meta-Audit Findings

### Over-Design

| Feature | Assessment |
|---------|------------|
| Content hash dedup | Only prevents exact-match duplicates. Changed-one-char defeats it. Acceptable as quick fix. |
| Working-phase card streaming | ~5 API calls per task for activity updates. Short tasks (<5s) never show intermediate states. |

### Under-Design

| Gap | Severity | What's Missing |
|-----|----------|----------------|
| Message queue | 🔴 | No buffering for busy sessions — messages just dropped |
| Graceful shutdown | 🔴 | No proc tracking, no SIGTERM handling for Claude subprocesses |
| Auth/ACL | 🔴 | No user identity check — anyone who can message the bot gets code exec |
| Path validation | 🔴 | /new allows any cwd |
| Memory management | 🟡 | No eviction policy for messages list |

### Cost Estimates

| Resource | Current | Risk |
|----------|---------|------|
| Poll QPS | ~0.5-2 (4 sessions × 2-6s) | Low |
| Feishu API calls | ~10-20 per task (reactions + cards) | Low (rate limit 5-50/s) |
| Memory per session | ~11000 messages × ~1KB = ~11MB | Medium (grows linearly) |
| Claude CLI startup | ~3-5s overhead per message | Medium (unavoidable) |

---

## 8. Priority Fix Order (Recommended)

1. **S18** — Path validation (1 line, prevents security issue)
2. **S3** — Busy feedback (3 lines, prevents user confusion)
3. **S14** — /stop status reset (5 lines, prevents stale working state)
4. **S17** — Chat ID whitelist (config + 5 lines, prevents unauthorized access)
5. **S12** — Baseline before forward (prevents replay on crash)
6. **S11** — Proc reference tracking (prevents orphan processes)
7. **S9** — Poll stop on session delete (prevents 404 loop)
8. **MEM** — Message list eviction (prevents OOM)
