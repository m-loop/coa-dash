# E2E Test Cases for Claude Code Sync (v0.7.0)

## Overview

These test cases verify the bidirectional sync between:
- Terminal Claude session
- Dashboard web UI (mobile)

## Prerequisites

1. Server running at `http://localhost:8890`
2. At least one Claude session exists on disk
3. Chrome DevTools or Playwright for testing

---

## Test Case 1: Import and Load Session

**Purpose:** Verify session loads with correct message count and recent messages

**Steps:**
1. Open `http://localhost:8890` in mobile viewport (390x844)
2. Click "Claude" tab
3. Click "Import" button
4. Select a project from the list
5. Click "Import" on the session card
6. Click on the imported session to open conversation

**Expected Results:**
- [ ] Import modal shows projects grouped by name (not all sessions)
- [ ] Imported session shows correct message count (matches file)
- [ ] Conversation view opens with messages visible
- [ ] User messages display actual text (not "[object Object]" or empty)
- [ ] Last 50 messages are loaded

**How to verify in DevTools:**
```javascript
// In Console, check session data
const session = await fetch('/api/claudecode/sessions').then(r => r.json());
console.log('Sessions:', session.sessions);

// Check history
const history = await fetch('/api/claudecode/sessions/YOUR_SESSION_ID/history?limit=10').then(r => r.json());
console.log('History count:', history.messages.length);
console.log('Last user msg:', history.messages.filter(m => m.type === 'user').pop());
```

---

## Test Case 2: Real-time File Watcher

**Purpose:** Verify messages from external Claude session sync to dashboard

**Steps:**
1. Import a Claude session in dashboard
2. Open the conversation view
3. In a separate terminal, send a message to the same Claude session:
   ```bash
   claude --resume <session_id> -p "Test message from terminal at $(date)"
   ```
4. Wait 2 seconds
5. Check dashboard for the new message

**Expected Results:**
- [ ] New message appears in dashboard within 2 seconds
- [ ] Status indicator shows "working" while processing
- [ ] Status returns to "idle" when complete

**How to verify in DevTools:**
```javascript
// Monitor SSE events
const es = new EventSource('/api/claudecode/sessions/YOUR_SESSION_ID/stream');
es.addEventListener('message', (e) => console.log('SSE message:', JSON.parse(e.data)));
es.addEventListener('status', (e) => console.log('SSE status:', JSON.parse(e.data)));
```

---

## Test Case 3: Dashboard to Terminal Sync

**Purpose:** Verify messages sent from dashboard appear in terminal Claude session

**Steps:**
1. Import a Claude session in dashboard
2. Open conversation view
3. Type a unique message (e.g., "Test from dashboard at 2024-01-01 12:00:00")
4. Click Send
5. In terminal, check the Claude session file:
   ```bash
   grep "Test from dashboard" ~/.claude/projects/*/SESSION_ID.jsonl
   ```
6. Or resume the session in terminal and check history

**Expected Results:**
- [ ] Message is sent to Claude API (check Network tab)
- [ ] Status shows "working" immediately
- [ ] Claude response appears in dashboard
- [ ] Message is written to Claude session file
- [ ] Message visible when resuming in terminal

**How to verify in DevTools:**
```javascript
// Check Network tab for POST to /api/claudecode/sessions/ID/message
// Response should include { success: true }

// Check if message was added
const history = await fetch('/api/claudecode/sessions/YOUR_SESSION_ID/history?limit=5').then(r => r.json());
const lastUserMsg = history.messages.filter(m => m.type === 'user').pop();
console.log('Last user message:', lastUserMsg?.message?.content);
```

---

## Test Case 4: Processing Indicator

**Purpose:** Verify UI shows feedback during processing

**Steps:**
1. Open a conversation in dashboard
2. Send a message that requires tool use (e.g., "list files in current directory")
3. Observe the UI during processing

**Expected Results:**
- [ ] Yellow processing bar appears at top
- [ ] Spinner shows in working indicator
- [ ] Status badge shows "working" with activity text
- [ ] Activity text updates (e.g., "Tool: Bash")
- [ ] Indicators disappear when done

