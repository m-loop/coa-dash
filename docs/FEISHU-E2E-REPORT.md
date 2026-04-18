# Feishu Bridge E2E Test Report

**Date**: 2026-04-18
**Environment**: bridge-test group, Feishu web via Playwright MCP
**Bridge version**: afb9d8c

## Results: 12/13 PASS, 1 PARTIAL

| # | Scenario | Result | Notes |
|---|----------|--------|-------|
| T1 | Send message → reply card | PASS | "ping" → "Pong!" green card |
| T2 | Reaction lifecycle | PASS | THINKING → Typing → CheckMark |
| T3 | Working → Done card | PASS | Blue working updates, green done sent |
| T4 | `/new` create session | PASS | "Created & linked" + session ID |
| T5 | `/sessions` list | PASS | Relative time, newest first |
| T6 | `/link` session | PASS | "Linked to" confirmation |
| T7 | `/load` history | PASS | Single combined card |
| T8 | `/stop` interrupt | PARTIAL | pgrep pattern mismatch — Claude CLI uses internal session ID |
| T9 | Busy feedback | PASS | ⏰ AlarmClock + "会话忙碌，请稍后重试" |
| T10 | Rapid duplicate send | PASS | Second msg gets "busy", WS dedup skips replay |
| T11 | Old card not mutated | PASS | Previous done cards preserved after fix |
| T12 | Bridge restart no replay | PASS | "Bridge restarted" notice, no old content |
| T13 | WS dedup in logs | PASS | `skip duplicate msg_id` confirmed |

## Bugs Found & Fixed

### Done card overwritten by next working card (CRITICAL)
- **Symptom**: T1's green "Pong!" card overwritten to blue "Claude (working)" when T2 started
- **Root cause**: `_response_cards[session_id]` kept done card ID after delivery. Next working phase reused it via `_update_card()`
- **Fix**: Pop `_response_cards[session_id]` after sending done card (`afb9d8c`)
- **Lesson**: Only discovered through real UI testing — API tests would never catch this

## Known Issues

### `/stop` pgrep pattern mismatch
- `pgrep -f "claude.*--resume.*{coa_dash_session_id}"` doesn't match actual process
- Actual command: `claude --resume {claude_internal_session_id} --dangerously-skip-permissions`
- Need to map coa-dash session ID → Claude session ID, or use server-side process tracking
