# GLM-5.1 Fix Bundle — COA-dash P1 Remediation

**Audience**: GLM-5.1 coding agent (Zhipu Max plan) invoked via separate CLI session.
**Input**: this file + repo checkout at `/home/aegis/vault/projects/coa-dash`.
**Prerequisite**: `backup-pre-audit-fix-2026-04-21` tag exists (git backup).
**Baseline**: P0 already fixed in 0.7.2 (Opus, 2026-04-21). Your work ships as **0.7.3**.

---

## Meta instructions — read first

1. **Do not** refactor beyond what each item specifies. Over-engineering is the project's biggest failure mode — the audit explicitly flagged it.
2. Each fix is independent. Do them in order, commit each one with the given commit message, push nothing until all 16 are done.
3. For every fix: read the cited `file:line-range`, understand the context (≥ 30 surrounding lines), then apply the minimal change.
4. After each group (A, B, C, D), run the smoke test block. If it fails, stop and report — do not "fix forward".
5. When a fix says "consolidate" or "extract helper", the helper goes in the same file near its first use, not a new module.
6. No new dependencies. Python stdlib only. Frontend: no new JS files.
7. All comments added must be ≤1 line and explain WHY (the attack / race / invariant), not WHAT.
8. Final deliverable: 16 commits (one per item, tagged `P1-01` … `P1-16`), + version bump to 0.7.3 + CHANGELOG entry.

---

## Group A — Server security (5 items)

### P1-01 · Cap request body size at 1 MiB
**Files**: `src/server.py` — every `do_POST` / `do_PUT` / `do_DELETE` handler that reads `self.rfile.read(content_length)`.
Approximate call-sites (verify by grep): 2567, 2586, 2600, 2638, 2667, 2681, 2693, 2706, 2719, 2736, 2755, 2955 (pre-0.7.2 numbers; may have shifted by ~20 lines).

**Fix**: extract a helper at the top of the handler class:
```python
_MAX_REQUEST_BODY = 1 * 1024 * 1024

def _read_body_capped(self):
    length = int(self.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > _MAX_REQUEST_BODY:
        self.send_response(413)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"error":"body too large"}')
        return None
    return self.rfile.read(length)
```

Replace every `body = self.rfile.read(int(self.headers.get("Content-Length", 0)))` with `body = self._read_body_capped(); if body is None: return`.

**Commit**: `fix(security): cap HTTP request body at 1 MiB (P1-01)`

---

### P1-02 · Thread-safe AgentConfigCache
**File**: `src/server.py` `AgentConfigCache` class (~line 56-69 pre-fix).

**Fix**: add `self._lock = threading.Lock()` in `__init__`; wrap `get_agents_list()` body in `with self._lock:`.

**Commit**: `fix(concurrency): guard AgentConfigCache with lock (P1-02)`

---

### P1-03 · Atomic sessions_metadata write
**File**: `src/server.py` `save_sessions_metadata` (~line 553-573 pre-fix).

**Fix**: inside the existing lock, write to `path + ".tmp"` then `os.replace(path + ".tmp", path)`. Keep the lock held until replace completes.

**Commit**: `fix(durability): atomic sessions metadata write (P1-03)`

---

### P1-04 · Atomic tasks.jsonl write (BIG — careful)
**File**: `src/server.py` — anywhere the tasks JSONL is rewritten. Grep for `with_jsonl_lock` and `f.truncate()` — there are 3-4 call-sites (update_task_priority, update_task_status, update_task_assignee, delete_task, batch status).

**Fix**: replace the `r+ + seek(0) + truncate + write` pattern with:
```python
tmp_path = path + ".tmp"
with open(tmp_path, "w") as f:
    for line in lines:
        f.write(line + "\n")
os.replace(tmp_path, path)
```
Keep the fcntl advisory lock held across this, acquired on the ORIGINAL file path (open it separately for locking).

**Verify**: run `python3 -c "import json; [json.loads(l) for l in open('/home/aegis/vault/tasks/tasks.jsonl')]"` before and after a task update — no exceptions.

**Commit**: `fix(durability): atomic tasks.jsonl rewrite (P1-04)`

---

### P1-05 · Robust json.loads in get_session_state
**File**: `src/server.py` `get_session_state` (~line 2244-2245 pre-fix).

