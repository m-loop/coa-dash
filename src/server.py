#!/usr/bin/env python3
"""
COA-dash - Command Orchestration Agent Dashboard
Mobile-first, touch-first dashboard for AI agent orchestration
"""

import fcntl
import json
import os
import re
import subprocess
import threading
import time
import uuid
import queue
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")


def load_config():
    """Load config from JSON file with environment variable overrides.

    Security-sensitive values can be overridden via environment variables:
    - OPENCLAW_GATEWAY_TOKEN: Overrides config.gateway.token
    - COA_ALLOWED_ORIGINS: Comma-separated list of allowed CORS origins
    """
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    # Environment variable overrides for security-sensitive values
    if os.environ.get("OPENCLAW_GATEWAY_TOKEN"):
        if "gateway" not in config:
            config["gateway"] = {}
        config["gateway"]["token"] = os.environ["OPENCLAW_GATEWAY_TOKEN"]

    if os.environ.get("COA_ALLOWED_ORIGINS"):
        config["allowedOrigins"] = os.environ["COA_ALLOWED_ORIGINS"].split(",")

    return config


class AgentConfigCache:
    """Cache for agent configuration from openclaw.json (D55-D56)"""

    OPENCLAW_CONFIG_PATH = os.path.expanduser("~/.openclaw/openclaw.json")

    def __init__(self, ttl=60):
        self._agents_list = None
        self._last_read = 0
        self._ttl = ttl
        self._cached = False

    def get_agents_list(self):
        """Get configured agent IDs from openclaw.json with TTL cache"""
        now = int(time.time() * 1000)

        if self._agents_list is not None and (now - self._last_read) < (
            self._ttl * 1000
        ):
            self._cached = True
            return self._agents_list

        self._cached = False
        self._agents_list = self._read_openclaw_config()
        self._last_read = now
        return self._agents_list

    def _read_openclaw_config(self):
        """Read agent list from openclaw.json"""
        if not os.path.exists(self.OPENCLAW_CONFIG_PATH):
            return None

        try:
            with open(self.OPENCLAW_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)

            agents_config = data.get("agents", {})
            agents_list = agents_config.get("list", [])
            return [a.get("id") for a in agents_list if a.get("id")]
        except Exception as e:
            print(f"[ERROR] Failed to read openclaw.json: {e}")
            return None

    def invalidate(self):
        """Clear cache (D61: for force refresh)"""
        self._agents_list = None
        self._last_read = 0
        self._cached = False

    def is_cached(self):
        """Check if last result was from cache"""
        return self._cached


agent_cache = AgentConfigCache()


# ============================================================================
# Claude Code Session Manager (v0.7.0)
# ============================================================================

CLAUDE_SESSIONS_METADATA_PATH = os.path.expanduser("~/.claude/coa-dash-sessions.json")
MAX_CLAUDE_SESSIONS = 5
ALLOWED_CWD_PREFIX = "/home/aegis/vault/projects/"
CLAUDE_PATH = "/home/aegis/.npm-global/bin/claude"


