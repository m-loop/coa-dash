#!/usr/bin/env python3
"""
Feishu-Claude Bridge Service

Bridges Feishu chats with Claude Code sessions via coa-dash API.

Modes:
  dm     - User DMs the bot, bot forwards to a linked Claude session
  topic  - 话题群 mode, each topic = 1 session (future)

Commands (in any mode):
  /link <#|id|name>   - Link this chat to a Claude session (use # from /sessions)
  /unlink             - Remove link
  /list               - Show all mappings
  /status             - Show session status
  /sessions           - List available Claude Code sessions
  /help               - Show this help
"""

import json
import os
import sys
import time
import threading
import traceback
from datetime import datetime

import hashlib

import requests
from lark_oapi import Client
from lark_oapi.core.enum import LogLevel
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws.client import Client as WsClient
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    CreateMessageReactionRequest,
    CreateMessageReactionRequestBody,
    DeleteMessageReactionRequest,
    PatchMessageRequest,
    PatchMessageRequestBody,
)

# ── Config paths ──────────────────────────────────────────────────────

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(_BASE_DIR, "config", "feishu-bridge.json")
PERSIST_PATH = os.path.join(_BASE_DIR, "config", "feishu-persistence.json")


class FeishuBridge:
    """Bridge between Feishu chats and Claude Code sessions"""

    def __init__(self):
        self._lark_client = None
        self._ws_client = None
        self._app_id = ""
        self._app_secret = ""
        self._mode = "dm"  # "dm" or "topic"
        self._topic_group_id = ""
        self._coa_dash_url = "http://localhost:8890"
        # chat_id -> session_id (DM mode) or root_id -> session_id (topic mode)
        self._chat_session_map = {}
        self._session_chat_map = {}  # reverse: session_id -> chat_id
        self._event_dispatcher = None
        self._lock = threading.Lock()
        self._last_poll_time = {}
        self._poll_threads = {}
        self._poll_stop = {}
        self._pending_reactions = {}  # session_id -> msg_id (to add reactions to)
        self._current_reactions = {}  # session_id -> reaction_id (current status reaction)
        self._forward_baselines = {}  # session_id -> message count at forward time
        self._response_cards = {}  # session_id -> message_id of response card
        self._last_delivered_hash = {}  # session_id -> hash of last delivered text (dedup)
        self._last_working_text = {}  # session_id -> last text shown on working card (throttle)
        self._seen_msg_ids = {}  # msg_id -> timestamp, dedup WS redelivery (LRU, 5min TTL)
        self._running = False

        self._load_config()
        self._load_persistence()
        self._load_baselines()

    # ── Config / Persistence ──────────────────────────────────────────

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
            self._app_id = config.get("app_id", "")
            self._app_secret = config.get("app_secret", "")
            self._mode = config.get("mode", "dm")
            self._topic_group_id = config.get("topic_group_id", "")
            self._coa_dash_url = config.get("coa_dash_url", "http://localhost:8890")
            self._allowed_chats = config.get("allowed_chats", [])  # Whitelist chat_ids
            self._chat_session_map = config.get("chat_session_map", {})
            if self._mode == "topic":
                self._chat_session_map = config.get("session_topic_map", {})
            self._session_chat_map = {v: k for k, v in self._chat_session_map.items()}
        except FileNotFoundError:
            print(f"[WARN] Config not found: {CONFIG_PATH}")
        except Exception as e:
            print(f"[WARN] Config load failed: {e}")

    def _load_persistence(self):
        try:
            with open(PERSIST_PATH, "r") as f:
                data = json.load(f)
            self._chat_session_map.update(data.get("chat_session_map", {}))
            self._session_chat_map = {v: k for k, v in self._chat_session_map.items()}
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[WARN] Persistence load failed: {e}")

    def _save_persistence(self):
        with self._lock:
            try:
                with open(PERSIST_PATH, "w") as f:
                    json.dump({
                        "chat_session_map": self._chat_session_map,
                        "forward_baselines": self._forward_baselines,
                        "last_delivered_hash": self._last_delivered_hash,
                        "mode": self._mode,
                        "last_saved": datetime.now().isoformat(),
                    }, f, indent=2)
            except Exception as e:
                print(f"[WARN] Persistence save failed: {e}")

    def _load_baselines(self):
        """Load forward baselines from persistence file"""
        try:
            with open(PERSIST_PATH, "r") as f:
                data = json.load(f)
            baselines = data.get("forward_baselines", {})
            if baselines:
                self._forward_baselines = baselines
                print(f"[Bridge] Loaded {len(baselines)} baselines from persistence")
            delivered = data.get("last_delivered_hash", {})
            if delivered:
                self._last_delivered_hash = delivered
                print(f"[Bridge] Loaded {len(delivered)} delivery hashes from persistence")
        except Exception:
            pass

    # ── Client Init ───────────────────────────────────────────────────

    def _init_clients(self):
        self._lark_client = (
            Client.builder()
            .app_id(self._app_id)
            .app_secret(self._app_secret)
            .log_level(LogLevel.INFO)
            .build()
        )

        self._event_dispatcher = (
            EventDispatcherHandler
            .builder("", "")  # encrypt_key, verification_token (empty for WS)
            .register_p2_im_message_receive_v1(self._on_message_receive)
            .build()
        )

        self._ws_client = WsClient(
            app_id=self._app_id,
            app_secret=self._app_secret,
            event_handler=self._event_dispatcher,
            domain="https://open.feishu.cn",
            auto_reconnect=True,
            log_level=LogLevel.INFO,
        )

        print(f"[Bridge] mode={self._mode}  app={self._app_id[:8]}  mappings={len(self._chat_session_map)}")

    # ── Start / Stop ──────────────────────────────────────────────────

    def start(self):
        if not self._app_id or not self._app_secret:
            print("ERROR: app_id and app_secret required in config")
            sys.exit(1)

        self._init_clients()

        self._running = True

        # Resume polling for existing mappings
        # B9: Clear stale working card tracking (card_ids lost on restart)
        notified_chats = set()
        for session_id in self._session_chat_map:
            self._start_poll(session_id)
            chat_key = self._session_chat_map[session_id]
            if chat_key not in notified_chats:
                notified_chats.add(chat_key)
                self._send_text(chat_key, "🔄 Bridge restarted. Previous working cards are stale.")

        print(f"[Bridge] Starting (mode={self._mode})...")
        try:
            self._ws_client.start()
        except KeyboardInterrupt:
            self.stop()
            sys.exit(0)

    def stop(self):
        self._running = False
        for session_id in list(self._poll_threads.keys()):
            self._stop_poll(session_id)
        # B7: Kill orphan Claude child processes
        try:
            result = subprocess.run(
                ["pgrep", "-f", "claude.*--resume"],
                capture_output=True, text=True, timeout=3,
            )
            pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            for pid in pids:
                try:
                    subprocess.run(["kill", pid], timeout=2)
                except Exception:
                    pass
            if pids:
                print(f"[Bridge] Killed {len(pids)} orphan Claude process(es)")
        except Exception:
            pass
        if self._ws_client:
            self._ws_client.stop()
        self._save_persistence()
        print("[Bridge] Stopped")

    # ── Message Handler ───────────────────────────────────────────────

    def _on_message_receive(self, ctx):
        """Handle incoming Feishu message event."""
        try:
            sender = ctx.event.sender
            msg = ctx.event.message

            # Ignore bot's own messages
            if sender.sender_type == "app":
                return

            chat_id = msg.chat_id or ""
            chat_type = msg.chat_type or ""
            msg_type = msg.message_type or ""
            content_str = msg.content or ""
            msg_id = msg.message_id or ""

            # Auth: reject messages from non-whitelisted chats
            if self._allowed_chats and chat_id not in self._allowed_chats:
                return

            # Dedup: skip WS redelivery (Feishu may push same event multiple times)
            now = time.time()
            if msg_id and msg_id in self._seen_msg_ids:
                print(f"[MSG] skip duplicate msg_id={msg_id[:16]}", flush=True)
                return
            if msg_id:
                self._seen_msg_ids[msg_id] = now
                # Prune entries older than 5 minutes
                if len(self._seen_msg_ids) > 200:
                    cutoff = now - 300
                    self._seen_msg_ids = {k: v for k, v in self._seen_msg_ids.items() if v > cutoff}

            text = self._extract_text(content_str, msg_type)
            if not text:
                return

            print(f"[MSG] {chat_type} chat={chat_id[:8]}... msg_id={msg_id[:16]} text={text[:60]}")

            # DM and group chats both use chat_id as lookup key
            lookup_key = chat_id

            # Handle commands
            if text.startswith("/"):
                self._handle_command(text, lookup_key, chat_id)
                return

            # Find linked session
            session_id = self._chat_session_map.get(lookup_key)
            if not session_id:
                self._send_text(chat_id, "No Claude session linked. Use /link <session-id> or /new <name> to connect.")
                return

            # Forward to Claude
            rid = self._add_reaction(msg_id, "Typing")  # ⌨️ received
            self._pending_reactions[session_id] = msg_id
            if rid:
                self._current_reactions[session_id] = rid  # Track for replacement
            self._forward_to_claude(session_id, text, chat_id, msg_id)

        except Exception as e:
            print(f"[ERROR] Message handler failed: {e}")
            traceback.print_exc()

    def _extract_text(self, content_str, msg_type):
        try:
            data = json.loads(content_str) if isinstance(content_str, str) else content_str
        except (json.JSONDecodeError, TypeError):
            return ""

        if msg_type == "text":
            return data.get("text", "").strip()
        elif msg_type == "post":
            texts = []
            content = data.get("content", [])
            for block in (content if isinstance(content, list) else [content]):
                for el in (block if isinstance(block, list) else [block]):
                    if isinstance(el, dict):
                        texts.append(el.get("text", ""))
                    elif isinstance(el, str):
                        texts.append(el)
            return " ".join(texts).strip()
        return ""

    # ── Commands ──────────────────────────────────────────────────────

    def _handle_command(self, text, lookup_key, chat_id):
        parts = text.split(None, 1)
        command = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        if command == "/link":
            self._cmd_link(args, lookup_key, chat_id)
        elif command == "/new":
            self._cmd_new(args, lookup_key, chat_id)
        elif command == "/unlink":
            self._cmd_unlink(lookup_key, chat_id)
        elif command == "/list":
            self._cmd_list(chat_id)
        elif command == "/status":
            self._cmd_status(lookup_key, chat_id)
        elif command == "/sessions":
            self._cmd_sessions(chat_id)
        elif command == "/load":
            self._cmd_load(lookup_key, chat_id, args)
        elif command == "/stop":
            self._cmd_stop(lookup_key, chat_id)
        elif command == "/compact":
            self._cmd_compact(lookup_key, chat_id)
        elif command == "/ls":
            self._cmd_ls(chat_id, args)
        elif command == "/help":
            self._send_text(chat_id,
                "Claude Bridge Commands:\n\n"
                "/new <project> [cwd] - Create session (auto-mkdir + git init)\n"
                "/link <#|id|name> - Link chat to session (# from /sessions)\n"
                "/unlink - Remove link\n"
                "/stop - Stop current session task\n"
                "/compact - Compress session context\n"
                "/load [N] - Load last N rounds of conversation (default 3)\n"
                "/ls [path] - List project directories\n"
                "/list - Show all mappings\n"
                "/status - Current session status\n"
                "/sessions - List available sessions\n"
                "/help - This message"
            )
        else:
            self._send_text(chat_id, "Unknown command. Try /help")

    def _cmd_link(self, session_id, lookup_key, chat_id):
        if not session_id:
            self._send_text(chat_id, "Usage: /link <#|session-id|name>")
            return

        # Resolve index shorthand (e.g. /link 3)
        if hasattr(self, "_session_index_map") and session_id in self._session_index_map:
            session_id = self._session_index_map[session_id]

        info = self._get_session_info(session_id)
        if not info:
            # Try matching by ID prefix, project name, or title
            sessions = self._get_available_sessions()
            matches = [s for s in sessions
                       if s["id"].startswith(session_id)
                       or s.get("shortId", "").startswith(session_id)
                       or s.get("projectName", "").lower() == session_id.lower()
                       or s.get("name", "").lower() == session_id.lower()
                       or s.get("title", "").lower().startswith(session_id.lower())]
            if matches:
                # Pick the most recent session
                matches.sort(key=lambda s: s.get("startedAt", 0), reverse=True)
                session_id = matches[0]["id"]
                info = self._get_session_info(session_id)
            else:
                self._send_text(chat_id, f"Session `{session_id}` not found. Try /sessions")
                return

        # B5: Prevent multi-chat link to same session
        existing_chat = self._session_chat_map.get(session_id)
        if existing_chat and existing_chat != lookup_key:
            self._send_text(chat_id, f"⚠️ Session already linked to another chat. /unlink there first.")
            return

        # Remove old mapping if this chat was linked to something else
        old_session = self._chat_session_map.get(lookup_key)
        if old_session and old_session != session_id:
            self._stop_poll(old_session)
            if old_session in self._session_chat_map:
                del self._session_chat_map[old_session]

        self._chat_session_map[lookup_key] = session_id
        self._session_chat_map[session_id] = lookup_key
        self._save_persistence()
        self._start_poll(session_id)

        name = info.get("title", info.get("name", session_id[:8])) if info else session_id[:8]
        self._send_text(chat_id, f"✅ Linked to: {name}")

    def _cmd_new(self, args, lookup_key, chat_id):
        """Create a new Claude session and link this chat to it"""
        parts = args.split()
        if not parts:
            self._send_text(chat_id,
                "Usage:\n"
                "/new <project-name> - Create session (auto-mkdir)\n"
                "/new <name> <path>  - Create session with custom cwd")
            return

        project_name = parts[0]
        cwd = parts[1] if len(parts) > 1 else f"/home/aegis/vault/projects/{project_name}"

        # Validate cwd: must be within /home/aegis/vault/projects/
        cwd = os.path.realpath(cwd)
        if not cwd.startswith("/home/aegis/vault/projects/"):
            self._send_text(chat_id, "⚠️ Only /home/aegis/vault/projects/ allowed")
            return

        # Auto-create project directory if not exists
        created = False
        if not os.path.isdir(cwd):
            try:
                os.makedirs(cwd, exist_ok=True)
                created = True
                # Init git repo for new projects (safe: project_name is alphanumeric)
                import subprocess
                subprocess.run(["git", "init", "-q"], cwd=cwd,
                               capture_output=True, timeout=5)
            except OSError as e:
                self._send_text(chat_id, f"⚠️ Cannot create dir {cwd}: {e}")
                return

        try:
            resp = requests.post(
                f"{self._coa_dash_url}/api/claudecode/sessions",
                json={"name": project_name, "cwd": cwd},
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            result = resp.json()
            if not result.get("success"):
                self._send_text(chat_id, f"⚠️ Create failed: {result.get('error', 'unknown')}")
                return

            session = result.get("session", {})
            session_id = session.get("id", "")

            # Auto-link
            old_session = self._chat_session_map.get(lookup_key)
            if old_session and old_session != session_id:
                self._stop_poll(old_session)

            self._chat_session_map[lookup_key] = session_id
            self._session_chat_map[session_id] = lookup_key
            self._save_persistence()
            self._start_poll(session_id)

            dir_info = f"📁 Created {cwd}" if created else f"📂 {cwd}"
            self._send_text(chat_id, f"✅ Created & linked: {project_name}\n{dir_info}\nSession: {session_id}\nSend a message to start!")
        except Exception as e:
            self._send_text(chat_id, f"⚠️ Error: {e}")

    def _cmd_unlink(self, lookup_key, chat_id):
        session_id = self._chat_session_map.get(lookup_key)
        if session_id:
            del self._chat_session_map[lookup_key]
            if session_id in self._session_chat_map:
                del self._session_chat_map[session_id]
            self._stop_poll(session_id)
            self._save_persistence()
            self._send_text(chat_id, "✅ Unlinked")
        else:
            self._send_text(chat_id, "No linked session.")

    def _cmd_stop(self, lookup_key, chat_id):
        session_id = self._chat_session_map.get(lookup_key)
        if not session_id:
            self._send_text(chat_id, "No linked session.")
            return
        import subprocess
        try:
            # Look up Claude's internal session ID for accurate pgrep matching
            info = self._get_session_info(session_id)
            claude_sid = info.get("claudeSessionId", "") if info else ""
            pids = []
            # Primary: match by Claude's internal session ID
            if claude_sid:
                result = subprocess.run(
                    ["pgrep", "-f", f"claude.*--resume.*{claude_sid}"],
                    capture_output=True, text=True, timeout=3
                )
                pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            # Fallback: match by coa-dash session ID (for older sessions)
            if not pids:
                result = subprocess.run(
                    ["pgrep", "-f", f"claude.*--resume.*{session_id}"],
                    capture_output=True, text=True, timeout=3
                )
                pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            # Fallback: match by buffer file
            if not pids:
                result = subprocess.run(
                    ["pgrep", "-f", f"claude-session-{session_id}"],
                    capture_output=True, text=True, timeout=3
                )
                pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            if pids:
                for pid in pids:
                    subprocess.run(["kill", pid], timeout=3)
                try:
                    requests.put(
                        f"{self._coa_dash_url}/api/claudecode/sessions/{session_id}/status",
                        json={"status": "idle"}, timeout=5,
                    )
                except Exception:
                    pass
                self._send_text(chat_id, f"⛔ Stopped (killed {len(pids)} process(es))")
            else:
                self._send_text(chat_id, "No active process found. Session may already be idle.")
        except Exception as e:
            self._send_text(chat_id, f"⚠️ Stop failed: {e}")

    def _cmd_ls(self, chat_id, args):
        """List project directories"""
        import subprocess
        base = "/home/aegis/vault/projects"
        target = os.path.join(base, args) if args else base

        # Security: only allow listing under /home/aegis/vault/projects
        real = os.path.realpath(target)
        if not real.startswith("/home/aegis/vault/projects"):
            self._send_text(chat_id, "⚠️ Only /home/aegis/vault/projects allowed")
            return

        if not os.path.isdir(real):
            self._send_text(chat_id, f"⚠️ Not found: {target}")
            return

        try:
            entries = sorted(os.listdir(real))
            dirs = [e for e in entries if os.path.isdir(os.path.join(real, e))]
            if not dirs:
                self._send_text(chat_id, f"📂 {os.path.relpath(real, base) or '/'} — empty")
                return

            # Show up to 30 dirs, with git status indicator
            lines = [f"📂 {os.path.relpath(real, base) or '/'} ({len(dirs)} dirs)"]
            for d in dirs[:30]:
                git_mark = ""
                if os.path.isdir(os.path.join(real, d, ".git")):
                    git_mark = " *"
                lines.append(f"  {d}{git_mark}")
            if len(dirs) > 30:
                lines.append(f"  ... +{len(dirs) - 30} more")
            lines.append("\n(* = git repo)")
            self._send_text(chat_id, "\n".join(lines))
        except Exception as e:
            self._send_text(chat_id, f"⚠️ Error: {e}")

    def _cmd_compact(self, lookup_key, chat_id):
        """Compress session context by piping /compact to claude CLI"""
        session_id = self._chat_session_map.get(lookup_key)
        if not session_id:
            self._send_text(chat_id, "No linked session.")
            return

        info = self._get_session_info(session_id)
        if not info:
            self._send_text(chat_id, "Session not found.")
            return

        if info.get("status") == "working":
            self._send_text(chat_id, "⚠️ Session is working. Wait or /stop first.")
            return

        claude_sid = info.get("claudeSessionId", "")
        cwd = info.get("cwd", ".")

        if not claude_sid:
            self._send_text(chat_id, "⚠️ No Claude session ID (no conversation to compact).")
            return

        self._send_text(chat_id, "⏳ Compacting session context...")

        import subprocess
        try:
            cmd = ["claude", "--resume", claude_sid, "--dangerously-skip-permissions"]
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            stdout, stderr = proc.communicate(input="/compact\n/exit\n", timeout=120)
            if proc.returncode == 0:
                msg_count = info.get("messageCount", "?")
                self._send_text(chat_id, f"✅ Context compacted (was {msg_count} messages). Session ready.")
                print(f"[COMPACT] {session_id[:8]} done", flush=True)
            else:
                err = stderr.strip()[:200] if stderr else "unknown error"
                self._send_text(chat_id, f"⚠️ Compact failed: {err}")
        except subprocess.TimeoutExpired:
            proc.kill()
            self._send_text(chat_id, "⚠️ Compact timed out (2 min). Try again or start a new session.")
        except Exception as e:
            self._send_text(chat_id, f"⚠️ Compact error: {e}")

    def _cmd_list(self, chat_id):
        lines = ["Active Mappings:"]
        for key, sid in self._chat_session_map.items():
            info = self._get_session_info(sid)
            name = info.get("title", sid[:8]) if info else sid[:8]
            lines.append(f"  - {name} (chat {key[:8]}...)")
        if not self._chat_session_map:
            lines.append("  None. Use /link <session-id>")
        self._send_text(chat_id, "\n".join(lines))

    def _cmd_status(self, lookup_key, chat_id):
        session_id = self._chat_session_map.get(lookup_key)
        if not session_id:
            self._send_text(chat_id, "No session linked. Use /link <session-id>")
            return
        info = self._get_session_info(session_id)
        if not info:
            self._send_text(chat_id, "Session not found (may have been deleted)")
            return

        # Format duration
        dur = info.get('duration', 0)
        dur_str = f"{dur:.0f}s" if dur < 3600 else f"{dur/3600:.1f}h"

        # Context estimate (rough: ~4 chars per token, messages are in JSONL)
        msg_count = info.get('messageCount', 0)
        ctx_est = f"~{msg_count * 500:,} tokens" if msg_count > 0 else "empty"

        status = info.get('status', '?')
        activity = info.get('activity', '')
        model = info.get('model') or 'default'
        claude_sid = info.get('claudeSessionId', '')

        lines = [
            f"Session: {info.get('title', session_id[:8])}",
            f"ID: {session_id}",
            f"Claude SID: {claude_sid[:20]}..." if claude_sid else "Claude SID: (none)",
            f"Folder: {info.get('cwd', '?')}",
            f"Status: {status}" + (f" ({activity})" if activity and status != 'idle' else ""),
            f"Model: {model}",
            f"Messages: {msg_count}",
            f"Context: {ctx_est}",
            f"Duration: {dur_str}",
            f"Project: {info.get('projectName', '?')}",
        ]
        self._send_text(chat_id, "\n".join(lines))

    def _cmd_sessions(self, chat_id):
        try:
            sessions = self._get_available_sessions()
            if not sessions:
                self._send_text(chat_id, "No sessions. Create one in dashboard first.")
                return
            now = time.time()

            # Group by project, keep only latest session per project
            projects = {}
            for s in sessions:
                proj = s.get("projectName", s.get("title", s.get("name", "?")).split("/")[0])
                if proj not in projects:
                    projects[proj] = s
                else:
                    old_la = projects[proj].get("lastActiveAt") or projects[proj].get("startedAt") or 0
                    new_la = s.get("lastActiveAt") or s.get("startedAt") or 0
                    if new_la > old_la:
                        projects[proj] = s

            # Sort projects by last active time (newest first)
            sorted_projects = sorted(
                projects.items(),
                key=lambda x: x[1].get("lastActiveAt") or x[1].get("startedAt") or 0,
                reverse=True,
            )

            # Build index map for /link <n> shorthand
            index_map = {}
            lines = []
            for i, (proj, s) in enumerate(sorted_projects, 1):
                index_map[str(i)] = s["id"]
                name = s.get("title", s.get("name", "?"))
                if "/" in name:
                    name = name.split("/", 1)[1]
                status = s.get("status", "idle")
                la = s.get("lastActiveAt") or s.get("startedAt") or 0
                ago = int(now - la) if la else 0
                if ago < 60:
                    time_str = f"{ago}s ago"
                elif ago < 3600:
                    time_str = f"{ago//60}m ago"
                elif ago < 86400:
                    time_str = f"{ago//3600}h ago"
                else:
                    time_str = f"{ago//86400}d ago"
                if status == "working":
                    act = s.get("activity", "")[:30]
                    tag = f"⚡ {act}" if act else "⚡ working"
                else:
                    tag = time_str
                mc = s.get("messageCount", 0)
                lines.append(f"[{i}] {proj}/{name} ({tag}, {mc} msgs)")

            # Store index map on instance for /link resolution
            self._session_index_map = index_map

            self._send_text(chat_id, "\n".join(lines))
        except Exception as e:
            self._send_text(chat_id, f"Error: {e}")

    def _cmd_load(self, lookup_key, chat_id, args):
        """Load recent conversation rounds and display as cards"""
        session_id = self._chat_session_map.get(lookup_key)
        if not session_id:
            self._send_text(chat_id, "No session linked. Use /link <session-id>")
            return

        try:
            num_rounds = int(args.strip()) if args.strip() else 3
            num_rounds = max(1, min(num_rounds, 10))  # Clamp 1-10
        except ValueError:
            num_rounds = 3

        # Fetch history
        try:
            resp = requests.get(
                f"{self._coa_dash_url}/api/claudecode/sessions/{session_id}/history?limit=200",
                timeout=15,
            )
            if resp.status_code != 200:
                self._send_text(chat_id, f"Failed to fetch history (HTTP {resp.status_code})")
                return
            messages = resp.json().get("messages", [])
        except Exception as e:
            self._send_text(chat_id, f"Error fetching history: {e}")
            return

        # Extract conversation rounds: pair user→assistant messages
        # Walk backwards collecting assistant texts with their preceding user messages
        rounds = []
        i = len(messages) - 1
        while i >= 0 and len(rounds) < num_rounds:
            msg = messages[i]

            # Find assistant message with text
            if msg.get("type") != "assistant":
                i -= 1
                continue
            content = msg.get("message", {}).get("content", [])
            if not isinstance(content, list):
                i -= 1
                continue
            texts = []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    text = c.get("text", "").strip()
                    if text:
                        texts.append(text)
            if not texts:
                i -= 1
                continue
            assistant_text = "\n\n".join(texts)

            # Walk back to find the preceding user message with actual text
            # Skip tool_result messages (they're also type="user" but have no user text)
            user_text = ""
            j = i - 1
            while j >= 0:
                um = messages[j]
                if um.get("type") == "user":
                    uc = um.get("message", {}).get("content", "")
                    candidate = ""
                    if isinstance(uc, str):
                        candidate = uc.strip()
                    elif isinstance(uc, list):
                        parts = []
                        for c in uc:
                            if isinstance(c, dict) and c.get("type") == "text":
                                parts.append(c.get("text", "").strip())
                        candidate = " ".join(p for p in parts if p)
                    if candidate:
                        user_text = candidate
                        break
                    # Empty user msg (tool_result) — keep searching
                j -= 1

            rounds.append((user_text, assistant_text))
            i = j - 1

        if not rounds:
            self._send_text(chat_id, "No conversation history found.")
            return

        rounds.reverse()  # Chronological order

        # Combine all rounds into a single card
        info = self._get_session_info(session_id)
        project = info.get("projectName", info.get("title", "")) if info else ""

        sections = []
        for idx, (user_msg, assistant_msg) in enumerate(rounds):
            round_num = len(rounds) - idx
            q = user_msg[:200] + ("..." if len(user_msg) > 200 else "")
            a = assistant_msg[:2000] + ("...\n_(truncated)_" if len(assistant_msg) > 2000 else "")
            sections.append(f"**Q:** {q}\n\n{a}")

        card_content = "\n\n---\n\n".join(sections)
        title = f"📂 {project} — Last {len(rounds)} rounds" if project else f"📂 Last {len(rounds)} rounds"
        self._send_card(chat_id, title, card_content, "done")


    def _get_session_info(self, session_id):
        try:
            resp = requests.get(
                f"{self._coa_dash_url}/api/claudecode/sessions/{session_id}",
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    def _get_available_sessions(self):
        try:
            resp = requests.get(
                f"{self._coa_dash_url}/api/claudecode/sessions",
                timeout=10,
            )
            return resp.json().get("sessions", [])
        except Exception:
            return []

    def _forward_to_claude(self, session_id, content, chat_id, msg_id):
        try:
            print(f"[FWD] session={session_id[:8]} content={content[:60]}", flush=True)
            # Clear dedup hash — new user message, expect new response
            self._last_delivered_hash.pop(session_id, None)
            self._last_working_text.pop(session_id, None)

            # Set baseline BEFORE POST so crash doesn't cause replay
            try:
                info_resp = requests.get(
                    f"{self._coa_dash_url}/api/claudecode/sessions/{session_id}",
                    timeout=5,
                )
                if info_resp.status_code == 200:
                    mc = info_resp.json().get("messageCount", 0)
                    self._forward_baselines[session_id] = mc
                    self._save_persistence()
                    print(f"[FWD] baseline set before POST: messageCount={mc}", flush=True)
            except Exception:
                pass

            resp = requests.post(
                f"{self._coa_dash_url}/api/claudecode/sessions/{session_id}/message",
                json={"content": content},
                headers={"Content-Type": "application/json"},
                timeout=120,
            )
            result = resp.json()
            print(f"[FWD] result: injected={result.get('injected')} retained={result.get('retained')} error={result.get('error')}", flush=True)
            if resp.status_code != 200 or result.get("error"):
                if result.get("injected") or result.get("retained"):
                    pass  # Message was accepted despite error code
                elif "busy" in result.get("error", "").lower():
                    # Session busy → reaction + text feedback
                    self._replace_reaction(session_id, "Alarm")
                    self._send_text(chat_id, "⏰ 会话忙碌，请稍后重试")
                else:
                    # Error → replace reaction with ❌
                    self._replace_reaction(session_id, "CrossMark")
                    self._pending_reactions.pop(session_id, None)
            # Response comes via polling thread
        except Exception as e:
            self._send_text(chat_id, f"⚠️ Forward failed: {e}")

    # ── Send Message ──────────────────────────────────────────────────

    def _add_reaction(self, message_id, emoji_type="THUMBSUP"):
        """Add emoji reaction, returns reaction_id"""
        try:
            request_body = (
                CreateMessageReactionRequestBody.builder()
                .reaction_type({"emoji_type": emoji_type})
                .build()
            )
            req = (
                CreateMessageReactionRequest.builder()
                .message_id(message_id)
                .request_body(request_body)
                .build()
            )
            resp = self._lark_client.im.v1.message_reaction.create(req)
            if not resp.success():
                print(f"[WARN] Reaction add failed: {resp.code} {resp.msg}")
                return None
            return resp.data.reaction_id if resp.data else None
        except Exception as e:
            print(f"[WARN] Reaction add: {e}")
            return None

    def _delete_reaction(self, message_id, reaction_id):
        """Delete a reaction by its ID"""
        if not reaction_id:
            return
        try:
            req = (
                DeleteMessageReactionRequest.builder()
                .message_id(message_id)
                .reaction_id(reaction_id)
                .build()
            )
            resp = self._lark_client.im.v1.message_reaction.delete(req)
            if not resp.success():
                print(f"[WARN] Reaction delete failed: {resp.code} {resp.msg}")
        except Exception as e:
            print(f"[WARN] Reaction delete: {e}")

    def _replace_reaction(self, session_id, emoji_type):
        """Replace current status reaction with a new one"""
        msg_id = self._pending_reactions.get(session_id)
        if not msg_id:
            print(f"[REACTION] skip {emoji_type}: no msg_id for {session_id[:8]}", flush=True)
            return
        # Remove old
        old_rid = self._current_reactions.get(session_id)
        if old_rid:
            self._delete_reaction(msg_id, old_rid)
        # Add new
        new_rid = self._add_reaction(msg_id, emoji_type)
        if new_rid:
            self._current_reactions[session_id] = new_rid
            print(f"[REACTION] {session_id[:8]}: -> {emoji_type} rid={new_rid[:8]}", flush=True)
        else:
            print(f"[REACTION] {session_id[:8]}: failed to add {emoji_type}", flush=True)

    def _send_text(self, chat_id, text):
        """Send a text message to a Feishu chat (DM or group)"""
        try:
            request_body = (
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .build()
            )
            req = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(request_body)
                .build()
            )
            resp = self._lark_client.im.v1.message.create(req)
            if not resp.success():
                print(f"[WARN] Send failed: {resp.code} {resp.msg}")
                return None
            return resp.data.message_id if resp.data else None
        except Exception as e:
            print(f"[ERROR] Send: {e}")
            return None

    # ── Card Messages ──────────────────────────────────────────────────

    @staticmethod
    def _build_card_json(title, content, status="done"):
        """Build Feishu card JSON 2.0 structure"""
        # Truncate content for card display
        display = content[:3500] if len(content) > 3500 else content
        # Escape any special chars for JSON
        card = {
            "schema": "2.0",
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "blue" if status == "working" else "green" if status == "done" else "red",
            },
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": display,
                    }
                ]
            },
        }
        return json.dumps(card)

    def _send_card(self, chat_id, title, content, status="done"):
        """Send an interactive card message. Returns message_id."""
        try:
            card_content = self._build_card_json(title, content, status)
            request_body = (
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("interactive")
                .content(card_content)
                .build()
            )
            req = (
                CreateMessageRequest.builder()
                .receive_id_type("chat_id")
                .request_body(request_body)
                .build()
            )
            resp = self._lark_client.im.v1.message.create(req)
            if not resp.success():
                print(f"[WARN] Card send failed: {resp.code} {resp.msg}")
                # Fallback to plain text
                return self._send_text(chat_id, content[:4000])
            msg_id = resp.data.message_id if resp.data else None
            print(f"[CARD] sent card chat={chat_id[:8]} msg_id={msg_id[:16] if msg_id else 'None'}", flush=True)
            return msg_id
        except Exception as e:
            print(f"[ERROR] Card send: {e}")
            return self._send_text(chat_id, content[:4000])

    def _update_card(self, message_id, title, content, status="done"):
        """Update an existing card message via PatchMessage."""
        if not message_id:
            return False
        try:
            card_content = self._build_card_json(title, content, status)
            request_body = PatchMessageRequestBody.builder().content(card_content).build()
            req = PatchMessageRequest.builder().message_id(message_id).request_body(request_body).build()
            resp = self._lark_client.im.v1.message.patch(req)
            if not resp.success():
                print(f"[WARN] Card update failed: {resp.code} {resp.msg}")
                return False
            print(f"[CARD] updated card msg={message_id[:16]} status={status}", flush=True)
            return True
        except Exception as e:
            print(f"[WARN] Card update: {e}")
            return False

    # ── Polling (Claude → Feishu) ─────────────────────────────────────

    def _start_poll(self, session_id):
        if session_id in self._poll_threads:
            return
        stop_event = threading.Event()
        self._poll_stop[session_id] = stop_event
        t = threading.Thread(
            target=self._poll_loop,
            args=(session_id,),
            daemon=True,
            name=f"poll-{session_id[:8]}",
        )
        self._poll_threads[session_id] = t
        t.start()
        print(f"[INFO] Polling started: {session_id[:8]}")

    def _stop_poll(self, session_id):
        if session_id in self._poll_stop:
            self._poll_stop[session_id].set()
        if session_id in self._poll_threads:
            self._poll_threads[session_id].join(timeout=5)
            del self._poll_threads[session_id]
        if session_id in self._poll_stop:
            del self._poll_stop[session_id]
        print(f"[INFO] Polling stopped: {session_id[:8]}")

    def _poll_loop(self, session_id):
        """Poll for new Claude messages and forward to Feishu.

        Strategy:
        - Fast poll (2s) while working, cycle reaction emoji to show status
        - Slow poll (6s) while idle
        - Detect stale sessions (process dead but status stuck "working")
        - On completion, replace reaction with ✅, send card response
        """
        print(f"[POLL] thread started for {session_id[:8]}", flush=True)
        last_emoji = ""
        last_card_activity = ""  # Track activity for card update throttling
        working_since = None  # Track when we first saw "working"
        last_activity = ""
        while self._running:
            if session_id in self._poll_stop and self._poll_stop[session_id].is_set():
                break
            try:
                baseline_count = self._forward_baselines.get(session_id)

                info_resp = requests.get(
                    f"{self._coa_dash_url}/api/claudecode/sessions/{session_id}",
                    timeout=10,
                )
                if info_resp.status_code != 200:
                    # S9: Session deleted — stop poll and unlink
                    if info_resp.status_code == 404:
                        print(f"[POLL] {session_id[:8]}: session deleted, stopping poll", flush=True)
                        old_chat = self._session_chat_map.pop(session_id, None)
                        if old_chat:
                            self._chat_session_map.pop(old_chat, None)
                            self._save_persistence()
                        break
                    # API down (coa-dash restarting?) — reset baseline to avoid
                    # replaying old messages when it comes back
                    if info_resp.status_code in (0, 502, 503):
                        self._forward_baselines[session_id] = baseline_count
                    time.sleep(6)
                    continue
                info = info_resp.json()
                current_count = info.get("messageCount", 0)
                is_working = info.get("status") in ("working", "starting")
                activity = info.get("activity", "")

                # No baseline yet
                if baseline_count is None:
                    self._forward_baselines[session_id] = current_count
                    print(f"[POLL] session={session_id[:8]} baseline={current_count}", flush=True)
                    time.sleep(6)
                    continue

                # Stale session detection: working for >5 min with same activity
                if is_working:
                    if working_since is None:
                        working_since = time.time()
                        last_activity = activity
                    elif activity != last_activity:
                        # Activity changed — reset timer
                        working_since = time.time()
                        last_activity = activity
                    elif time.time() - working_since > 300:
                        # 5 min with same activity — check if process alive
                        if not self._is_claude_alive(session_id):
                            print(f"[STALE] {session_id[:8]}: working 5+ min, no process. Resetting.", flush=True)
                            self._reset_stale_session(session_id, info)
                            chat_id = self._session_chat_map.get(session_id)
                            if chat_id:
                                self._send_text(chat_id, "⚠️ Session was stuck (process died). Reset to idle. Try again.")
                            self._replace_reaction(session_id, "CrossMark")
                            working_since = None
                            last_emoji = ""
                            time.sleep(6)
                            continue
                else:
                    working_since = None

                # Update reaction while working (status changes)
                if is_working:
                    emoji = self._activity_emoji(activity)
                    if emoji and emoji != last_emoji:
                        self._replace_reaction(session_id, emoji)
                        last_emoji = emoji
                        print(f"[POLL] {emoji} ({activity})", flush=True)

                    # Send/update status card showing current activity (throttled)
                    if activity != last_card_activity:
                        chat_id_for_card = self._session_chat_map.get(session_id)
                        if chat_id_for_card:
                            card_id = self._response_cards.get(session_id)
                            status_text = f"**{activity}**"
                            if card_id:
                                self._update_card(card_id, "Claude (working)", status_text, "working")
                            else:
                                card_id = self._send_card(chat_id_for_card, "Claude (working)", status_text, "working")
                                if card_id:
                                    self._response_cards[session_id] = card_id
                        last_card_activity = activity

                # No new messages
                if current_count <= baseline_count:
                    time.sleep(2 if is_working else 6)
                    continue

                # New messages detected
                new_count = current_count - baseline_count
                chat_id = self._session_chat_map.get(session_id)
                if not chat_id:
                    time.sleep(6)
                    continue

                # Fetch history
                resp = requests.get(
                    f"{self._coa_dash_url}/api/claudecode/sessions/{session_id}/history?limit={max(new_count + 20, 50)}",
                    timeout=15,
                )
                if resp.status_code != 200:
                    time.sleep(2)
                    continue

                messages = resp.json().get("messages", [])
                skip = max(0, len(messages) - new_count)
                new_msgs = messages[skip:]

                # Collect the LAST assistant response that has text content
                last_assistant_text = ""
                for msg in reversed(new_msgs):
                    if msg.get("type") != "assistant":
                        continue
                    content = msg.get("message", {}).get("content", [])
                    if not isinstance(content, list):
                        continue
                    texts = []
                    for c in content:
                        if isinstance(c, dict) and c.get("type") == "text":
                            text = c.get("text", "").strip()
                            if text:
                                texts.append(text)
                    if texts:
                        last_assistant_text = "\n\n".join(texts)
                        break

                if not last_assistant_text:
                    time.sleep(2 if is_working else 6)
                    continue

                if is_working:
                    # Still working — update reaction, update card with partial
                    emoji = self._activity_emoji(activity)
                    if emoji and emoji != last_emoji:
                        self._replace_reaction(session_id, emoji)
                        last_emoji = emoji

                    # Throttle: skip card update if text hasn't changed
                    prev_text = self._last_working_text.get(session_id, "")
                    if last_assistant_text != prev_text:
                        # Dedup: skip if this content was already delivered as a done card
                        text_hash = hashlib.md5(last_assistant_text.encode()).hexdigest()[:12]
                        if text_hash != self._last_delivered_hash.get(session_id):
                            card_id = self._response_cards.get(session_id)
                            chat_id_for_card = self._session_chat_map.get(session_id)
                            if chat_id_for_card:
                                if card_id:
                                    self._update_card(card_id, "Claude (working...)", last_assistant_text, "working")
                                else:
                                    card_id = self._send_card(chat_id_for_card, "Claude (working...)", last_assistant_text, "working")
                                    if card_id:
                                        self._response_cards[session_id] = card_id
                            self._last_working_text[session_id] = last_assistant_text
                    time.sleep(2)
                else:
                    # Done — replace reaction with ✅, send card response
                    # Dedup: skip if same content was already delivered
                    content_hash = hashlib.md5(last_assistant_text.encode()).hexdigest()[:12]
                    if content_hash == self._last_delivered_hash.get(session_id):
                        print(f"[POLL] {session_id[:8]} skip duplicate (hash={content_hash})", flush=True)
                        self._forward_baselines[session_id] = current_count
                        self._save_persistence()
                        time.sleep(6)
                        continue

                    self._replace_reaction(session_id, "CheckMark")

                    # Always send a new card for the final response
                    card_id = self._send_card(chat_id, "Claude", last_assistant_text, "done")

                    # Clear working card ref — next message creates a fresh working card
                    # instead of overwriting this done card
                    self._response_cards.pop(session_id, None)

                    self._forward_baselines[session_id] = current_count
                    self._pending_reactions.pop(session_id, None)
                    self._current_reactions.pop(session_id, None)
                    self._last_delivered_hash[session_id] = content_hash
                    self._last_working_text.pop(session_id, None)
                    last_emoji = ""
                    last_card_activity = ""
                    self._save_persistence()  # Persist baseline after delivery

                    print(f"[POLL→Feishu] session={session_id[:8]} done len={len(last_assistant_text)} card={card_id is not None} hash={content_hash}", flush=True)
                    time.sleep(6)

            except (requests.ConnectionError, requests.Timeout) as e:
                # coa-dash likely restarting — reset baseline to current count
                # to avoid replaying old messages when it comes back
                print(f"[WARN] Poll {session_id[:8]}: connection error, syncing baseline", flush=True)
                try:
                    resp = requests.get(
                        f"{self._coa_dash_url}/api/claudecode/sessions/{session_id}",
                        timeout=5,
                    )
                    if resp.status_code == 200:
                        new_baseline = resp.json().get("messageCount", 0)
                        self._forward_baselines[session_id] = new_baseline
                        print(f"[POLL] {session_id[:8]} baseline synced to {new_baseline}", flush=True)
                except Exception:
                    pass
                time.sleep(6)
            except Exception as e:
                print(f"[WARN] Poll {session_id[:8]}: {e}")
                time.sleep(6)

    def _is_claude_alive(self, session_id):
        """Check if a Claude process is still running for this session."""
        import subprocess
        try:
            # Look up Claude's internal session ID
            info = self._get_session_info(session_id)
            claude_sid = info.get("claudeSessionId", "") if info else ""
            # Primary: match by Claude's internal session ID
            if claude_sid:
                result = subprocess.run(
                    ["pgrep", "-f", f"claude.*--resume.*{claude_sid}"],
                    capture_output=True, text=True, timeout=3
                )
                if result.stdout.strip():
                    return True
            # Fallback: match by coa-dash session ID
            result = subprocess.run(
                ["pgrep", "-f", f"claude.*--resume.*{session_id}"],
                capture_output=True, text=True, timeout=3
            )
            if result.stdout.strip():
                return True
            # Fallback: match by buffer file
            result2 = subprocess.run(
                ["pgrep", "-f", f"claude-session-{session_id}"],
                capture_output=True, text=True, timeout=3
            )
            return bool(result2.stdout.strip())
        except Exception:
            return False

    def _reset_stale_session(self, session_id, info):
        """Force reset a stuck session to idle via coa-dash API."""
        # Try the reset endpoint if available
        try:
            resp = requests.put(
                f"{self._coa_dash_url}/api/claudecode/sessions/{session_id}/status",
                json={"status": "idle", "activity": "Reset (stale process)"},
                timeout=5,
            )
            if resp.status_code == 200:
                print(f"[STALE] {session_id[:8]} reset via API", flush=True)
                return
        except Exception:
            pass
        # Fallback: no API endpoint to reset status directly
        # The server.py doesn't expose a status reset endpoint, so we just
        # note it and handle it in the bridge (skip forward, notify user)
        print(f"[STALE] {session_id[:8]} no reset API available", flush=True)

    def _activity_emoji(self, activity):
        """Map session activity to valid Feishu emoji_type"""
        if not activity:
            return "Typing"
        a = activity.lower()
        if "think" in a:
            return "THINKING"
        if "tool" in a:
            tool = a.split(":", 1)[-1].strip() if ":" in a else ""
            tool_map = {
                "read": "Pin",           # Pin = bookmarking what you read
                "write": "Fire",
                "edit": "Fire",
                "bash": "BOMB",
                "grep": "SMART",
                "glob": "Pin",
                "agent": "STRIVE",
                "web": "LOOKDOWN",
                "search": "SMART",
            }
            for k, v in tool_map.items():
                if k in tool:
                    return v
            return "STRIVE"
        if "done" in a:
            return "CheckMark"
        if "error" in a:
            return "CrossMark"
        if "timeout" in a:
            return "SWEAT"
        if "send" in a or "resume" in a:
            return "ROCKET"
        return "Typing"


def main():
    bridge = FeishuBridge()
    try:
        bridge.start()
    except KeyboardInterrupt:
        bridge.stop()


if __name__ == "__main__":
    main()