**Fix**: wrap the per-line `json.loads` in `try/except json.JSONDecodeError: continue`. Log `print(f"[WARN] skipping bad tasks.jsonl line", flush=True)` once.

**Commit**: `fix(robustness): skip corrupted tasks.jsonl lines (P1-05)`

---

## Group A smoke test (run after 01-05)

```bash
systemctl --user restart coa-dash && sleep 2
curl -s -o /dev/null -w "%{http_code}\n" localhost:8890/api/agents    # 200
curl -s -o /dev/null -w "%{http_code}\n" -X POST \
  -H "Content-Length: 2000000" -d "$(python3 -c 'print("x"*2000000)')" \
  localhost:8890/api/tasks/foo/execute    # 413
curl -s localhost:8890/api/session-state | head -c 80    # JSON, not 500
```

All three must pass.

---

## Group B — Server input validation (3 items)

### P1-06 · Validate cwd_path in disk-session message path
**File**: `src/server.py` `_send_disk_session_message` (~line 1122-1139 pre-fix).

**Fix**: before launching Claude, check `if not cwd_path.startswith(ALLOWED_CWD_PREFIX): return {"error":"cwd not allowed"}`. Use the same constant already defined for `create_claude_session`.

**Commit**: `fix(security): enforce cwd allowlist in disk session send (P1-06)`

---

### P1-07 · Validate session_id + action in OpenCode proxy
**File**: `src/server.py` `proxy_opencode_request` (~line 2928-2941 pre-fix).

**Fix**:
- `session_id`: must match `^[A-Za-z0-9_-]{1,64}$` regex.
- `action`: must be in explicit allowlist `{"message", "abort", "revert", "share", "unshare"}` (adjust to match what endpoints exist).
- Reject with 400 otherwise.

**Commit**: `fix(security): whitelist OpenCode proxy params (P1-07)`

---

### P1-08 · Escape LIKE wildcards in OpenCode session filter
**File**: `src/server.py` line ~2173 pre-fix (`worktree_filter` SQLite LIKE).

**Fix**:
```python
def _escape_like(s): return s.replace("\\","\\\\").replace("%","\\%").replace("_","\\_")
sql = "... WHERE worktree LIKE ? ESCAPE '\\' ..."
params = (f"%{_escape_like(worktree_filter)}%",)
```

**Commit**: `fix(security): escape LIKE wildcards in opencode filter (P1-08)`

---

### P1-09 · Enum validation for task fields
**File**: `src/server.py` task PUT handlers.

**Fix**:
- `priority` ∈ `{"P0","P1","P2","P3","low","medium","high"}` (check what the code actually accepts; adjust)
- `status` ∈ `{"pending","in_progress","completed","deleted"}` (or actual enum)
- `task_id` must match `^[A-Za-z0-9_-]{1,64}$`

Return 400 on violation.

**Commit**: `fix(validation): enum-check task priority/status (P1-09)`

---

### P1-10 · Thread-safe path_cache in list_available_claude_sessions
**File**: `src/server.py` ~1203-1235 pre-fix.

**Fix**: replace function-attribute cache with module-level `_AVAILABLE_CACHE = {"ts":0, "data":None}` + `_AVAILABLE_CACHE_LOCK = threading.Lock()`. Hold lock across read+write.

**Commit**: `fix(concurrency): lock available sessions cache (P1-10)`

---

## Group B smoke test

```bash
systemctl --user restart coa-dash && sleep 2
curl -s "localhost:8890/api/opencode/sessions/%27/message" -X POST -d '{}'    # 400
curl -s -X PUT localhost:8890/api/tasks/notvalid/priority -d '{"priority":"wtf"}'    # 400
```

---

## Group C — Bridge state (4 items)

### P1-11 · Clear _response_cards on new user message
**File**: `src/feishu-bridge.py` `_forward_to_claude` (~line 988-996 pre-fix).

**Fix**: at the VERY TOP of `_forward_to_claude`, before the baseline GET:
```python
with self._lock:
    self._response_cards.pop(session_id, None)
```
This enforces "one card per user message" by discarding the previous round's card reference.

**Commit**: `fix(bridge): reset response card ref per user message (P1-11)`

---