**How to verify in DevTools:**
```javascript
// Check for processing elements in DOM
document.querySelector('.claude-processing-bar') !== null; // Should be true when working
document.querySelector('.claude-working-indicator') !== null; // Should be true when working
document.querySelector('.claude-conversation-status.working') !== null; // Should be true when working
```

---

## Test Case 5: SSE Connection and Reconnection

**Purpose:** Verify SSE handles disconnects gracefully

**Steps:**
1. Open conversation view
2. In DevTools Network tab, find the SSE connection (`/stream`)
3. Close and reopen the browser tab
4. Check if SSE reconnects

**Expected Results:**
- [ ] SSE connection established on conversation open
- [ ] Keep-alive comments sent every 30 seconds
- [ ] Connection reconnects after page refresh
- [ ] No error messages in console

**How to verify in DevTools:**
```javascript
// Check SSE connection state
// Network tab → EventStream tab should show events

// Monitor connection
let eventCount = 0;
const es = new EventSource('/api/claudecode/sessions/YOUR_SESSION_ID/stream');
es.onopen = () => console.log('SSE connected');
es.onerror = (e) => console.log('SSE error:', e);
es.addEventListener('init', () => eventCount++);
```

---

## Test Case 6: Multiple Sessions Same Project

**Purpose:** Verify session list shows correct grouping

**Steps:**
1. Have multiple Claude sessions in the same project
2. Import one session
3. Check session list

**Expected Results:**
- [ ] Session list shows one card per project
- [ ] Shows the most recent session's info
- [ ] Shows session count badge if >1 session
- [ ] Import modal still shows all sessions grouped by project

---

## Test Case 7: Session Persistence After Restart

**Purpose:** Verify sessions recover after server restart

**Steps:**
1. Import a session
2. Restart the server: `systemctl --user restart coa-dash`
3. Refresh the page
4. Check session list

**Expected Results:**
- [ ] Session appears in list after restart
- [ ] Message count is correct (reads from Claude file)
- [ ] History loads correctly
- [ ] claudeSessionId is preserved

**How to verify in DevTools:**
```javascript
// Check metadata file
// In terminal: cat ~/.claude/coa-dash-sessions.json

// Check if session recovered correctly
const sessions = await fetch('/api/claudecode/sessions').then(r => r.json());
const recovered = sessions.sessions.find(s => s.name === 'your-session-name');
console.log('Recovered session:', recovered);
console.log('Has claudeSessionId:', recovered?.claudeSessionId !== null);
```

---

## Test Case 8: Error Handling

**Purpose:** Verify graceful error handling

**Steps:**
1. Try to send a message when Claude session is busy
2. Try to import a non-existent session
3. Check error states

**Expected Results:**
- [ ] Error toast appears for failed operations
- [ ] Status shows "error" when appropriate
- [ ] No JavaScript console errors
- [ ] UI remains responsive

---

## Debug Commands

### Check file watcher status
```bash
# Check if file watcher is running
journalctl --user -u coa-dash -f | grep -i watcher
```

### Check SSE connection
```bash
# Test SSE endpoint
curl -N http://localhost:8890/api/claudecode/sessions/SESSION_ID/stream
```

### Check session file for new messages
```bash
# Watch file for changes
tail -f ~/.claude/projects/*/SESSION_ID.jsonl | jq -c '{type, timestamp}'
```

### Check message sync
```bash
# Count messages in file vs API
wc -l ~/.claude/projects/*/SESSION_ID.jsonl
curl -s http://localhost:8890/api/claudecode/sessions/ID | jq '.messageCount'
```

---

## Known Issues

1. **Race condition:** Both terminal and dashboard writing to same file can cause conflicts
2. **Timeout:** Dashboard send_message has 120s timeout, may not be enough for long operations
3. **File watcher interval:** 500ms may miss rapid file changes

## Test Automation

Run all tests with Playwright:
```bash
node scripts/e2e-playwright.js
```

For manual testing, use Chrome DevTools with mobile emulation (390x844).