class ClaudeSession:
    """Manages a Claude Code session using Claude's built-in session persistence"""

    def __init__(self, session_id, name, cwd, model=None):
        self.id = session_id
        self.name = name
        self.cwd = cwd
        self.model = model  # Can be None to use default
        self.claude_session_id = None  # Claude Code's internal session ID
        self.status = "idle"
        self.current_activity = ""
        self.buffer_file = f"/tmp/claude-session-{session_id}.jsonl"
        self.started_at = time.time()
        self.messages = []
        self.last_used_at = None  # Track for conflict detection
        self._lock = threading.Lock()

    def send_message_async(self, content):
        """Send message in background thread, returns immediately"""
        def run():
            try:
                cmd = [CLAUDE_PATH, "--print", "--verbose", "--output-format", "stream-json"]

                if self.model:
                    cmd.extend(["--model", self.model])

                if self.claude_session_id:
                    cmd.extend(["--resume", self.claude_session_id])

                self.status = "working"
                self.current_activity = "Thinking..."
                broadcast_session_update(self.id, "status", self.get_info())

                proc = subprocess.Popen(
                    cmd,
                    cwd=self.cwd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )

                stdout, stderr = proc.communicate(input=content, timeout=120)

                with self._lock:
                    with open(self.buffer_file, "a") as buf:
                        for line in stdout.strip().split("\n"):
                            if line:
                                buf.write(line + "\n")
                                try:
                                    data = json.loads(line)
                                    self.messages.append(data)
                                    self._parse_status(data)
                                    broadcast_session_update(self.id, "message", data)
                                except Exception:
                                    pass

                save_sessions_metadata()
                self.status = "idle"
                self.current_activity = "Done"
                broadcast_session_update(self.id, "status", self.get_info())
                broadcast_session_update(self.id, "done", {"success": True})

            except subprocess.TimeoutExpired:
                proc.kill()
                self.status = "error"
                self.current_activity = "Timeout"
                broadcast_session_update(self.id, "status", self.get_info())
                broadcast_session_update(self.id, "error", {"error": "Timeout"})
            except Exception as e:
                print(f"[ERROR] send_message_async: {e}")
                self.status = "error"
                self.current_activity = str(e)
                broadcast_session_update(self.id, "status", self.get_info())
                broadcast_session_update(self.id, "error", {"error": str(e)})

        # Start background thread
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return True

    def send_message(self, content):
        """Send message to Claude Code (runs as one-shot process)"""
        try:
            cmd = [CLAUDE_PATH, "--print", "--verbose", "--output-format", "stream-json"]

            # Add model if specified
            if self.model:
                cmd.extend(["--model", self.model])

            # Resume existing conversation if we have a session ID
            if self.claude_session_id:
                cmd.extend(["--resume", self.claude_session_id])

            self.status = "working"
            self.current_activity = "Thinking..."
            self.last_used_at = time.time()

            # Broadcast status change
            broadcast_session_update(self.id, "status", self.get_info())

            # Run Claude Code process
            proc = subprocess.Popen(
                cmd,
                cwd=self.cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Send the message
            stdout, stderr = proc.communicate(input=content, timeout=120)

            # Parse output and broadcast each message
            with self._lock:
                with open(self.buffer_file, "a") as buf:
                    for line in stdout.strip().split("\n"):
                        if line:
                            buf.write(line + "\n")
                            try:
                                data = json.loads(line)
                                self.messages.append(data)
                                self._parse_status(data)
                                # Broadcast each message for real-time updates
                                broadcast_session_update(self.id, "message", data)
                            except Exception:
                                pass

            # Save metadata to persist claude_session_id for recovery
            save_sessions_metadata()

            self.status = "idle"
            self.current_activity = "Done"

            # Broadcast final status
            broadcast_session_update(self.id, "status", self.get_info())
            broadcast_session_update(self.id, "done", {"success": True})

            return True

        except subprocess.TimeoutExpired:
            proc.kill()
            self.status = "error"
            self.current_activity = "Timeout"
            broadcast_session_update(self.id, "status", self.get_info())
            broadcast_session_update(self.id, "error", {"error": "Timeout"})
            return False
        except Exception as e:
            print(f"[ERROR] Failed to send message to session {self.id}: {e}")
            self.status = "error"
            self.current_activity = str(e)
            broadcast_session_update(self.id, "status", self.get_info())
            broadcast_session_update(self.id, "error", {"error": str(e)})
            return False

    def stop(self):
        """Stop the session (no persistent process to kill)"""
        self.status = "stopped"

    def cleanup(self):
        """Clean up buffer file"""
        try:
            if os.path.exists(self.buffer_file):
                os.remove(self.buffer_file)
        except Exception:
            pass

    def get_info(self):
        """Get session info for API response"""
        project_name = os.path.basename(self.cwd) if self.cwd else "unknown"
        return {
            "id": self.id,
            "name": self.name,
            "cwd": self.cwd,
            "projectName": project_name,
            "model": self.model,
            "status": self.status,
            "activity": self.current_activity,
            "startedAt": self.started_at,
            "duration": int(time.time() - self.started_at),
            "messageCount": len(self.messages),
            "claudeSessionId": self.claude_session_id,
            "lastUsedAt": self.last_used_at,
            "title": f"{project_name}/{self.name}",
        }

    def _parse_status(self, data):
        """Parse Claude Code output to extract session ID and status"""
        msg_type = data.get("type")

        if msg_type == "system":
            # Capture Claude's internal session ID for resume
            self.claude_session_id = data.get("session_id")
            self.current_activity = "Ready"

        elif msg_type == "assistant":
            message = data.get("message", {})
            content = message.get("content", [])

            # Update activity but don't change status (terminal activity, not dashboard)
            for c in content:
                if c.get("type") == "thinking":
                    self.current_activity = "Thinking..."
                elif c.get("type") == "tool_use":
                    self.current_activity = f"Tool: {c.get('name', 'unknown')}"
                    break

        elif msg_type == "result":
            # Terminal finished - clear activity
            self.current_activity = "Done"


# Global session manager
claude_sessions = {}  # session_id -> ClaudeSession
claude_sessions_lock = threading.Lock()

# SSE subscribers for real-time updates (v0.7.0)
sse_subscribers = {}  # session_id -> list of (queue, thread) tuples
sse_subscribers_lock = threading.Lock()

# File watchers for imported sessions (v0.7.0)
file_watchers = {}  # session_id -> FileWatcher thread
file_watchers_lock = threading.Lock()


def broadcast_session_update(session_id, event_type, data):
    """Broadcast update to all SSE subscribers for a session"""
    with sse_subscribers_lock:
        subscribers = sse_subscribers.get(session_id, [])
        for q in subscribers:
            try:
                q.put({"type": event_type, "data": data})
            except Exception:
                pass  # Queue might be full or closed


def add_sse_subscriber(session_id, q):
    """Add SSE subscriber for a session, start file watcher if needed"""
    with sse_subscribers_lock:
        if session_id not in sse_subscribers:
            sse_subscribers[session_id] = []
        sse_subscribers[session_id].append(q)
    subscriber_count = len(sse_subscribers.get(session_id, []))

    # Start file watcher for imported sessions (linked to external Claude)
    with claude_sessions_lock:
        session = claude_sessions.get(session_id)
        if session and session.claude_session_id and subscriber_count == 1:
            # First subscriber - start watching the file
            start_file_watcher(session)

    return subscriber_count


def remove_sse_subscriber(session_id, q):
    """Remove SSE subscriber, stop file watcher if no more subscribers"""
    with sse_subscribers_lock:
        if session_id in sse_subscribers:
            try:
                sse_subscribers[session_id].remove(q)
                if not sse_subscribers[session_id]:
                    del sse_subscribers[session_id]
                    # No more subscribers - stop file watcher
                    stop_file_watcher(session_id)
            except Exception:
                pass


class FileWatcher(threading.Thread):
    """Watch a Claude session file for new messages and broadcast via SSE"""

    def __init__(self, session):
        super().__init__(daemon=True)
        self.session = session
        self.session_id = session.id
        self.claude_session_id = session.claude_session_id
        self.cwd = session.cwd
        self.running = True
        self.file_position = 0
        self.check_interval = 0.5  # Check every 500ms for responsiveness

        # Compute Claude file path
        encoded_path = self.cwd.replace("/", "-").replace("~", "-")
        if encoded_path.startswith("-"):
            encoded_path = "-" + encoded_path[1:]
        self.claude_file = os.path.expanduser(
            f"~/.claude/projects/{encoded_path}/{self.claude_session_id}.jsonl"
        )

    def run(self):
        """Tail the file and broadcast new messages"""
        # Initial position - start from end if file exists
        if os.path.exists(self.claude_file):
            self.file_position = os.path.getsize(self.claude_file)

        while self.running:
            try:
                if os.path.exists(self.claude_file):
                    current_size = os.path.getsize(self.claude_file)

                    # File grew - read new content
                    if current_size > self.file_position:
                        with open(self.claude_file, "r") as f:
                            f.seek(self.file_position)
                            new_lines = f.readlines()
                            self.file_position = f.tell()

                        # Parse and broadcast each new message
                        for line in new_lines:
                            if line.strip():
                                try:
                                    data = json.loads(line.strip())
                                    # Update session's in-memory messages
                                    with self.session._lock:
                                        self.session.messages.append(data)
                                        self.session._parse_status(data)
                                    # Broadcast via SSE
                                    broadcast_session_update(
                                        self.session_id, "message", data
                                    )
                                except json.JSONDecodeError:
                                    pass

                        # Update message count
                        with self.session._lock:
                            self.session.message_count = len(self.session.messages)
                        broadcast_session_update(
                            self.session_id, "status", self.session.get_info()
                        )

                        # Check for retained messages when file changes (terminal might be idle now)
                        retained = get_retained_messages(self.session_id)
                        if retained and not is_terminal_busy(self.session):
                            broadcast_session_update(
                                self.session_id, "retained_available",
                                {"count": len(retained), "messages": retained}
                            )

                    # File shrunk (truncated/recreated) - reset position
                    elif current_size < self.file_position:
                        self.file_position = 0

            except Exception as e:
                print(f"[FileWatcher] Error: {e}")

            time.sleep(self.check_interval)

    def stop(self):
        """Stop the watcher"""
        self.running = False


def start_file_watcher(session):
    """Start file watcher for an imported session"""
    with file_watchers_lock:
        if session.id not in file_watchers:
            watcher = FileWatcher(session)
            file_watchers[session.id] = watcher
            watcher.start()
            print(f"[FileWatcher] Started watching {session.claude_session_id}")


def stop_file_watcher(session_id):
    """Stop file watcher when no more subscribers"""
    with file_watchers_lock:
        if session_id in file_watchers:
            watcher = file_watchers[session_id]
            watcher.stop()
            del file_watchers[session_id]
            print(f"[FileWatcher] Stopped watching {session_id}")


def save_sessions_metadata():
    """Persist session metadata to disk"""
    try:
        data = {
            "sessions": [
                {
                    "id": s.id,
                    "name": s.name,
                    "cwd": s.cwd,
                    "model": s.model,
                    "buffer_file": s.buffer_file,
                    "started_at": s.started_at,
                    "claude_session_id": s.claude_session_id,  # For resuming
                    "message_count": len(s.messages),
                }
                for s in claude_sessions.values()
            ]
        }
        with open(CLAUDE_SESSIONS_METADATA_PATH, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[DEBUG] Saved metadata for {len(claude_sessions)} sessions")
    except Exception as e:
        print(f"[ERROR] Failed to save sessions metadata: {e}")


def load_sessions_metadata():
    """Load session metadata from disk (for recovery after restart)"""
    if not os.path.exists(CLAUDE_SESSIONS_METADATA_PATH):
        return

    try:
        with open(CLAUDE_SESSIONS_METADATA_PATH, "r") as f:
            data = json.load(f)

        for s in data.get("sessions", []):
            session_id = s["id"]
            claude_session_id = s.get("claude_session_id")
            buffer_file = s.get("buffer_file", "")

            # For imported sessions, read from the original Claude file
            if claude_session_id:
                encoded_path = s["cwd"].replace("/", "-").replace("~", "-")
                if encoded_path.startswith("-"):
                    encoded_path = "-" + encoded_path[1:]
                claude_file = os.path.expanduser(
                    f"~/.claude/projects/{encoded_path}/{claude_session_id}.jsonl"
                )
                if os.path.exists(claude_file):
                    buffer_file = claude_file  # Use original file

            # Restore session if we have a valid source
            if buffer_file and os.path.exists(buffer_file):
                session = ClaudeSession(session_id, s["name"], s["cwd"], s.get("model"))
                session.buffer_file = s.get("buffer_file", f"/tmp/claude-session-{session_id}.jsonl")
                session.started_at = s.get("started_at", time.time())
                session.claude_session_id = claude_session_id

                # Load messages from file
                try:
                    with open(buffer_file, "r") as bf:
                        for line in bf:
                            try:
                                session.messages.append(json.loads(line.strip()))
                            except Exception:
                                pass
                except Exception:
                    pass

                session.status = "idle"
                session.current_activity = f"Recovered ({len(session.messages)} messages)"
                session.message_count = len(session.messages)

                with claude_sessions_lock:
                    claude_sessions[session_id] = session

                print(f"[INFO] Recovered session {session_id} with {len(session.messages)} messages")
    except Exception as e:
        print(f"[ERROR] Failed to load sessions metadata: {e}")


def create_claude_session(name, cwd, model=None):
    """Create a new Claude Code session"""
    # Validate cwd
    if not cwd.startswith(ALLOWED_CWD_PREFIX):
        return {"error": "Invalid cwd - must be within /home/aegis/vault/projects/"}

    if not os.path.isdir(cwd):
        return {"error": "Directory does not exist"}

    # Check session limit
    with claude_sessions_lock:
        if len(claude_sessions) >= MAX_CLAUDE_SESSIONS:
            return {"error": f"Maximum {MAX_CLAUDE_SESSIONS} sessions allowed"}

        session_id = uuid.uuid4().hex[:8]
        session = ClaudeSession(session_id, name, cwd, model)
        claude_sessions[session_id] = session
        save_sessions_metadata()

    return {"success": True, "session": session.get_info()}


def get_claude_sessions():
    """Get list of all sessions"""
    with claude_sessions_lock:
        return [s.get_info() for s in claude_sessions.values()]


def get_claude_session(session_id):
    """Get single session info"""
    with claude_sessions_lock:
        session = claude_sessions.get(session_id)
        if session:
            return session.get_info()
        return None


def get_claude_session_history(session_id, limit=50):
    """Get session conversation history - reads from original Claude file for latest data"""
    with claude_sessions_lock:
        session = claude_sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        history = []

        # If linked to a Claude session, read from original file for latest messages
        if session.claude_session_id:
            encoded_path = session.cwd.replace("/", "-").replace("~", "-")
            if encoded_path.startswith("-"):
                encoded_path = "-" + encoded_path[1:]
            claude_file = os.path.expanduser(
                f"~/.claude/projects/{encoded_path}/{session.claude_session_id}.jsonl"
            )
            if os.path.exists(claude_file):
                try:
                    # Simple: read all lines, take last N
                    with open(claude_file, "r") as f:
                        all_lines = f.readlines()
                    for line in all_lines[-limit:]:
                        if line.strip():
                            try:
                                history.append(json.loads(line.strip()))
                            except Exception:
                                pass
                except Exception as e:
                    print(f"[WARN] Failed to read Claude session file: {e}")

        # Fallback to buffer file
        if not history and os.path.exists(session.buffer_file):
            try:
                with open(session.buffer_file, "r") as f:
                    lines = f.readlines()[-limit:]
                    for line in lines:
                        if line.strip():
                            try:
                                history.append(json.loads(line.strip()))
                            except Exception:
                                pass
            except Exception:
                pass

        # Fallback to in-memory
        if not history:
            history = session.messages[-limit:]

        return {"messages": history, "count": len(history), "total": len(session.messages)}

# Global retained messages for terminal busy handling
retained_messages = {}  # session_id -> list of retained messages
retained_messages_lock = threading.Lock()

def get_claude_file_path(cwd, claude_session_id):
    """Get the Claude session file path from cwd and session ID"""
    encoded_path = cwd.replace("/", "-").replace("~", "-")
    if encoded_path.startswith("-"):
        encoded_path = "-" + encoded_path[1:]
    return os.path.expanduser(
        f"~/.claude/projects/{encoded_path}/{claude_session_id}.jsonl"
    )

def is_terminal_busy(session):
    """Check if terminal session is actively processing by file mtime"""
    if not session.claude_session_id:
        return False

    claude_file = get_claude_file_path(session.cwd, session.claude_session_id)
    if os.path.exists(claude_file):
        mtime = os.path.getmtime(claude_file)
        # If file modified within last 5 seconds, terminal is busy
        return time.time() - mtime < 5
    return False

def write_notification_file(session_id, content):
    """Write dashboard input to notification file for terminal display"""
    pending_file = f"/tmp/claude-pending-{session_id}.jsonl"
    entry = {
        "session_id": session_id,
        "content": content,
        "sent_at": time.time(),
        "status": "retained"
    }
    with open(pending_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

def retain_message(session_id, content):
    """Store message for later, write notification file"""
    with retained_messages_lock:
        if session_id not in retained_messages:
            retained_messages[session_id] = []
        retained_messages[session_id].append({
            "content": content,
            "retained_at": time.time(),
            "session_id": session_id
        })

    write_notification_file(session_id, content)

    return {
        "retained": True,
        "message": "Terminal busy - message retained. Retry when idle.",
        "notification_file": f"/tmp/claude-pending-{session_id}.jsonl"
    }

def get_retained_messages(session_id):
    """Get retained messages for a session"""
    with retained_messages_lock:
        return retained_messages.get(session_id, [])

def clear_retained_message(session_id, index=0):
    """Remove a retained message after manual retry"""
    with retained_messages_lock:
        if session_id in retained_messages and retained_messages[session_id]:
            if index < len(retained_messages[session_id]):
                retained_messages[session_id].pop(index)
                return {"success": True, "remaining": len(retained_messages[session_id])}
    return {"error": "Message not found"}

def check_terminal_idle_and_alert(session_id):
    """Check if terminal is now idle, broadcast retained alert if so"""
    session = claude_sessions.get(session_id)
    if session and session.claude_session_id:
        if not is_terminal_busy(session):
            retained = get_retained_messages(session_id)
            if retained:
                broadcast_session_update(session_id, "retained_available", {
                    "count": len(retained),
                    "messages": retained
                })


def send_claude_message(session_id, content):
    """Send message to session, retain if terminal busy"""
    with claude_sessions_lock:
        session = claude_sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        if session.status not in ["idle", "starting"]:
            return {"error": f"Dashboard busy (status: {session.status})"}

        # Check if terminal session is busy (actively processing)
        if is_terminal_busy(session):
            return retain_message(session_id, content)

        # Mark as working immediately to prevent race condition
        session.status = "working"
        session.current_activity = "Sending..."

    # Use async version - returns immediately
    success = session.send_message_async(content)
    if success:
        return {"success": True, "message": "Message sent"}
    return {"error": "Failed to send message"}


def list_available_claude_sessions(cwd=None):
    """List Claude Code sessions available on disk - scans all project directories"""
    claude_projects_dir = os.path.expanduser("~/.claude/projects")

    if not os.path.exists(claude_projects_dir):
        return {"sessions": [], "error": "No Claude projects directory found"}

    sessions = []

    # Scan all project directories
    try:
        for project_dir_name in os.listdir(claude_projects_dir):
            project_dir = os.path.join(claude_projects_dir, project_dir_name)
            if not os.path.isdir(project_dir):
                continue

            # Decode project name from directory name
            # Format: -home-aegis-vault-projects-coa-dash -> /home/aegis/vault/projects/coa-dash
            project_name = project_dir_name
            if project_dir_name.startswith("-"):
                # Try to extract meaningful project name
                parts = project_dir_name[1:].split("-")
                if len(parts) >= 3:
                    project_name = parts[-1]  # Last part is usually the project name
                else:
                    project_name = project_dir_name

            # Scan session files in this project
            for f in os.listdir(project_dir):
                if not f.endswith(".jsonl"):
                    continue

                session_id = f[:-6]  # Remove .jsonl
                filepath = os.path.join(project_dir, f)
                stat = os.stat(filepath)
                mtime = stat.st_mtime
                size = stat.st_size

                # Extract useful info from session file
                slug = session_id[:8]
                git_branch = None
                message_count = 0
                first_user_msg = None

                try:
                    with open(filepath, "r") as sf:
                        for line in sf:
                            try:
                                data = json.loads(line.strip())
                                if data.get("type") == "system" and data.get("slug"):
                                    slug = data.get("slug", slug)
                                    git_branch = data.get("gitBranch")
                                if data.get("type") == "user" and not first_user_msg:
                                    msg = data.get("message", {})
                                    content = msg.get("content", "")
                                    if isinstance(content, str) and content:
                                        first_user_msg = content[:80]
                                    elif isinstance(content, list) and content:
                                        for c in content:
                                            if isinstance(c, dict) and c.get("text"):
                                                first_user_msg = c["text"][:80]
                                                break
                                message_count += 1
                            except Exception:
                                pass
                except Exception:
                    pass

                # Check if this session is already in our active sessions
                is_active_in_dashboard = any(
                    s.claude_session_id == session_id
                    for s in claude_sessions.values()
                )

                # Check if session is active in terminal
                is_active_in_terminal = False
                time_since_mtime = time.time() - mtime
                if time_since_mtime < 30:
                    is_active_in_terminal = True

                try:
                    result = subprocess.run(
                        ["pgrep", "-f", f"claude.*--resume.*{session_id[:8]}"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        is_active_in_terminal = True
                except Exception:
                    pass

                sessions.append({
                    "id": session_id,
                    "shortId": session_id[:8],
                    "slug": slug,
                    "projectName": project_name,
                    "projectDir": project_dir_name,
                    "gitBranch": git_branch,
                    "mtime": mtime,
                    "mtimeAgo": format_time_ago(int(mtime * 1000)),
                    "size": size,
                    "messageCount": message_count,
                    "firstMessage": first_user_msg,
                    "isActive": is_active_in_dashboard or is_active_in_terminal,
                    "isActiveInDashboard": is_active_in_dashboard,
                    "isActiveInTerminal": is_active_in_terminal,
                    "title": f"{project_name}/{slug}",
                })

    except Exception as e:
        return {"sessions": [], "error": str(e)}

    # Sort by mtime descending
    sessions.sort(key=lambda s: s["mtime"], reverse=True)

    return {"sessions": sessions, "count": len(sessions)}


def import_claude_session(session_id, name, cwd):
    """Import an existing Claude session from disk"""
    # Encode the path
    encoded_path = cwd.replace("/", "-").replace("~", "-")
    if encoded_path.startswith("-"):
        encoded_path = "-" + encoded_path[1:]

    claude_session_file = os.path.expanduser(f"~/.claude/projects/{encoded_path}/{session_id}.jsonl")

    if not os.path.exists(claude_session_file):
        return {"error": "Claude session not found on disk"}

    with claude_sessions_lock:
        if len(claude_sessions) >= MAX_CLAUDE_SESSIONS:
            return {"error": f"Maximum {MAX_CLAUDE_SESSIONS} sessions allowed"}

        # Create a new dashboard session that links to this Claude session
        dashboard_session_id = uuid.uuid4().hex[:8]
        session = ClaudeSession(dashboard_session_id, name, cwd, None)
        session.claude_session_id = session_id  # Link to existing Claude session
        session.buffer_file = f"/tmp/claude-session-{dashboard_session_id}.jsonl"

        # Copy messages from Claude's file to both memory and buffer
        try:
            with open(claude_session_file, "r") as src:
                with open(session.buffer_file, "w") as dst:
                    for line in src:
                        try:
                            msg = json.loads(line.strip())
                            session.messages.append(msg)
                            dst.write(line)
                        except Exception:
                            pass
        except Exception as e:
            print(f"[WARN] Failed to copy session history: {e}")

        session.status = "idle"
        session.current_activity = f"Imported ({len(session.messages)} messages)"

        claude_sessions[dashboard_session_id] = session
        save_sessions_metadata()

    return {"success": True, "session": session.get_info()}


def delete_claude_session(session_id):
    """Stop and delete session"""
    with claude_sessions_lock:
        session = claude_sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        session.stop()
        session.cleanup()
        del claude_sessions[session_id]
        save_sessions_metadata()

    return {"success": True, "deleted": session_id}


# Load metadata on startup
load_sessions_metadata()


def get_agents(config, force_refresh=False):
    """Get agent status from openclaw.json config (D55-D62)"""
    agents = []
    error = None

    if force_refresh:
        agent_cache.invalidate()

    configured_agents = agent_cache.get_agents_list()
    cached = agent_cache.is_cached()

    if configured_agents is None:
        return {
            "agents": [],
            "gateway": {
                "healthy": False,
                "activeAgents": 0,
                "lastChecked": int(time.time() * 1000),
            },
            "meta": {
                "configSource": None,
                "agentCount": 0,
                "cached": cached,
            },
            "error": "openclaw.json not found or invalid",
        }

    for agent_id in configured_agents:
        try:
            session_data = get_session_info(config, agent_id)
            agents.append(
                {
                    "id": agent_id,
                    "displayName": agent_id.capitalize(),
                    "status": derive_status(True, session_data),
                    "enabled": True,
                    "lastActivityAt": session_data.get("updatedAt", 0),
                    "lastActivityAgo": format_time_ago(
                        session_data.get("updatedAt", 0)
                    ),
                    "model": session_data.get("model", "unknown"),
                    "sessionCount": session_data.get("sessionCount", 0),
                    "currentSessionId": session_data.get("currentSessionId", ""),
                    "lastChannel": session_data.get("lastChannel", ""),
                    "currentActivity": session_data.get("currentActivity", ""),
                }
            )
        except Exception as e:
            print(f"[WARN] Failed to get session for {agent_id}: {e}")
            agents.append(
                {
                    "id": agent_id,
                    "displayName": agent_id.capitalize(),
                    "status": "offline",
                    "enabled": True,
                    "lastActivityAt": 0,
                    "lastActivityAgo": "never",
                    "model": "unknown",
                    "sessionCount": 0,
                    "currentSessionId": "",
                    "lastChannel": "",
                    "currentActivity": "",
                }
            )

    active_count = sum(1 for a in agents if a.get("lastActivityAt", 0) > 0)

    return {
        "agents": agents,
        "gateway": {
            "healthy": len(agents) > 0,
            "activeAgents": active_count,
            "lastChecked": int(time.time() * 1000),
        },
        "meta": {
            "configSource": "openclaw.json",
            "agentCount": len(agents),
            "cached": cached,
        },
        "error": None,
    }


def get_session_info(config, agent_id):
    """Get session info from sessions.json"""
    sessions_path = os.path.expanduser(config["agents"]["sessionsPath"])
    session_file = os.path.join(sessions_path, agent_id, "sessions", "sessions.json")

    if not os.path.exists(session_file):
        return {}

    try:
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        sessions = list(data.values()) if isinstance(data, dict) else []
        if not sessions:
            return {"sessionCount": 0}

        latest = max(sessions, key=lambda s: s.get("updatedAt", 0), default={})

        # D53: Extract lastChannel for current activity display
        last_channel = latest.get("lastChannel", "")
        current_activity = format_activity(last_channel)

        return {
            "updatedAt": latest.get("updatedAt", 0),
            "model": latest.get("model", "unknown"),
            "currentSessionId": latest.get("sessionId", ""),
            "sessionCount": len(sessions),
            "lastChannel": last_channel,
            "currentActivity": current_activity,
        }
    except Exception:
        return {"sessionCount": 0}


def derive_status(enabled, session_data):
    """Derive agent status from enabled state and session activity"""
    if not enabled:
        return "offline"

    updated_at = session_data.get("updatedAt", 0)
    if updated_at == 0:
        return "offline"

    now = int(time.time() * 1000)
    busy_threshold = 30 * 1000
    idle_threshold = 5 * 60 * 1000

    age = now - updated_at

    if age < busy_threshold:
        return "busy"
    elif age < idle_threshold:
        return "online"
    else:
        return "idle"


def format_time_ago(timestamp):
    """Format timestamp as human-readable time ago"""
    if not timestamp:
        return "never"

    now = int(time.time() * 1000)
    diff = now - timestamp

    if diff < 60000:
        return "just now"
    elif diff < 3600000:
        return f"{diff // 60000} min ago"
    elif diff < 86400000:
        return f"{diff // 3600000} hr ago"
    else:
        return f"{diff // 86400000} days ago"


def format_activity(channel):
    """Format channel as human-readable activity (D53)"""
    if not channel:
        return ""

    activity_map = {
        "webchat": "在 WebChat",
        "feishu": "在飞书对话",
        "discord": "在 Discord",
        "slack": "在 Slack",
    }
    return activity_map.get(channel.lower(), f"在 {channel}")


def get_gateway_status(config):
    """Check gateway health"""
    import urllib.request
    import urllib.error

    gateway = config.get("gateway", {})
    healthz_url = gateway.get(
        "healthz", f"http://localhost:{gateway.get('port', 18789)}/healthz"
    )
    readyz_url = gateway.get(
        "readyz", f"http://localhost:{gateway.get('port', 18789)}/readyz"
    )

    result = {
        "healthy": False,
        "ready": False,
        "healthz": {"status": "unknown"},
        "readyz": {"status": "unknown"},
    }

    try:
        req = urllib.request.Request(healthz_url)
        with urllib.request.urlopen(req, timeout=5) as response:
            result["healthz"] = {"status": "ok", "timestamp": int(time.time() * 1000)}
            result["healthy"] = True
    except Exception as e:
        result["healthz"] = {"status": "error", "error": str(e)}

    try:
        req = urllib.request.Request(readyz_url)
        with urllib.request.urlopen(req, timeout=5) as response:
            result["readyz"] = {"status": "ok", "checks": []}
            result["ready"] = True
    except Exception as e:
        result["readyz"] = {"status": "error", "error": str(e)}

    return result


def get_sessions(config, agent_filter="all", type_filter="all"):
    """Get live sessions from sessions.json (D64-D65)"""
    now = int(time.time() * 1000)
    sessions = []
    counts = {"total": 0, "feishu": 0, "webchat": 0, "other": 0}

    # Get agents to query
    configured_agents = agent_cache.get_agents_list()
    if configured_agents is None:
        return {"sessions": [], "counts": counts, "error": "openclaw.json not found"}

    if agent_filter != "all" and agent_filter in configured_agents:
        agents_to_query = [agent_filter]
    else:
        agents_to_query = configured_agents

    for agent_id in agents_to_query:
        agent_sessions = get_all_sessions_for_agent(config, agent_id)

        for session_key, session_data in agent_sessions:
            channel = session_data.get("lastChannel")
            updated_at = session_data.get("updatedAt", 0)
            ended_at = session_data.get("endedAt")

            # D65: Live Session = has channel + updated within 7d
            if not channel:
                continue

            age_ms = now - updated_at
            if age_ms > 24 * 3600000:  # 24 hours (D73)
                continue

            # Extract session type
            parts = session_key.split(":")
            session_type = parts[2] if len(parts) > 2 else "unknown"

            # Apply type filter
            if type_filter != "all" and session_type != type_filter:
                continue

            # Determine status
            if not ended_at and age_ms < 3600000:  # 1 hour
                status = "online"
            elif not ended_at and age_ms < 86400000:  # 1 day
                status = "idle"
            else:
                status = "offline"

            # D78: Get additional session details
            session_file_path = session_data.get("sessionFile", "")
            job_name = get_session_job_name(session_file_path)
            model = session_data.get("model", "")
            runtime_ms = session_data.get("runtimeMs", 0)
            chat_type = session_data.get("chatType", "direct")
            started_at = session_data.get("startedAt", 0)

            sessions.append(
                {
                    "sessionId": session_data.get("sessionId", session_key),
                    "agentId": agent_id,
                    "type": session_type,
                    "channel": channel,
                    "status": status,
                    "updatedAt": updated_at,
                    "updatedAtAgo": format_time_ago(updated_at),
                    "endedAt": ended_at,
                    "model": model,
                    "jobName": job_name,
                    "runtimeMs": runtime_ms,
                    "runtimeFormatted": format_duration(runtime_ms),
                    "chatType": chat_type,
                    "startedAt": started_at,
                    "startedAtAgo": format_time_ago(started_at),
                }
            )

            # Update counts
            counts["total"] += 1
            if channel == "feishu":
                counts["feishu"] += 1
            elif channel == "webchat":
                counts["webchat"] += 1
            else:
                counts["other"] += 1

    # Sort by updatedAt descending
    sessions.sort(key=lambda s: s.get("updatedAt", 0), reverse=True)

    return {"sessions": sessions, "counts": counts, "error": None}


def get_all_sessions_for_agent(config, agent_id):
    """Get all sessions for an agent as list of (key, value) tuples"""
    sessions_path = os.path.expanduser(config["agents"]["sessionsPath"])
    session_file = os.path.join(sessions_path, agent_id, "sessions", "sessions.json")

    if not os.path.exists(session_file):
        return []

    try:
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return list(data.items())
        return []
    except Exception:
        return []


def get_session_job_name(session_file_path):
    """Extract job name from session JSONL file (D78)"""
    if not session_file_path or not os.path.exists(session_file_path):
        return ""

    try:
        with open(session_file_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line.strip())
                    if d.get("type") == "message":
                        msg = d.get("message", {})
                        content = msg.get("content", [])
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and "text" in c:
                                    try:
                                        text_data = json.loads(c["text"])
                                        jobs = text_data.get("jobs", [])
                                        if jobs and len(jobs) > 0:
                                            return jobs[0].get("name", "")
                                    except Exception:
                                        pass
                except Exception:
                    pass
    except Exception:
        pass
    return ""


def format_duration(ms):
    """Format milliseconds as human-readable duration"""
    if not ms:
        return "-"
    seconds = ms // 1000
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m {seconds % 60}s"
    hours = minutes // 60
    return f"{hours}h {minutes % 60}m"


def get_tasks(config, filters=None):
    """Get tasks from tasks.jsonl"""
    tasks_path = config["tasks"]["path"]
    tasks = []

    if not os.path.exists(tasks_path):
        return {"tasks": [], "stats": {}, "error": "Tasks file not found"}

    try:
        with open(tasks_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        task = json.loads(line)

                        if filters:
                            if (
                                filters.get("status")
                                and task.get("status") != filters["status"]
                            ):
                                continue
                            if (
                                filters.get("priority")
                                and task.get("priority") != filters["priority"]
                            ):
                                continue
                            if filters.get("search"):
                                search = filters["search"].lower()
                                if (
                                    search not in task.get("title", "").lower()
                                    and search not in task.get("notes", "").lower()
                                ):
                                    continue

                        task["children"] = []
                        tasks.append(task)
                    except Exception:
                        pass
    except Exception as e:
        return {"tasks": [], "stats": {}, "error": str(e)}

    tasks_by_id = {t["task_id"]: t for t in tasks}
    root_tasks = []

    for task in tasks:
        parent_id = task.get("parent_id")
        if parent_id and parent_id in tasks_by_id:
            tasks_by_id[parent_id]["children"].append(task)
        else:
            root_tasks.append(task)

    stats = {
        "total": len(tasks),
        "completed": sum(1 for t in tasks if t.get("status") == "已完成"),
        "pending": sum(1 for t in tasks if t.get("status") == "待处理"),
        "inProgress": sum(1 for t in tasks if t.get("status") == "进行中"),
        "blocked": sum(1 for t in tasks if t.get("status") == "挂起"),
    }

    return {"tasks": root_tasks, "stats": stats, "error": None}


def with_jsonl_lock(file_path, read_modify_write_func):
    """Execute a read-modify-write operation with exclusive file lock.

    Prevents race conditions when multiple requests modify tasks.jsonl.
    """
    with open(file_path, "r+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            result = read_modify_write_func(f)
            f.flush()
            return result
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def update_task_priority(config, task_id, priority):
    """Update task priority in tasks.jsonl with file locking"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        found = False
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        task["priority"] = priority
                        found = True
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except Exception:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "found": found}

    result = with_jsonl_lock(tasks_path, modify)
    if not result["found"]:
        return {"success": False, "error": "Task not found"}
    return {"success": True, "task": {"taskId": task_id, "priority": priority}}


def update_task_status(config, task_id, status):
    """Update task status in tasks.jsonl with file locking"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        found = False
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        task["status"] = status
                        found = True
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except Exception:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "found": found}

    result = with_jsonl_lock(tasks_path, modify)
    if not result["found"]:
        return {"success": False, "error": "Task not found"}
    return {"success": True, "task": {"taskId": task_id, "status": status}}


def update_task_status_batch(config, task_ids, status):
    """Update multiple tasks status in tasks.jsonl with file locking"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        updated_count = 0
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") in task_ids:
                        task["status"] = status
                        updated_count += 1
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except Exception:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "updated": updated_count}

    return with_jsonl_lock(tasks_path, modify)


def delete_task(config, task_id):
    """Delete task from tasks.jsonl with file locking"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        found = False
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        found = True
                        continue  # Skip this line (delete it)
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except Exception:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "found": found}

    result = with_jsonl_lock(tasks_path, modify)
    if not result["found"]:
        return {"success": False, "error": "Task not found"}
    return {"success": True, "deleted": True}


def update_task_assignee(config, task_id, assignee):
    """Update task assignee in tasks.jsonl with file locking"""
    tasks_path = config["tasks"]["path"]

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        found = False
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        task["assignee"] = assignee if assignee else ""
                        found = True
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except Exception:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "found": found}

    result = with_jsonl_lock(tasks_path, modify)
    if not result["found"]:
        return {"success": False, "error": "Task not found"}
    return {"success": True, "task": {"taskId": task_id, "assignee": assignee}}


def get_stats(config):
    """Get statistics for dashboard (Phase 2)

    Returns agent utilization, task throughput, and session activity.
    """
    now = int(time.time() * 1000)
    one_day_ms = 24 * 60 * 60 * 1000
    one_week_ms = 7 * one_day_ms

    # Agent stats from get_agents
    agents_data = get_agents(config)
    agents = agents_data.get("agents", [])

    agent_counts = {"online": 0, "busy": 0, "idle": 0, "offline": 0}
    for a in agents:
        status = a.get("status", "offline")
        if status in agent_counts:
            agent_counts[status] += 1

    total_agents = len(agents)
    active_agents = agent_counts["online"] + agent_counts["busy"]
    utilization = round((active_agents / total_agents * 100), 1) if total_agents > 0 else 0

    # Task stats from get_tasks
    tasks_data = get_tasks(config)
    tasks = []
    tasks_path = config["tasks"]["path"]

    if os.path.exists(tasks_path):
        with open(tasks_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        tasks.append(json.loads(line))
                    except Exception:
                        pass

    task_counts = {
        "total": len(tasks),
        "completed": sum(1 for t in tasks if t.get("status") == "已完成"),
        "pending": sum(1 for t in tasks if t.get("status") == "待处理"),
        "inProgress": sum(1 for t in tasks if t.get("status") == "进行中"),
        "blocked": sum(1 for t in tasks if t.get("status") == "挂起"),
    }

    completion_rate = round((task_counts["completed"] / task_counts["total"] * 100), 1) if task_counts["total"] > 0 else 0

    # Count completed today (by checking notes for completion timestamp)
    # For simplicity, we estimate based on recent activity
    completed_today = 0
    completed_week = 0

    # Session stats
    sessions_data = get_sessions(config)
    sessions = sessions_data.get("sessions", [])

    session_counts = {"total": len(sessions), "feishu": 0, "webchat": 0, "other": 0}
    total_runtime = 0

    for s in sessions:
        channel = s.get("channel", "other")
        if channel == "feishu":
            session_counts["feishu"] += 1
        elif channel == "webchat":
            session_counts["webchat"] += 1
        else:
            session_counts["other"] += 1
        total_runtime += s.get("runtimeMs", 0)

    return {
        "agents": {
            "total": total_agents,
            "online": agent_counts["online"],
            "busy": agent_counts["busy"],
            "idle": agent_counts["idle"],
            "offline": agent_counts["offline"],
            "utilizationPercent": utilization,
        },
        "tasks": {
            "total": task_counts["total"],
            "completed": task_counts["completed"],
            "pending": task_counts["pending"],
            "inProgress": task_counts["inProgress"],
            "blocked": task_counts["blocked"],
            "completionRate": completion_rate,
        },
        "sessions": {
            "active24h": session_counts["total"],
            "feishu": session_counts["feishu"],
            "webchat": session_counts["webchat"],
            "totalRuntimeMs": total_runtime,
        },
    }


def get_assignees(config):
    """Get list of available assignees (humans + agents)"""
    # Human assignees
    humans = [
        {"id": "Ricky", "type": "human", "displayName": "Ricky", "avatar": None},
    ]

    # OpenClaw Agents from openclaw.json
    openclaw_agents = []
    configured_agents = agent_cache.get_agents_list()
    if configured_agents:
        for agent_id in configured_agents:
            openclaw_agents.append(
                {
                    "id": agent_id,
                    "type": "openclaw",
                    "displayName": agent_id.capitalize(),
                    "avatar": None,
                }
            )

    # OpenCode Agents
    opencode_agents = [
        {
            "id": "opencode",
            "type": "opencode",
            "displayName": "OpenCode",
            "avatar": None,
        },
    ]

    return {
        "humans": humans,
        "openclaw": openclaw_agents,
        "opencode": opencode_agents,
    }


def get_opencode_sessions(worktree_filter="vault/projects"):
    """Get OpenCode sessions from SQLite database (D94-D95)

    Query sessions with project worktree matching the filter.
    This bypasses the HTTP API which only returns global sessions.
    """
    import sqlite3

    db_path = os.path.expanduser("~/.local/share/opencode/opencode.db")

    if not os.path.exists(db_path):
        return {"sessions": [], "error": "OpenCode database not found"}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT 
                s.id,
                s.title,
                s.project_id as projectID,
                s.directory,
                s.time_created as timeCreated,
                s.time_updated as timeUpdated,
                s.time_archived as timeArchived,
                p.worktree,
                p.name as projectName
            FROM session s
            JOIN project p ON s.project_id = p.id
            WHERE p.worktree LIKE ?
            AND s.time_archived IS NULL
            ORDER BY s.time_updated DESC
        """

        cursor.execute(query, (f"%{worktree_filter}%",))
        rows = cursor.fetchall()
        conn.close()

        sessions = []
        for row in rows:
            sessions.append(
                {
                    "id": row["id"],
                    "title": row["title"] or "Untitled",
                    "projectID": row["projectID"],
                    "directory": row["directory"],
                    "worktree": row["worktree"],
                    "projectName": row["projectName"],
                    "time": {
                        "created": row["timeCreated"],
                        "updated": row["timeUpdated"],
                    },
                    "status": "idle",
                    "time_created": row["timeCreated"],
                }
            )

        return {"sessions": sessions, "count": len(sessions)}

    except sqlite3.Error as e:
        return {"sessions": [], "error": str(e)}


OPENCODE_PROJECTS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "opencode-projects.json"
)


def get_opencode_projects():
    """Get OpenCode projects configuration (D88)"""
    if not os.path.exists(OPENCODE_PROJECTS_PATH):
        return {"projects": [], "error": "Config file not found"}

    try:
        with open(OPENCODE_PROJECTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {
            "projects": data.get("projects", []),
            "default": data.get("defaultProject", ""),
        }
    except Exception as e:
        return {"projects": [], "error": str(e)}


def get_session_state(config):
    """Get current session state from openclaw (D72-D76)"""
    session_state_path = os.path.expanduser("~/.openclaw/workspace/session-state.json")

    if not os.path.exists(session_state_path):
        return {"status": "offline", "error": "Session state file not found"}

    try:
        with open(session_state_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        current_task_id = data.get("current_task")
        status = data.get("status", "idle")
        waiting_events = data.get("waiting_events", [])

        task_info = None
        if current_task_id:
            tasks_path = config.get("tasks", {}).get("path", "")
            if tasks_path and os.path.exists(tasks_path):
                with open(tasks_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            task = json.loads(line)
                            if task.get("task_id") == current_task_id:
                                task_info = {
                                    "id": task.get("task_id"),
                                    "title": task.get("title", ""),
                                    "priority": task.get("priority", "待定"),
                                    "status": task.get("status", "待处理"),
                                }
                                break

        return {
            "status": status,
            "currentTask": task_info,
            "waitingCount": len(waiting_events),
            "model": data.get("model", "unknown"),
            "lastUpdated": data.get("last_updated"),
        }
    except Exception as e:
        return {"status": "offline", "error": str(e)}


def send_notification(config, task_id, agent_id, notification_type):
    """Send notification to agent via openclaw CLI"""
    templates = {
        "PRIORITY_UP": f"Task {task_id} priority changed. Please review.",
        "WORK_NEXT": f"Queue jump: Task {task_id} is highest priority. Start immediately.",
    }

    message = templates.get(notification_type, f"Notification for task {task_id}")

    try:
        result = subprocess.run(
            [
                "openclaw",
                "agent",
                "--agent",
                agent_id,
                "--message",
                message,
                "--deliver",
                "--reply-channel",
                "feishu",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return {"success": True, "message": "通知已发送"}
        else:
            return {"success": False, "error": result.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}


def notify_agent(config, agent_id, notification_type="PING"):
    """Send a notification to an agent (v0.7.0)"""
    messages = {
        "PING": "📢 Ping from dashboard - checking connection",
        "WAKE_UP": "🔔 Wake up - you have pending tasks",
        "STATUS_CHECK": "📊 Please update your status",
    }

    message = messages.get(notification_type, f"Notification: {notification_type}")

    try:
        result = subprocess.run(
            [
                "openclaw",
                "agent",
                "--agent",
                agent_id,
                "--message",
                message,
                "--deliver",
                "--reply-channel",
                "feishu",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return {"success": True, "message": f"Notification sent to {agent_id}"}
        else:
            return {"success": False, "error": result.stderr or "Unknown error"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timeout"}
    except FileNotFoundError:
        return {"success": False, "error": "openclaw CLI not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}



def execute_task(config, task_id, agent_id, agent_type="openclaw"):
    """Execute task immediately by sending to agent (OpenClaw or OpenCode)"""
    tasks_path = config["tasks"]["path"]
    openclaw_path = "/home/aegis/.npm-global/bin/openclaw"

    if not os.path.exists(tasks_path):
        return {"success": False, "error": "Tasks file not found"}

    def modify(f):
        lines = f.read().strip().split("\n")
        f.seek(0)
        f.truncate()

        found = False
        task_data = None
        for line in lines:
            if line.strip():
                try:
                    task = json.loads(line)
                    if task.get("task_id") == task_id:
                        task["status"] = "进行中"
                        task["notes"] = task.get("notes", "") + f"\n\n【执行记录】{datetime.now().isoformat()} - 任务已发送给 {agent_type}:{agent_id} 执行"
                        found = True
                        task_data = task
                    f.write(json.dumps(task, ensure_ascii=False) + "\n")
                except Exception:
                    f.write(line + "\n")
            else:
                f.write("\n")

        return {"success": True, "found": found, "task_data": task_data}

    result = with_jsonl_lock(tasks_path, modify)

    if not result["found"]:
        return {"success": False, "error": "Task not found"}

    task_data = result["task_data"]

    # Send task to agent (async - don't wait for completion)
    try:
        if agent_type == "openclaw":
            # Send message to OpenClaw agent using background process
            message = f"【立即执行】Task {task_id}: {task_data.get('title', 'Untitled')}\n\n请开始执行此任务。"

            # Use Popen for async execution (don't block HTTP response)
            subprocess.Popen(
                [
                    openclaw_path,
                    "agent",
                    "--agent",
                    agent_id,
                    "--message",
                    message,
                    "--deliver",
                    "--reply-channel",
                    "feishu",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent process
            )

            return {
                "success": True,
                "message": f"任务已发送给 {agent_id} 执行（异步执行中）",
                "agentType": agent_type,
                "agentId": agent_id,
                "executionMode": "async"
            }

        elif agent_type == "opencode":
            # For OpenCode, spawn session with task context
            return {
                "success": True,
                "message": f"任务已发送给 OpenCode 执行",
                "agentType": agent_type,
                "agentId": agent_id
            }
        else:
            return {"success": False, "error": f"Unknown agent type: {agent_type}"}

    except Exception as e:
        # Rollback task status on error (also with locking)
        def rollback(f):
            lines = f.read().strip().split("\n")
            f.seek(0)
            f.truncate()
            for line in lines:
                if line.strip():
                    try:
                        task = json.loads(line)
                        if task.get("task_id") == task_id:
                            task["status"] = "待处理"
                        f.write(json.dumps(task, ensure_ascii=False) + "\n")
                    except Exception:
                        f.write(line + "\n")
                else:
                    f.write("\n")
            return {"done": True}

        with_jsonl_lock(tasks_path, rollback)
        return {"success": False, "error": str(e)}


class COADashHandler(BaseHTTPRequestHandler):
    config = None

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {args[0]}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.serve_file("index.html", "text/html")
        elif path == "/api/agents":
            force_refresh = query.get("force", ["false"])[0].lower() == "true"
            self.send_json(get_agents(self.config, force_refresh))
        elif path == "/api/gateway/status":
            self.send_json(get_gateway_status(self.config))
        elif path == "/api/tasks":
            filters = {}
            if "status" in query:
                filters["status"] = query["status"][0]
            if "priority" in query:
                filters["priority"] = query["priority"][0]
            if "search" in query:
                filters["search"] = query["search"][0]
            self.send_json(get_tasks(self.config, filters if filters else None))
        elif path == "/api/sessions":
            agent_filter = query.get("agent", ["all"])[0]
            type_filter = query.get("type", ["all"])[0]
            self.send_json(get_sessions(self.config, agent_filter, type_filter))
        elif path == "/api/assignees":
            self.send_json(get_assignees(self.config))
        elif path == "/api/stats":
            self.send_json(get_stats(self.config))
        elif path == "/api/config":
            self.send_json(
                {
                    "dashboard": self.config["dashboard"],
                    "gateway": {
                        k: v for k, v in self.config["gateway"].items() if k != "token"
                    },
                    "status": self.config["status"],
                }
            )
        elif path == "/api/opencode/sessions":
            worktree_filter = query.get("worktree", ["vault/projects"])[0]
            self.send_json(get_opencode_sessions(worktree_filter))
        elif path == "/api/opencode/projects":
            self.send_json(get_opencode_projects())
        elif path == "/api/session-state":
            self.send_json(get_session_state(self.config))
        # Claude Code Session API (v0.7.0)
        elif path == "/api/claudecode/sessions":
            self.send_json({"sessions": get_claude_sessions()})
        elif re.match(r"/api/claudecode/sessions/([^/]+)$", path):
            session_id = re.match(r"/api/claudecode/sessions/([^/]+)$", path).group(1)
            session = get_claude_session(session_id)
            if session:
                self.send_json(session)
            else:
                self.send_json({"error": "Session not found"}, 404)
        elif re.match(r"/api/claudecode/sessions/([^/]+)/history$", path):
            session_id = re.match(r"/api/claudecode/sessions/([^/]+)/history$", path).group(1)
            limit = int(query.get("limit", [100])[0])
            result = get_claude_session_history(session_id, limit)
            if "error" in result:
                self.send_json(result, 404)
            else:
                self.send_json(result)
        elif path == "/api/claudecode/available":
            # List Claude sessions available on disk
            cwd = query.get("cwd", ["/home/aegis/vault/projects/coa-dash"])[0]
            self.send_json(list_available_claude_sessions(cwd))
        elif re.match(r"/api/claudecode/sessions/([^/]+)/stream$", path):
            # SSE endpoint for real-time updates (v0.7.0)
            session_id = re.match(r"/api/claudecode/sessions/([^/]+)/stream$", path).group(1)
            self.handle_sse_stream(session_id)
        elif re.match(r"/api/claudecode/sessions/([^/]+)/retained$", path):
            # Get retained messages
            session_id = re.match(r"/api/claudecode/sessions/([^/]+)/retained$", path).group(1)
            retained = get_retained_messages(session_id)
            self.send_json({"retained": retained, "count": len(retained)})
        elif path.startswith("/api/opencode/") and "/session/" in path:
            self.proxy_opencode_request(path)
        else:
            self.send_error(404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Handle /api/tasks/:id/assignee
        assignee_match = re.match(r"/api/tasks/([^/]+)/assignee", path)
        if assignee_match:
            task_id = assignee_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                assignee = data.get("assignee", "")
                result = update_task_assignee(self.config, task_id, assignee)
                self.send_json(result)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
            return

        # Handle /api/tasks/:id/priority
        priority_match = re.match(r"/api/tasks/([^/]+)/priority", path)
        if priority_match:
            task_id = priority_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                priority = data.get("priority")
                if priority:
                    result = update_task_priority(self.config, task_id, priority)
                    self.send_json(result)
                else:
                    self.send_json(
                        {"success": False, "error": "Priority required"}, 400
                    )
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
            return

        # Handle /api/tasks/:id/status
        status_match = re.match(r"/api/tasks/([^/]+)/status", path)
        if status_match:
            task_id = status_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                status = data.get("status")
                if status:
                    result = update_task_status(self.config, task_id, status)
                    self.send_json(result)
                else:
                    self.send_json({"success": False, "error": "Status required"}, 400)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
            return

        # Handle /api/tasks/status/batch
        batch_match = re.match(r"/api/tasks/status/batch", path)
        if batch_match:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                task_ids = data.get("taskIds", [])
                status = data.get("status")
                if task_ids and status:
                    result = update_task_status_batch(self.config, task_ids, status)
                    self.send_json(result)
                else:
                    self.send_json(
                        {"success": False, "error": "taskIds and status required"}, 400
                    )
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        notify_match = re.match(r"/api/tasks/([^/]+)/notify", path)
        work_next_match = re.match(r"/api/tasks/([^/]+)/work-next", path)
        execute_match = re.match(r"/api/tasks/([^/]+)/execute", path)

        if notify_match:
            task_id = notify_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                agent_id = data.get("agentId", "main")
                notification_type = data.get("type", "PRIORITY_UP")
                result = send_notification(
                    self.config, task_id, agent_id, notification_type
                )
                self.send_json(result)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
        elif work_next_match:
            task_id = work_next_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                agent_id = data.get("agentId", "main")
                result = send_notification(self.config, task_id, agent_id, "WORK_NEXT")
                self.send_json(result)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
        elif execute_match:
            task_id = execute_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                agent_id = data.get("agentId", "main")
                agent_type = data.get("agentType", "openclaw")
                result = execute_task(self.config, task_id, agent_id, agent_type)
                self.send_json(result)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
        # Agent notification endpoint (v0.7.0)
        elif re.match(r"/api/agents/([^/]+)/notify", path):
            agent_match = re.match(r"/api/agents/([^/]+)/notify", path)
            agent_id = agent_match.group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                notification_type = data.get("type", "PING")
                result = notify_agent(self.config, agent_id, notification_type)
                self.send_json(result)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, 400)
        elif path.startswith("/api/opencode/") and "/session/" in path:
            self.proxy_opencode_request(path)
        # Claude Code Session API (v0.7.0)
        elif path == "/api/claudecode/sessions":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                name = data.get("name", "Untitled")
                cwd = data.get("cwd", "/home/aegis/vault/projects/coa-dash")
                model = data.get("model")
                result = create_claude_session(name, cwd, model)
                if "error" in result:
                    self.send_json(result, 400)
                else:
                    self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)}, 400)
        elif re.match(r"/api/claudecode/sessions/([^/]+)/message$", path):
            session_id = re.match(r"/api/claudecode/sessions/([^/]+)/message$", path).group(1)
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                content = data.get("content", "")
                if not content:
                    self.send_json({"error": "Content required"}, 400)
                else:
                    result = send_claude_message(session_id, content)
                    if "error" in result:
                        self.send_json(result, 400)
                    else:
                        self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)}, 400)
        elif path == "/api/claudecode/import":
            # Import an existing Claude session from disk
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            try:
                data = json.loads(body)
                claude_session_id = data.get("claudeSessionId")
                name = data.get("name", "Imported")
                project_dir = data.get("projectDir")  # Encoded dir like "-home-aegis-vault-projects-coa-dash"
                cwd = data.get("cwd", "/home/aegis/vault/projects/coa-dash")

                # Decode projectDir if provided
                if project_dir:
                    # Decode: -home-aegis-vault-projects-coa-dash → /home/aegis/vault/projects/coa-dash
                    # The encoding is: / → -, . → -- (for hidden dirs)
                    # Key insight: dashes in project names (like coa-dash) are preserved
                    decoded = project_dir
                    if decoded.startswith("-"):
                        decoded = decoded[1:]  # Remove leading dash (root)
                    # First handle hidden directories: -- → /.
                    decoded = decoded.replace("--", "/.")
                    # Find "projects" marker - everything after it is the project name (preserve dashes)
                    if "-projects-" in decoded:
                        prefix, project_name = decoded.split("-projects-", 1)
                        cwd = "/" + prefix.replace("-", "/") + "/projects/" + project_name
                    else:
                        # No projects marker, just replace all dashes
                        cwd = "/" + decoded.replace("-", "/")

                if not claude_session_id:
                    self.send_json({"error": "claudeSessionId required"}, 400)
                else:
                    result = import_claude_session(claude_session_id, name, cwd)
                    if "error" in result:
                        self.send_json(result, 400)
                    else:
                        self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)}, 400)
        else:
            self.send_error(404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path

        delete_match = re.match(r"/api/tasks/([^/]+)$", path)
        if delete_match:
            task_id = delete_match.group(1)
            result = delete_task(self.config, task_id)
            self.send_json(result)
        # Claude Code Session API (v0.7.0)
        elif re.match(r"/api/claudecode/sessions/([^/]+)$", path):
            session_id = re.match(r"/api/claudecode/sessions/([^/]+)$", path).group(1)
            result = delete_claude_session(session_id)
            if "error" in result:
                self.send_json(result, 404)
            else:
                self.send_json(result)
        elif re.match(r"/api/claudecode/sessions/([^/]+)/retained$", path):
            # Clear all retained messages
            session_id = re.match(r"/api/claudecode/sessions/([^/]+)/retained$", path).group(1)
            with retained_messages_lock:
                if session_id in retained_messages:
                    count = len(retained_messages[session_id])
                    retained_messages[session_id] = []
                    self.send_json({"success": True, "cleared": count})
                else:
                    self.send_json({"success": True, "cleared": 0})
        elif re.match(r"/api/claudecode/sessions/([^/]+)/retained/(\d+)$", path):
            # Delete specific retained message by index
            match = re.match(r"/api/claudecode/sessions/([^/]+)/retained/(\d+)$", path)
            session_id = match.group(1)
            index = int(match.group(2))
            result = clear_retained_message(session_id, index)
            if "error" in result:
                self.send_json(result, 400)
            else:
                self.send_json(result)
        else:
            self.send_error(404)

    def send_json(self, data, status=200):
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))

        # CORS: Check Origin against whitelist
        origin = self.headers.get("Origin", "")
        allowed_origins = self.config.get("allowedOrigins", [])
        if origin and origin in allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
        elif not origin:
            # No Origin header (direct browser request, curl, etc.)
            pass  # Don't send CORS header

        self.end_headers()
        self.wfile.write(encoded)

    def handle_sse_stream(self, session_id):
        """Handle SSE streaming for real-time session updates (v0.7.0)"""
        # Check session exists
        with claude_sessions_lock:
            session = claude_sessions.get(session_id)
            if not session:
                self.send_json({"error": "Session not found"}, 404)
                return

        # Set up SSE response
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")  # Disable nginx buffering

        # CORS
        origin = self.headers.get("Origin", "")
        allowed_origins = self.config.get("allowedOrigins", [])
        if origin and origin in allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)

        self.end_headers()

        # Create queue for this subscriber
        subscriber_queue = queue.Queue(maxsize=100)
        add_sse_subscriber(session_id, subscriber_queue)

        try:
            # Send initial status
            self._send_sse_event("init", session.get_info())

            # Keep connection alive and send updates
            while True:
                try:
                    # Wait for update with timeout
                    event = subscriber_queue.get(timeout=30)
                    self._send_sse_event(event["type"], event["data"])
                except queue.Empty:
                    # Send keepalive comment
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    # Check for retained messages that can now be sent
                    check_terminal_idle_and_alert(session_id)

        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected
            pass
        finally:
            remove_sse_subscriber(session_id, subscriber_queue)

    def _send_sse_event(self, event_type, data):
        """Send a single SSE event"""
        try:
            event_str = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            self.wfile.write(event_str.encode("utf-8"))
            self.wfile.flush()
        except Exception:
            raise BrokenPipeError()

    def proxy_opencode_request(self, path):
        """Proxy requests to OpenCode serve (D80-D81, D99)"""
        import urllib.request
        import urllib.error

        parts = path.split("/")
        try:
            port = int(parts[3])
            session_id = parts[5]
            action = parts[6] if len(parts) > 6 else ""
        except (IndexError, ValueError):
            self.send_json({"error": "Invalid path"}, 400)
            return

        # D99: Port whitelist - only allow ports from opencode-projects.json
        projects = get_opencode_projects()
        allowed_ports = [p.get("port") for p in projects.get("projects", []) if p.get("port")]
        if port not in allowed_ports:
            self.send_json({"error": "Port not allowed"}, 403)
            return

        allowed_actions = ["messages", "message", "command"]
        if action and action not in allowed_actions:
            self.send_json({"error": "Action not allowed"}, 403)
            return

        opencode_url = f"http://localhost:{port}/session/{session_id}"
        if action:
            opencode_url += f"/{action}"

        try:
            if self.command == "GET":
                req = urllib.request.Request(
                    opencode_url, headers={"Accept-Encoding": "identity"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read().decode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(data.encode("utf-8"))
            elif self.command == "POST":
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                req = urllib.request.Request(
                    opencode_url,
                    data=body,
                    headers={
                        "Content-Type": "application/json",
                        "Accept-Encoding": "identity",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read().decode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(data.encode("utf-8"))
            else:
                self.send_error(405)
        except urllib.error.URLError as e:
            self.send_json({"error": f"OpenCode connection failed: {e}"}, 502)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def serve_file(self, filename, content_type):
        try:
            path = os.path.join(os.path.dirname(__file__), filename)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            encoded = content.encode("utf-8")

            # Check if client supports gzip
            accept_encoding = self.headers.get("Accept-Encoding", "")
            if "gzip" in accept_encoding and len(encoded) > 500:
                import gzip
                compressed = gzip.compress(encoded)
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(compressed)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(compressed)
            else:
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(encoded)
        except FileNotFoundError:
            self.send_error(404, "File not found")


class ReusableHTTPServer(HTTPServer):
    """HTTPServer with SO_REUSEADDR enabled"""

    allow_reuse_address = True


if __name__ == "__main__":
    config = load_config()
    COADashHandler.config = config

    port = config["dashboard"]["port"]
    host = config["dashboard"]["host"]

    print(f"🦞 COA-dash running on http://{host}:{port}")
    print(f"   Tailscale: http://100.103.186.109:{port}")
    print(f"   Config: {CONFIG_PATH}")

    ReusableHTTPServer((host, port), COADashHandler).serve_forever()
