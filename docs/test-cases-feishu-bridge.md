# Feishu Bridge E2E Test Cases

**Version**: 0.8.0
**Date**: 2026-04-20
**Status**: Active

---

## Design Methodology

### First Principles

A user interacts with the Feishu bridge through exactly **3 input mechanisms**:

| Input | Mechanism | Examples |
|-------|-----------|---------|
| Text command | Type `/command` in chat | `/sessions`, `/link 3`, `/help` |
| Text message | Type free-form text (non-command) | `帮我看看这个bug` |
| Card button | Click button on interactive card | [Sessions], [Link], [Stop] |

The bridge operates in **2 connection states**:

| State | Description |
|-------|-------------|
| Unlinked | Chat has no Claude session. Commands work, messages rejected. |
| Linked | Chat connected to a Claude session. Commands + messages both work. |

Linked sessions have sub-states: idle / working / stale / deleted.

### MECE Matrix

Every test case maps to exactly one cell in `{input} x {state}`. No overlap, no gaps.

```
                    │ Unlinked  │ Linked-Idle │ Linked-Working │ Linked-Deleted │
────────────────────┼───────────┼─────────────┼────────────────┼────────────────┤
/help               │ FB-01     │ FB-02       │ FB-02          │ FB-01          │
/sessions           │ FB-03     │ FB-03       │ FB-03          │ FB-03          │
/link               │ FB-04~07  │ FB-08       │ —              │ —              │
/new                │ FB-09~10  │ FB-11       │ —              │ —              │
/unlink             │ FB-12     │ FB-13       │ —              │ —              │
/status             │ FB-01     │ FB-14       │ FB-14          │ FB-01          │
/list               │ FB-15     │ FB-15       │ —              │ —              │
/stop               │ FB-12     │ FB-16       │ FB-16          │ —              │
/compact            │ FB-12     │ FB-17       │ —              │ —              │
/load               │ FB-12     │ FB-18       │ —              │ —              │
/ls                 │ FB-19~20  │ FB-19~20    │ —              │ —              │
unknown cmd         │ FB-21     │ FB-21       │ —              │ —              │
text message        │ FB-22     │ FB-23       │ FB-24          │ FB-25          │
card button click   │ FB-26~32  │ FB-26~32    │ —              │ —              │
edge cases          │ FB-33~38  │ (cross-cutting)              │ —              │
```