### P1-12 · Lock around _seen_msg_ids
**File**: `src/feishu-bridge.py` ~line 314-322 pre-fix.

**Fix**: wrap the entire block (check `message_id in _seen_msg_ids`, add, prune) in `with self._lock:`.

**Commit**: `fix(bridge): lock _seen_msg_ids access (P1-12)`

---

### P1-13 · Lock around /link check-and-set
**File**: `src/feishu-bridge.py` `_cmd_link` ~line 477-479 pre-fix (B5 guard).

**Fix**: wrap the `if session_id in self._session_chat_map … self._session_chat_map[session_id] = chat_id` block in `with self._lock:`.

**Commit**: `fix(bridge): lock /link dual-chat race (P1-13)`

---

### P1-14 · Persist _response_cards across restart
**File**: `src/feishu-bridge.py` `_save_persistence` / `_load_persistence` (~line 177-189 pre-fix).

**Fix**:
- in `_save_persistence`: add `"response_cards": dict(self._response_cards)` to the saved JSON.
- in `_load_persistence`: restore `self._response_cards = data.get("response_cards", {})`.
- Do not persist `_last_delivered_hash` etc (those are legitimately transient).

**Commit**: `fix(bridge): persist response card map across restart (P1-14)`

---

## Group C smoke test

```bash
systemctl --user restart feishu-bridge && sleep 3
systemctl --user is-active feishu-bridge   # active
# Manual: send 2 messages in a row in a linked Feishu chat, confirm only 2 cards (not 3+)
```

---

## Group D — Frontend (2 items) — **SCOPE-DEFERRED 2026-04-21**

> **Do not execute.** Per `memory/project-scope-decision.md`, the COA-dash web dashboard is deprecated; short-term audit/fix work focuses on the Feishu bridge. P1-15 and P1-16 are documented below for historical completeness but are **backlog**, not part of the 0.7.3 ship.

### P1-15 · Remove onkeypress handlers (D1 violation) — DEFERRED
**File**: `src/index.html` lines 3724 and 4984 (approximately).
Web dashboard is deprecated; do not touch.

### P1-16 · Escape tool output in OpenCode renderer — DEFERRED
**File**: `src/index.html` — OpenCode message rendering functions.
Web dashboard is deprecated; do not touch.

---

## Group D smoke test — N/A (skipped per scope decision)

---

## Scope decision summary (2026-04-21)

- **In scope** for GLM-5.1 0.7.3 run: Groups A (P1-01..05), B (P1-06..10), C (P1-11..14). ~14 items.
- **Out of scope** (backlog): Group D (P1-15, P1-16).
- **Optional — check bridge dependency first**: P1-07 (OpenCode proxy), P1-08 (OpenCode LIKE), P1-09 (task enum). If bridge does not hit these endpoints, move to backlog too.

---

## Final steps

1. Bump `VERSION` → `0.7.3`
2. Bump `README.md` → `**Version**: 0.7.3`
3. Bump `CLAUDE.md` → `**Current Version**: 0.7.3`
4. Prepend to `CHANGELOG.md`:
   ```
   ## [0.7.3] - 2026-04-??

   ### Security
   - Cap request body at 1 MiB (P1-01)
   - Enforce cwd allowlist in disk-session send (P1-06)
   - Whitelist OpenCode proxy params (P1-07)       # if executed
   - Escape LIKE wildcards in SQLite filter (P1-08) # if executed
   - Enum-validate task priority/status (P1-09)    # if executed

   ### Fixed
   - Thread-safe agent/session caches (P1-02, P1-10)
   - Atomic metadata + tasks.jsonl writes (P1-03, P1-04)
   - Skip corrupted tasks.jsonl lines (P1-05)
   - Feishu bridge card lifecycle + session race fixes (P1-11..14)

   ### Deferred
   - Web frontend hardening (P1-15 onkeypress, P1-16 OpenCode XSS) — deprecated surface
   ```
5. Single `git push origin master` at the end.

---

## What is explicitly NOT in this bundle

- Bridge state refactor to `SessionState` object — needs design, not execution.
- Touch-target compliance sweep — UI design call, not mechanical.
- Removing duplicate `import subprocess` in bridge — harmless.
- `/proc` scan caching for `is_live` — performance, not correctness.
- Doc/API drift catch-up — humans should triage which endpoints to document.
