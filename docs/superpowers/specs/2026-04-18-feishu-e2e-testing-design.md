# Feishu Bridge E2E Testing Design

## Goal

Verify Feishu Bot interaction quality through real browser testing — not API mocks. Catch issues that only manifest in the actual Feishu UI: card rendering, reaction display, duplicate delivery, stale cards.

## Architecture

Two phases:
- **Phase C (Interactive)**: Playwright MCP in Claude Code session. Scripts handle mechanical ops (navigate, type, wait), Claude reads snapshots for assertions.
- **Phase A (Script固化)**: Independent `e2e-feishu.js` Playwright script, zero AI cost, reusable.

```
Data:
  config/feishu-e2e-cookies.json   — Feishu login session (gitignored)
  screenshots/feishu-e2e/          — Visual evidence per scenario
  docs/FEISHU-E2E-REPORT.md        — Test results
```

## Test Scenarios (13)

### Group 1: Basic Flow

| # | Name | Action | Verify |
|---|------|--------|--------|
| T1 | Send message → reply | Send "ping" in test group | Green done card with Claude response |
| T2 | Reaction lifecycle | Send "hello" | ⌨️ → tool emoji → ✅ sequence |
| T3 | Working → Done card | Send "list files" | Blue working card updates, final green done card |

### Group 2: Commands

| # | Name | Action | Verify |
|---|------|--------|--------|
| T4 | /new create session | Send `/new test-project` | "Created & linked" confirmation |
| T5 | /sessions list | Send `/sessions` | Session list with relative times |
| T6 | /link session | Send `/link <id>` | "Linked to" confirmation |
| T7 | /load history | Send `/load` | Single combined card (not multiple) |
| T8 | /stop interrupt | Send message → immediately `/stop` | Confirmation, session returns idle |

### Group 3: Edge Cases

| # | Name | Action | Verify |
|---|------|--------|--------|
| T9 | Busy feedback | Send while session working | "会话忙碌" text + ⏰ reaction |
| T10 | Rapid duplicate send | Send same message twice in 0.5s | Only one done card (dedup) |
| T11 | Old card not mutated | Compare T1 card after T3 | T1 done card unchanged |
| T12 | Bridge restart no replay | Restart bridge, wait for poll | No new done card, "Bridge restarted" notice |
| T13 | WS dedup in logs | Check journalctl | `skip duplicate msg_id` in logs |

## Timeouts

| Action | Timeout |
|--------|---------|
| Wait for reaction | 120s |
| Wait for card change | 60s |
| Per-scenario global | 300s |

## Cost Strategy

- Mechanical ops (navigate, type, wait, screenshot): `browser_run_code` JS scripts
- Assertions (verify card content, reaction): Claude reads snapshot
- Phase A script: pure Playwright JS, zero AI cost

## Verification Methods

- T1-T10: Playwright accessibility snapshot (read message text + reaction)
- T11: Record first card message_id, compare after later scenarios
- T12: Snapshot check message count before/after restart
- T13: `journalctl` log grep for dedup evidence

## Risks

- Feishu web DOM changes → use accessibility roles, not CSS selectors
- Cookie expiry → detect login redirect, prompt re-login
- Claude reply non-determinism → verify "reply exists" not "reply matches"