(`—` means covered by the unlinked variant, since commands don't depend on linked state unless they need the session)

---

## Test Cases

### A. Discovery Commands (no session needed)

#### FB-01: /help shows control panel (unlinked)

**Priority**: P0
**User story**: As a new user, I type /help to learn what this bot does.
**Steps**: Send `/help`
**Expected**:
- Reply is an interactive card (not plain text)
- Card title: "Claude Bridge"
- Card shows "No session linked"
- Card contains [Sessions] and [New] buttons
- Card header is green (done template)

---

#### FB-02: /help shows control panel (linked)

**Priority**: P0
**Precondition**: Session linked, idle
**Steps**: Send `/help`
**Expected**:
- Card title: "Claude Bridge"
- Card shows session name, status, message count, last active time
- Card contains [Stop], [History], [Compact], [Unlink], [Sessions] buttons
- Status emoji matches actual session status (idle/working)

---

#### FB-03: /sessions lists all projects with correct status

**Priority**: P0
**Steps**: Send `/sessions`
**Expected**:
- Reply is an interactive card
- Lists sessions grouped by project (one per project, latest)
- Each session shows: project/name, status tag, message count
- **Status tags are accurate** (the bug we fixed):
  - 💻 terminal — only when terminal process confirmed (cwd match + JSONL mtime < 300s)
  - ⚡ active — only when session is genuinely active (API says isActive)
  - Plain time — for genuinely idle sessions
- No false ⚡ on idle sessions
- Each session has a [N] button for linking
- Index numbers match: `/link N` resolves to correct session

**Edge cases to verify**:
- Session with terminal open shows 💻
- Session with Claude running shows ⚡
- Session idle for 3+ days shows "Nd ago"
- No sessions → "No sessions found." text

---

#### FB-15: /list shows active mappings

**Priority**: P1
**Steps**: Send `/list`
**Expected**:
- Lists all chat→session mappings
- Format: `- name (chat xxxxxxxx...)`
- No mappings → "None. Use /link <session-id>"

---

### B. Connection Commands

#### FB-04: /link by index number

**Priority**: P0
**Precondition**: `/sessions` returned index map
**Steps**: Send `/link 3` (where 3 is a valid session index)
**Expected**:
- Reply: `✅ Linked to: <session-name>`
- `/list` now shows the mapping
- Polling thread starts for this session

---

#### FB-05: /link by session ID (prefix match)

**Priority**: P1
**Steps**: Send `/link 7dc0ef37` (valid session ID prefix)
**Expected**:
- Fuzzy matches the session by ID prefix
- Reply: `✅ Linked to: <matched-name>`

---

#### FB-06: /link with invalid input

**Priority**: P1
**Steps**: Send `/link nonexistent`
**Expected**:
- Reply: `Session 'nonexistent' not found. Try /sessions`
- No mapping created

---

#### FB-07: /link with no arguments

**Priority**: P2
**Steps**: Send `/link` (no args)
**Expected**:
- Reply: `Usage: /link <#|session-id|name>`

---

#### FB-08: /link replaces existing mapping

**Priority**: P1
**Precondition**: Already linked to session A
**Steps**: Send `/link <session-B>`
**Expected**:
- Old session A polling stopped
- New session B polling started
- `/list` shows only session B
- Reply: `✅ Linked to: <session-B>`

---

#### FB-09: /new creates session and auto-links

**Priority**: P0
**Steps**: Send `/new test-project`
**Expected**:
- Auto-creates `/home/aegis/vault/projects/test-project/` if not exists
- Inits git repo in new directory
- Creates Claude session via API
- Auto-links this chat to new session
- Reply: `✅ Created & linked: test-project 📁 Created /home/aegis/vault/projects/test-project Session: <id> Send a message to start!`

---

#### FB-10: /new with path traversal blocked

**Priority**: P0 (security)
**Steps**: Send `/new hack /tmp/evil`
**Expected**:
- Reply: `⚠️ Only /home/aegis/vault/projects/ allowed`
- No directory created outside vault

---

#### FB-11: /new with no arguments

**Priority**: P2
**Steps**: Send `/new` (no args)
**Expected**:
- Reply shows usage instructions

---

#### FB-12: Command requires linked session (unlinked state)

**Priority**: P1
**Precondition**: No session linked
**Steps**: Send `/unlink`, `/stop`, `/compact`, `/load`
**Expected**:
- `/unlink`: "No linked session."
- `/stop`: "No linked session."
- `/compact`: "No linked session."
- `/load`: "No session linked. Use /link <session-id>"

---

#### FB-13: /unlink removes mapping

**Priority**: P0
**Precondition**: Session linked
**Steps**: Send `/unlink`
**Expected**:
- Reply: `✅ Unlinked`
- `/list` no longer shows this mapping
- Polling thread stopped

---

### C. Session Management Commands

#### FB-14: /status shows session details

**Priority**: P1
**Precondition**: Session linked
**Steps**: Send `/status`
**Expected**:
- Shows: Session name, ID, Claude SID, folder, status, model, message count, context estimate, duration, project
- All fields populated with real data

---

#### FB-16: /stop kills Claude process

**Priority**: P0
**Precondition**: Session linked, Claude actively running
**Steps**: Send `/stop`
**Expected**:
- Finds Claude process via pgrep (by claudeSessionId, then session_id, then buffer file)
- Kills the process
- Reply: `⛔ Stopped (killed N process(es))`
- Session status reset to idle via API

**Edge**: No active process → "No active process found. Session may already be idle."

---

#### FB-17: /compact compresses session context

**Priority**: P1
**Precondition**: Session linked, idle, has conversation history
**Steps**: Send `/compact`
**Expected**:
- Reply: `⏳ Compacting session context...`
- Runs `claude --resume <sid> --dangerously-skip-permissions` with `/compact\n/exit` stdin
- On success: `✅ Context compacted (was N messages). Session ready.`
- On timeout (2 min): `⚠️ Compact timed out (2 min). Try again or start a new session.`
- Session working → `⚠️ Session is working. Wait or /stop first.`

---

#### FB-18: /load shows conversation history

**Priority**: P1
**Precondition**: Session linked, has conversation history
**Steps**: Send `/load 3`
**Expected**:
- Reply is a card with last 3 conversation rounds
- Each round shows Q (user) and A (assistant), truncated
- Card title: `📂 <project> — Last 3 rounds`
- Rounds in chronological order

**Edge cases**:
- `/load` (no args) → defaults to 3 rounds
- `/load 0` → clamped to 1
- `/load 15` → clamped to 10
- No history → "No conversation history found."

---

#### FB-19: /ls lists project directories

**Priority**: P1
**Steps**: Send `/ls`
**Expected**:
- Lists directories under `/home/aegis/vault/projects/`
- Git repos marked with `*`
- Format: `📂 / (N dirs)` then `  dirname *`
- Max 30 entries, `+N more` if exceeded

---

#### FB-20: /ls with path traversal blocked

**Priority**: P0 (security)
**Steps**: Send `/ls ../../etc`
**Expected**:
- Reply: `⚠️ Only /home/aegis/vault/projects allowed`

---

#### FB-21: Unknown command

**Priority**: P2
**Steps**: Send `/foo`
**Expected**:
- Reply: `Unknown command. Try /help`

---

### D. Text Message Forwarding

#### FB-22: Text message without linked session

**Priority**: P0
**Precondition**: No session linked
**Steps**: Send `你好` (non-command text)
**Expected**:
- Reply: `No Claude session linked. Use /link <session-id> or /new <name> to connect.`
- No Typing reaction added
- No message forwarded to Claude

---

#### FB-23: Text message forwarded to idle session (happy path)

**Priority**: P0
**Precondition**: Session linked, idle
**Steps**: Send `e2e test message`
**Expected**:
- Typing ⌨️ reaction added to user's message immediately
- Message forwarded to Claude via API
- No CrossMark ❌ error (the bug we fixed — disk sessions work)
- Claude response arrives as card:
  - While working: reaction cycles through emojis (THINKING, Pin, Fire, etc.) based on activity
  - While working: **new blue working card** created with "⏳ Thinking..." (unless recent done card within TTL)
  - While working: same card updated in place with activity text / partial response
  - On completion: reaction replaced with ✅ CheckMark
  - On completion: **same card turns green** ("done") with full response (not a new card)
  - If >10 min since last done → new card created; otherwise existing card reused

---

#### FB-24: Text message while session is busy

**Priority**: P0
**Precondition**: Session linked, already working (Claude processing previous message)
**Steps**: Send `second message`
**Expected**:
- Bridge checks session status BEFORE injecting — detects "working"/"starting"
- Reaction: Alarm ⏰ emoji on user's message
- Text: `⏰ 会话忙碌，请稍后重试`
- Message NOT forwarded to Claude
- No card created for rejected message

---

#### FB-25: Text message to deleted session

**Priority**: P1
**Precondition**: Session linked but then deleted from server
**Steps**: Send `test`
**Expected**:
- CrossMark ❌ reaction on user's message
- Error feedback in chat
- Poll detects 404 → auto-unlinks, stops polling

---

### E. Card Button Interactions

#### FB-26: Click [Sessions] button → shows session list

**Priority**: P0
**Steps**: On /help control panel card, click [Sessions] button
**Expected**:
- Session list card appears (same as `/sessions` output)
- Each session has [Link] button

---

#### FB-27: Click [Link] button on session card

**Priority**: P0
**Steps**: On sessions card, click [N] button for a session
**Expected**:
- Session linked
- Toast: "Done"
- Same behavior as `/link N`

---

#### FB-28: Click [Stop] button

**Priority**: P0
**Precondition**: Session linked, Claude running
**Steps**: Click [Stop] button on control panel
**Expected**:
- Claude process killed
- Same as `/stop`

---

#### FB-29: Click [Unlink] button

**Priority**: P0
**Precondition**: Session linked
**Steps**: Click [Unlink] button on control panel
**Expected**:
- Mapping removed, polling stopped
- Same as `/unlink`

---

#### FB-30: Click [History] button

**Priority**: P1
**Precondition**: Session linked
**Steps**: Click [History] button (value: `{"action":"load","rounds":3}`)
**Expected**:
- Last 3 rounds displayed as card
- Same as `/load 3`

---

#### FB-31: Click [Compact] button

**Priority**: P1
**Precondition**: Session linked, idle
**Steps**: Click [Compact] button
**Expected**:
- Compact process starts
- Same as `/compact`

---

#### FB-32: Click [New] button

**Priority**: P2
**Steps**: Click [New] button on unlinked control panel
**Expected**:
- Reply: `Create a new session: /new <project-name> [cwd]`

---

### F. Response Lifecycle (Claude → Feishu)

#### FB-33: Working state — reaction cycling

**Priority**: P0
**Precondition**: Session linked, Claude actively processing
**Observe**: Reactions on user's message change over time
**Expected**:
- Typing → THINKING (when activity: "thinking")
- THINKING → Pin (when activity: "tool:read")
- Pin → Fire (when activity: "tool:edit")
- Activity-specific emoji mapping per `_activity_emoji()`
- Reaction continues cycling throughout working state

---

#### FB-34: Working card creation and update

**Priority**: P0
**Precondition**: Session linked, Claude processing
**Observe**: Cards appear in chat
**Expected**:
- First activity → **blue working card** created with activity text (visible near user message)
- Activity changes → **same card** updated in place (not new card)
- Card title: "Claude (working)" or "Claude (working...)"
- Card header: blue (working)
- Partial response text appears in card as Claude streams

---

#### FB-35: Done card delivery

**Priority**: P0
**Precondition**: Claude finishes response
**Observe**: Final card in chat
**Expected**:
- **Same card turns green** (working → done in place, not a new card)
- Card title: "Claude"
- Card contains Claude's full response text
- ✅ CheckMark reaction replaces working emoji
- Done timestamp recorded for TTL check
- Next message within 10 min → reuses this card; after 10 min → creates new card

---

#### FB-36: Response dedup (no duplicate delivery)

**Priority**: P1
**Precondition**: Bridge restarts after delivering a response
**Expected**:
- On restart, bridge loads `last_delivered_hash` and `forward_baselines` from persistence
- Same response text hash → skipped, not re-delivered
- Baseline synced to current message count

---

#### FB-37: Stale session detection

**Priority**: P1
**Precondition**: Session status stuck "working" for 5+ minutes, Claude process dead
**Expected**:
- Poll detects: working 5+ min + same activity + no process
- Session reset to idle via API
- Chat notified: `⚠️ Session was stuck (process died). Reset to idle. Try again.`
- CrossMark reaction

---

### G. Resilience & Security

#### FB-38: Bridge restart preserves state

**Priority**: P0
**Steps**: Restart bridge process
**Expected**:
- Loads `chat_session_map` from persistence
- Loads `forward_baselines` from persistence
- Resumes polling for all mapped sessions
- No message replay (baselines match current counts)

---

#### FB-39: coa-dash restart — graceful reconnection

**Priority**: P1
**Steps**: Restart coa-dash server while bridge is running
**Expected**:
- Poll gets 502/503 → resets baseline, retries
- When coa-dash back → baseline synced to current count
- No old messages replayed

---

#### FB-40: Non-whitelisted chat rejected

**Priority**: P0 (security)
**Precondition**: `allowed_chats` configured with specific chat_ids
**Steps**: Send message from non-whitelisted chat
**Expected**:
- Message silently ignored (no response, no error)
- Bridge log shows no processing for this chat_id

---

#### FB-41: Bot's own messages ignored

**Priority**: P1
**Steps**: Bot sends a response (triggered by another user)
**Expected**:
- Bot's response message event is received via WebSocket
- `sender.sender_type == "app"` → ignored
- No infinite loop (bot responding to its own messages)

---

#### FB-42: Duplicate WS message dedup

**Priority**: P1
**Steps**: Feishu WS redelivers same message event
**Expected**:
- Second delivery detected by `msg_id` in `_seen_msg_ids`
- Log: `[MSG] skip duplicate msg_id=...`
- No duplicate processing

---

#### FB-43: Rich text (post) message extraction

**Priority**: P2
**Steps**: Send rich text message (formatted text with bold/links)
**Expected**:
- Text extracted from post content blocks
- Forwarded to Claude as plain text

---

### H. Terminal State Detection (Bug Fix Verification)

#### FB-44: Accurate terminal status in /sessions

**Priority**: P0
**Steps**: 
1. Have a Claude terminal open in project X
2. Send `/sessions`
3. Verify session for project X shows 💻 terminal with accurate time
4. Close terminal
5. Send `/sessions` again
6. Verify session no longer shows 💻 terminal

**Expected**:
- 💻 terminal only when both conditions met: (a) cwd match found in /proc/*/cwd, (b) session JSONL mtime < 300s
- After closing terminal: no false 💻, shows plain idle time

---

#### FB-45: Disk session message delivery (no CrossMark)

**Priority**: P0
**Steps**:
1. `/link` to a disk-scanned session (not imported into server memory)
2. Send text message
**Expected**:
- No CrossMark ❌ error
- Message delivered via `claude --resume --print` fallback
- Claude response arrives normally

---

## Test Priority Summary

| Priority | Count | Must Pass |
|----------|-------|-----------|
| P0 | 20 | 100% |
| P1 | 16 | 80%+ |
| P2 | 4 | Best effort |
| **Total** | **40** | |

## Coverage Matrix

### By Input Type

| Input Type | Cases | Coverage |
|-----------|-------|----------|
| Text command (14 commands) | FB-01~21 | All commands + unknown |
| Text message (4 states) | FB-22~25 | All states |
| Card button (7 buttons) | FB-26~32 | All buttons |
| Response lifecycle | FB-33~37 | Working/Done/Dedup/Stale |
| Resilience/Security | FB-38~43 | Restart/Dedup/Auth/Injection |
| Bug fix verification | FB-44~45 | The 2 bugs we fixed |

### By Connection State

| State | Cases |
|-------|-------|
| Unlinked | FB-01, 04~07, 09~10, 12, 19~20, 22, 32 |
| Linked-Idle | FB-02, 08, 11, 13~14, 17~18, 23, 26~31, 33~36, 44~45 |
| Linked-Working | FB-16, 24, 33~34, 37 |
| Linked-Deleted | FB-25, 37 |
| Cross-state (resilience) | FB-38~43 |

### MECE Verification

Every user-facing behavior is covered by exactly one test case. Verification:

1. **Every /command** → FB-01 through FB-21 (14 commands + unknown)
2. **Every card button** → FB-26 through FB-32 (7 buttons)
3. **Text message in every state** → FB-22 through FB-25 (4 states)
4. **Every response stage** → FB-33 through FB-37 (4 stages)
5. **Every resilience scenario** → FB-38 through FB-43 (6 scenarios)
6. **Bug fix regression** → FB-44, FB-45

No overlap, no gaps.

---

## E2E Execution Notes

### Prerequisites
- Feishu bridge running (`feishu-bridge.py`)
- coa-dash server running (port 8890)
- Playwright MCP browser on Feishu chat (for browser-based tests)
- At least 2 Claude sessions on disk (for link tests)
- `allowed_chats` configured in `config/feishu-bridge.json`

### Test Sequence (optimal order)

```
Phase 1: Discovery (no side effects)
  FB-01 → FB-03 → FB-15 → FB-21 → FB-19

Phase 2: Connection (creates mappings)
  FB-09 → FB-04 → FB-02 → FB-14 → FB-18 → FB-13

Phase 3: Messaging (core flow)
  FB-23 → FB-33 → FB-34 → FB-35 → FB-22

Phase 4: Management (modifies sessions)
  FB-16 → FB-17 → FB-24 → FB-37

Phase 5: Card interactions
  FB-26 → FB-27 → FB-28 → FB-29 → FB-30 → FB-31 → FB-32

Phase 6: Resilience & Security
  FB-38 → FB-40 → FB-41 → FB-42 → FB-10 → FB-20 → FB-36 → FB-39

Phase 7: Regression (the 2 fixed bugs)
  FB-44 → FB-45
```

### Automated vs Manual

| Method | Cases | Tool |
|--------|-------|------|
| Playwright MCP (browser) | FB-01~05, 22~23, 26~27, 44~45 | `browser_run_code` with keyboard.type |
| curl (API) | FB-10, FB-14, FB-19~20, FB-40~41 | Server API directly |
| Bridge log inspection | FB-33~37, FB-38~39, FB-42 | `journalctl` / bridge stdout |
| Manual (requires timing) | FB-16, FB-24, FB-37 | Human observation |

---

## FB-46: Retained message — idle session

**Feature**: F12 (Retained Message Handling)
**Priority**: P0
**Method**: Bridge log inspection

### 前提
- Session 已 link
- Session status = idle（Claude 不在处理）
- 终端进程存在（isActiveInTerminal = true）

### 操作
1. 在飞书发文本消息（如 "test"）

### 预期
- Hourglass reaction（替换 Typing）
- 文本消息"⏳ 消息已排队，终端空闲后将自动处理"
- **不创建** working 卡片（无蓝色卡片）
- Bridge 日志：`[FWD→Retained] session=... message queued`
- Bridge 日志：**无** `[FWD→Card]` 输出

### 验证
```bash
journalctl --user -u feishu-bridge --since "30 sec ago" --no-pager | grep -E "FWD→Retained|FWD→Card"
```
应只有 `FWD→Retained`，没有 `FWD→Card`。

---

## FB-47: Working card timeout (pending implementation)

**Feature**: F13 (Working Card Timeout)
**Priority**: P1
**Method**: Bridge log inspection
**Status**: pending — 依赖 F10 Stale Detection 增强

### 前提
- Working 卡片已创建（session status = working）
- Claude 进程已死或卡住

### 操作
1. 创建 working 状态
2. 等待 5 分钟，期间 poll 一直看到 idle 且 messageCount 不变

### 预期（计划）
- Working 卡片变为黄色 "Claude (waiting)"
- 文本通知"⚠️ 响应超时，会话可能已卡住"
- SWEAT reaction

---

## FB-48: Restart management — path cache warmup + session validation

**Feature**: F14 (Restart Management)
**Priority**: P0
**Method**: Bridge log inspection

### 前提
- Bridge 和 coa-dash 均已运行
- 至少 1 个 session 已 link

### 操作
1. `systemctl --user restart coa-dash && sleep 2 && systemctl --user restart feishu-bridge && sleep 5`
2. 检查 bridge 启动日志

### 预期
- 日志包含 `[Bridge] Warmup: N sessions, path cache primed`（N > 0）
- 日志包含 `connected to wss://msg-frontier.feishu.cn/ws/v2`
- 日志**不包含** `[Bridge] Warmup failed` 或 `ERROR`
- 已 link session 的 cwd 正确解析（无 "Session has no working directory"）
- 飞书端发消息 → 正常收到回复卡片（非 CrossMark）

### 验证
```bash
# Warmup 成功
journalctl --user -u feishu-bridge --since "30 sec ago" --no-pager | grep "Warmup"
# 已 link session cwd 正确
curl -sf "localhost:8890/api/claudecode/available" | python3 -c "
import json,sys
d=json.load(sys.stdin)
no_cwd=[s for s in d.get('sessions',[]) if not s.get('cwd')]
print(f'missing cwd: {len(no_cwd)}')
"
```

### 额外场景：coa-dash 单独重启
1. `systemctl --user restart coa-dash && sleep 2`
2. 从飞书发消息 → 应正常工作（path cache auto-rebuild）

---

## FB-49: /model command — switch session model

**Feature**: F15 (Model Switching)
**Priority**: P0
**Method**: Feishu text + log inspection

### 前提
- Session 已 link
- Session status = idle

### 操作
1. 发 `/model`（无参数）
2. 在弹出卡片中点击 [sonnet]
3. 发 `/model opus`（直接切换）

### 预期
- 步骤 1：弹出卡片，header 显示当前 model，4 个按钮 [sonnet] [opus] [haiku] [default]
- 步骤 2：收到文本 "✅ Model set to sonnet"
- 步骤 3：收到文本 "✅ Model set to opus"
- 控制面板 `/help` 显示更新后的 model

### 验证
```bash
curl -sf "localhost:8890/api/claudecode/sessions/<SESSION_ID>" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(f'model={d.get(\"model\")}')"
```

---

## FB-50: [Model] card button on control panel

**Feature**: F15 (Model Switching)
**Priority**: P1
**Method**: Feishu card interaction

### 前提
- Session 已 link

### 操作
1. 发 `/help`（显示控制面板）
2. 点击 [Model] 按钮

### 预期
- 控制面板卡片有 6 个按钮：[Stop] [History] [Compact] [Model] [Unlink] [Sessions]
- 点击 [Model] 后弹出 model 选择卡片（同 FB-49）
- 面板状态行包含 `model: <current_model>`
